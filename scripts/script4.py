import json
import time
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from tqdm import tqdm

# ---------------------------------------------------------
# 1. Kana → IPA conversion
# ---------------------------------------------------------

KANA_TO_IPA = {
    "あ": "a", "い": "i", "う": "ɯ", "え": "e", "お": "o",
    "か": "ka", "き": "ki", "く": "kɯ", "け": "ke", "こ": "ko",
    "さ": "sa", "し": "ɕi", "す": "sɯ", "せ": "se", "そ": "so",
    "た": "ta", "ち": "tɕi", "つ": "tsɯ", "て": "te", "と": "to",
    "な": "na", "に": "ni", "ぬ": "nɯ", "ね": "ne", "の": "no",
    "は": "ha", "ひ": "çi", "ふ": "ɸɯ", "へ": "he", "ほ": "ho",
    "ま": "ma", "み": "mi", "む": "mɯ", "め": "me", "も": "mo",
    "や": "ja", "ゆ": "jɯ", "よ": "jo",
    "ら": "ɾa", "り": "ɾi", "る": "ɾɯ", "れ": "ɾe", "ろ": "ɾo",
    "わ": "wa", "を": "o",
    "ん": "N",
    "が": "ga", "ぎ": "gi", "ぐ": "gɯ", "げ": "ge", "ご": "go",
    "ざ": "za", "じ": "dʑi", "ず": "zɯ", "ぜ": "ze", "ぞ": "zo",
    "だ": "da", "ぢ": "dʑi", "づ": "dzɯ", "で": "de", "ど": "do",
    "ば": "ba", "び": "bi", "ぶ": "bɯ", "べ": "be", "ぼ": "bo",
    "ぱ": "pa", "ぴ": "pi", "ぷ": "pɯ", "ぺ": "pe", "ぽ": "po",
}

YOON = {
    "きゃ": "kʲa", "きゅ": "kʲɯ", "きょ": "kʲo",
    "しゃ": "ɕa", "しゅ": "ɕɯ", "しょ": "ɕo",
    "ちゃ": "tɕa", "ちゅ": "tɕɯ", "ちょ": "tɕo",
    "にゃ": "ɲa", "にゅ": "ɲɯ", "にょ": "ɲo",
    "ひゃ": "ça", "ひゅ": "çɯ", "ひょ": "ço",
    "みゃ": "mʲa", "みゅ": "mʲɯ", "みょ": "mʲo",
    "りゃ": "ɾʲa", "りゅ": "ɾʲɯ", "りょ": "ɾʲo",
    "ぎゃ": "gʲa", "ぎゅ": "gʲɯ", "ぎょ": "gʲo",
    "じゃ": "dʑa", "じゅ": "dʑɯ", "じょ": "dʑo",
    "びゃ": "bʲa", "びゅ": "bʲɯ", "びょ": "bʲo",
    "ぴゃ": "pʲa", "ぴゅ": "pʲɯ", "ぴょ": "pʲo",
}

def kana_to_ipa(kana):
    ipa = []
    i = 0
    while i < len(kana):
        if i + 1 < len(kana) and kana[i:i+2] in YOON:
            ipa.append(YOON[kana[i:i+2]])
            i += 2
            continue
        ipa.append(KANA_TO_IPA.get(kana[i], kana[i]))
        i += 1
    return ".".join(ipa)

# ---------------------------------------------------------
# 2. Frequency table
# ---------------------------------------------------------

def load_frequency_table(path):
    freq = {}
    if not path:
        return freq
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                word, rank = parts[0], parts[1]
                freq[word] = int(rank)
    return freq

# ---------------------------------------------------------
# 3. Cache
# ---------------------------------------------------------

def load_cache(path):
    if Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return {}

def save_cache(path, cache):
    Path(path).write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------------------------------------------------------
# 4. API fetch
# ---------------------------------------------------------

def fetch_words_for_kanji(kanji):
    url = f"https://kanjiapi.dev/v1/words/{kanji}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return []
        return r.json()
    except Exception:
        return []

# ---------------------------------------------------------
# 5. Worker for one kanji
# ---------------------------------------------------------

def process_single_kanji(literal, freq_table):
    words_raw = fetch_words_for_kanji(literal)
    processed = []

    for w in words_raw:
        meanings = w.get("meanings", [])
        variants = w.get("variants", [])

        for v in variants:
            word = v.get("written")
            kana = v.get("pronounced")

            ipa = kana_to_ipa(kana) if kana else None
            freq = freq_table.get(word, None)

            processed.append({
                "word": word,
                "kana": kana,
                "meanings": meanings,
                "frequency": freq,
                "ipa": ipa
            })

    return literal, processed

# ---------------------------------------------------------
# 6. Parallel main with count‑based resume
# ---------------------------------------------------------

def process_kanji_file(
    kanji_file,
    freq_file=None,
    cache_file="word_cache.json",
    output_file="kanji_with_words.json",
    max_workers=12
):
    kanji_data = json.loads(Path(kanji_file).read_text(encoding="utf-8"))
    freq_table = load_frequency_table(freq_file)
    cache = load_cache(cache_file)

    lock = Lock()

    # Only process kanji whose cached count doesn't match
    kanji_to_process = []
    for k in kanji_data.keys():
        if k not in cache:
            kanji_to_process.append(k)
        else:
            expected = cache[k].get("count")
            actual = len(cache[k].get("words", []))
            if expected != actual:
                kanji_to_process.append(k)

    print(f"Processing {len(kanji_to_process)} kanji in parallel...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_single_kanji, literal, freq_table): literal
            for literal in kanji_to_process
        }

        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing kanji"):
            literal, processed_words = future.result()

            entry = {
                "count": len(processed_words),
                "words": processed_words
            }

            with lock:
                cache[literal] = entry
                kanji_data[literal]["words"] = processed_words
                save_cache(cache_file, cache)

    Path(output_file).write_text(
        json.dumps(kanji_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("All kanji processed.")

# ---------------------------------------------------------
# 7. Run
# ---------------------------------------------------------

if __name__ == "__main__":
    process_kanji_file(
        kanji_file="kanji_data_with_names.json",
        freq_file="word_frequency.tsv",
        cache_file="word_cache.json",
        output_file="kanji_with_words.json",
        max_workers=20
    )
