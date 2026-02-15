import csv
import json
from collections import defaultdict

KANJI_JSON_IN = "kanji_data.json"
RADICAL_JSON_IN = "radical_data.json"
FREQ_CSV = "2242KANJIFREQUENCYLISTVER.1.1 - MAIN.csv"

KANJI_JSON_OUT = "kanji_data_with_freq.json"
RADICAL_JSON_OUT = "radical_data_with_freq.json"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_frequency_csv(path):
    freq = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=",")
        for row in reader:
            kanji = row["FORM"]
            # Convert numeric fields to integers where possible
            clean_row = {}
            for k, v in row.items():
                if k == "FORM":
                    continue
                try:
                    clean_row[k] = int(v)
                except ValueError:
                    clean_row[k] = v
            freq[kanji] = clean_row
    return freq


def merge_kanji_frequency(kanji_data, freq_data):
    for kanji, info in kanji_data.items():
        if kanji in freq_data:
            info["frequency"] = freq_data[kanji]
        else:
            info["frequency"] = None
    return kanji_data


def aggregate_radical_frequency(radical_data, kanji_data):
    """
    For each radical:
      - Look at all kanji under that radical
      - For each frequency category, take the MIN (best rank)
    """
    radical_freq = {}

    for rad, entry in radical_data.items():
        kanji_list = entry["kanji"]

        # Collect all frequency categories
        categories = set()
        for k in kanji_list:
            freq = kanji_data.get(k, {}).get("frequency")
            if freq:
                categories.update(freq.keys())

        # Compute minimum per category
        agg = {}
        for cat in categories:
            values = []
            for k in kanji_list:
                freq = kanji_data.get(k, {}).get("frequency")
                if freq and isinstance(freq.get(cat), int):
                    values.append(freq[cat])
            agg[cat] = min(values) if values else None

        radical_freq[rad] = {
            "radical_char": entry["radical_char"],
            "kanji": kanji_list,
            "stroke_count": entry.get("stroke_count"),
            "count": entry.get("count"),
            "frequency": agg
        }

    return radical_freq


def main():
    print("Loading JSON…")
    kanji_data = load_json(KANJI_JSON_IN)
    radical_data = load_json(RADICAL_JSON_IN)

    print("Loading frequency CSV…")
    freq_data = load_frequency_csv(FREQ_CSV)

    print("Merging kanji frequency data…")
    kanji_data = merge_kanji_frequency(kanji_data, freq_data)

    print("Aggregating radical frequency data…")
    radical_data_with_freq = aggregate_radical_frequency(radical_data, kanji_data)

    print("Saving output JSON files…")
    save_json(KANJI_JSON_OUT, kanji_data)
    save_json(RADICAL_JSON_OUT, radical_data_with_freq)

    print("Done.")


if __name__ == "__main__":
    main()
