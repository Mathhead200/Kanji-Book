import json
import time
import random
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import cloudscraper
from bs4 import BeautifulSoup
from urllib.parse import quote
from tqdm import tqdm

from name_scraper import parse_name_list


KANJI_JSON_IN = "kanji_data_with_freq.json"
RADICAL_JSON_IN = "radical_data_with_freq.json"

KANJI_JSON_OUT = "kanji_data_with_names.json"
RADICAL_JSON_OUT = "radical_data_with_names.json"

CACHE_FILE = "name_cache.json"

BASE_URL = "https://japanese-names.info/kanji/{}/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_cache():
    if Path(CACHE_FILE).exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def make_scraper():
    return cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )


def is_cloudflare_challenge(html):
    if html is None:
        return False
    html = html.lower()
    return (
        "cf-browser-verification" in html
        or "cf-challenge" in html
        or "just a moment" in html
        or "attention required" in html
    )


def fetch_html(scraper, url):
    for attempt in range(5):
        time.sleep(random.uniform(0.3, 0.9))  # pre-request jitter

        try:
            r = scraper.get(url, headers=HEADERS, timeout=20)

            if r.status_code == 403:
                time.sleep(random.uniform(1.0, 2.0))
                continue

            if is_cloudflare_challenge(r.text):
                time.sleep(random.uniform(1.5, 3.0))
                continue

            r.raise_for_status()
            return r.text

        except Exception:
            time.sleep(random.uniform(1.0, 2.0))

    return None


def scrape_one_kanji(kanji, cache, scraper):
    if kanji in cache:
        return kanji, cache[kanji]

    url = BASE_URL.format(quote(kanji))
    html = fetch_html(scraper, url)

    if not html:
        print(f"Failed to scrape {kanji}")
        cache[kanji] = {"given": [], "family": []}
        save_cache(cache)
        return kanji, cache[kanji]

    soup = BeautifulSoup(html, "html.parser")
    lists = soup.find_all("ul", class_="name-list")

    given = parse_name_list(lists[0]) if len(lists) > 0 else []
    family = parse_name_list(lists[1]) if len(lists) > 1 else []

    cache[kanji] = {"given": given, "family": family}
    save_cache(cache)

    time.sleep(random.uniform(0.2, 0.6))  # post-request jitter

    return kanji, cache[kanji]


def scrape_all_kanji_parallel(kanji_list, cache, threads=5):
    results = {}

    scrapers = [make_scraper() for _ in range(threads)]

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = {}
        for i, k in enumerate(kanji_list):
            scraper = scrapers[i % threads]
            futures[executor.submit(scrape_one_kanji, k, cache, scraper)] = k

        for future in tqdm(as_completed(futures), total=len(futures), desc="Scraping kanji"):
            kanji, data = future.result()
            results[kanji] = data

    return results


def freq_to_rank(freq):
    if freq is None:
        return float("inf")
    freq = freq.lower()

    if freq.startswith("under "):
        try:
            return int(freq.replace("under ", ""))
        except:
            return float("inf")

    if freq.startswith("aprx."):
        try:
            return int(freq.replace("aprx.", "").strip())
        except:
            return float("inf")

    try:
        return int(freq)
    except:
        return float("inf")


def extract_top_family_names(radical_entry, kanji_data):
    family_entries = []

    for k in radical_entry["kanji"]:
        names = kanji_data.get(k, {}).get("names", {})
        for fam in names.get("family", []):
            family_entries.append(fam)

    family_entries.sort(key=lambda x: freq_to_rank(x.get("frequency")))
    return family_entries[:5]


def build_radical_name_mapping(radical_data, kanji_data):
    new_radical_data = {}

    for rad, entry in radical_data.items():
        top_families = extract_top_family_names(entry, kanji_data)
        new_entry = dict(entry)
        new_entry["top_family_names"] = top_families
        new_radical_data[rad] = new_entry

    return new_radical_data


def main():
    print("Working directory:", os.getcwd())

    print("Loading JSON…")
    kanji_data = load_json(KANJI_JSON_IN)
    radical_data = load_json(RADICAL_JSON_IN)

    print("Loading cache…")
    cache = load_cache()

    all_kanji = list(kanji_data.keys())

    print(f"Scraping {len(all_kanji)} kanji in safe parallel mode (5 threads)…")
    results = scrape_all_kanji_parallel(all_kanji, cache, threads=5)

    print("Merging names into kanji data…")
    for kanji, names in results.items():
        kanji_data[kanji]["names"] = names

    print("Building radical name aggregates…")
    radical_data_with_names = build_radical_name_mapping(radical_data, kanji_data)

    print("Saving output JSON files…")
    save_json(KANJI_JSON_OUT, kanji_data)
    save_json(RADICAL_JSON_OUT, radical_data_with_names)

    print("Done.")


if __name__ == "__main__":
    main()
