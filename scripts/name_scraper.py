import json
import cloudscraper
from bs4 import BeautifulSoup
from urllib.parse import quote


BASE_URL = "https://japanese-names.info/kanji/{}/"


def fetch_html(url: str) -> str:
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }
    r = scraper.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.text


def parse_name_list(ul):
    results = []

    for li in ul.find_all("li", recursive=False):
        title = li.find("div", class_="title")
        summary = li.find("div", class_="name_summary")
        if not title or not summary:
            continue

        # ROMAJI (in <h3>)
        romaji = None
        h3 = title.find("h3")
        if h3:
            romaji = h3.get_text(strip=True)

        # KANJI + MEANING (in <a><strong>KANJI</strong>meaning text…</a>)
        kanji = None
        meaning = None

        a = summary.find("a")
        if a:
            strong = a.find("strong")
            if strong:
                kanji = strong.get_text(strip=True)

                # Meaning = everything in the <a> AFTER the <strong>
                meaning_parts = []
                for elem in strong.next_siblings:
                    if isinstance(elem, str):
                        meaning_parts.append(elem.strip())
                    else:
                        meaning_parts.append(elem.get_text(strip=True))

                meaning = " ".join(p for p in meaning_parts if p).strip()
                if meaning == "":
                    meaning = None

        # FREQUENCY
        frequency_parts = []

        # Tooltip (optional)
        icon = summary.select_one("span.ico_households_tips")
        tooltip = icon.get("title").strip() if icon and icon.get("title") else None
        if tooltip:
            frequency_parts.append(tooltip)

        # Suffix (optional: "aprx.")
        suffix_span = summary.find("span", class_="num_sfx")
        suffix = suffix_span.get_text(strip=True) if suffix_span else None
        if suffix:
            frequency_parts.append(suffix)

        # Case 1: number after <span class="num_sfx">
        number = None
        if suffix_span:
            next_text = suffix_span.next_sibling
            if next_text and isinstance(next_text, str):
                number = next_text.strip()
                if number:
                    frequency_parts.append(number)

        # Case 2: number after <span class="q-icon-all"> (e.g. "under 10")
        if not number:
            qicon = summary.find("span", class_="q-icon-all")
            if qicon:
                next_text = qicon.next_sibling
                if next_text and isinstance(next_text, str):
                    raw = next_text.strip()
                    if raw:
                        frequency_parts.append(raw)

        frequency = " ".join(frequency_parts) if frequency_parts else None

        results.append(
            {
                "kanji": kanji,
                "romaji": romaji,
                "meaning": meaning,
                "frequency": frequency,
            }
        )

    return results


def get_names_for_kanji(kanji: str) -> str:
    encoded = quote(kanji)
    url = BASE_URL.format(encoded)

    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    # Two <ul class="name-list"> blocks:
    #   1st = given names
    #   2nd = family names
    lists = soup.find_all("ul", class_="name-list")

    given = parse_name_list(lists[0]) if len(lists) > 0 else []
    family = parse_name_list(lists[1]) if len(lists) > 1 else []

    return json.dumps(
        {"given_names": given, "family_names": family},
        ensure_ascii=False,
        indent=2,
    )


if __name__ == "__main__":
    print(get_names_for_kanji("良"))
