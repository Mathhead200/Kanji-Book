import json
import time
import requests
from pathlib import Path

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

# yōon combinations
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
        # yōon (small ゃゅょ)
        if i + 1 < len(kana) and kana[i:i+2] in YOON:
            ipa.append(YOON[kana[i:i+2]])
            i += 2
            continue
        # regular kana
        if kana[i] in KANA_TO_IPA:
            ipa.append(KANA_TO_IPA[kana[i]])
        else:
            ipa.append(kana[i])  # fallback
        i += 1
    return ".".join(ipa)

# ---------------------------------------------------------
# 2. Load frequency table (optional)
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
# 3. Word cache
# ---------------------------------------------------------

def load_cache(path):
    if Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return {}

def save_cache(path, cache):
    Path(path).write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------------------------------------------------------
# 4. Fetch words from kanjiapi.dev
# ---------------------------------------------------------

def fetch_words_for_kanji(kanji):
    url = f"https://kanjiapi.dev/v1/words/{kanji}"
    r = requests.get(url)
    if r.status_code != 200:
        return []
    return r.json()

# ---------------------------------------------------------
# 5. Main processing
# ---------------------------------------------------------

def process_kanji_file(
    kanji_file,
    freq_file=None,
    cache_file="word_cache.json",
    output_file="kanji_with_words.json"
):
    kanji_data = json.loads(Path(kanji_file).read_text(encoding="utf-8"))
    freq_table = load_frequency_table(freq_file)
    cache = load_cache(cache_file)

    for literal, entry in kanji_data.items():
        if literal in cache:
            kanji_data[literal]["words"] = cache[literal]
            continue

        print(f"Fetching words for {literal}...")
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

        cache[literal] = processed
        kanji_data[literal]["words"] = processed

        save_cache(cache_file, cache)
        time.sleep(0.2)  # be polite to the API

    Path(output_file).write_text(
        json.dumps(kanji_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


# ---------------------------------------------------------
# 6. Run
# ---------------------------------------------------------

if __name__ == "__main__":
    process_kanji_file(
        kanji_file="kanji_data_with_names.json",  # kanji_file="kanji_data.json",
        freq_file="word_frequency.tsv",
        cache_file="word_cache.json",
        output_file="kanji_with_words.json"
    )
