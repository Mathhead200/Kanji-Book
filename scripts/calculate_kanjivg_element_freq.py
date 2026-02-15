#!/usr/bin/env python3
import json
import csv
import os

ELEMENT_STATS_PATH = "data/element_stats.json"
FREQ_CSV_PATH = "data/2242KANJIFREQUENCYLISTVER.1.1 - MAIN.csv"
OUTPUT_CSV_PATH = "data/element_freq.csv"

DEFAULT_AVG_FREQ = 10000.0  # fallback for unknown kanji


def load_element_stats(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def detect_kanji_column(header):
    candidates = ["FORM", "KANJI", "Kanji", "Character", "CHAR", "char"]
    for c in candidates:
        if c in header:
            return c
    raise ValueError(f"Could not find a kanji column in header: {header}")


def detect_avg_freq_column(header):
    candidates = ["AVG FREQ", "AVG_FREQ", "AvgFreq", "Avg Freq", "avg_freq"]
    for c in candidates:
        if c in header:
            return c
    raise ValueError(f"Could not find an AVG FREQ column in header: {header}")


def load_frequency_weights(path):
    weights = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames

        kanji_col = detect_kanji_column(header)
        avg_freq_col = detect_avg_freq_column(header)

        for row in reader:
            k = row[kanji_col].strip()
            if not k:
                continue
            try:
                avg_freq = float(row[avg_freq_col])
                if avg_freq <= 0:
                    avg_freq = DEFAULT_AVG_FREQ
            except:
                avg_freq = DEFAULT_AVG_FREQ

            weights[k] = 1.0 / avg_freq

    return weights


def compute_frequency_scores(element_stats, weights):
    scores = {}

    for elem, stats in element_stats.items():
        kanji_list = stats.get("kanji_list", [])

        # If no kanji use this element → score = 0
        if not kanji_list:
            scores[elem] = 0.0
            continue

        score = 0.0
        for k in kanji_list:
            score += weights.get(k, 1.0 / DEFAULT_AVG_FREQ)

        scores[elem] = score

    return scores


def write_output_csv(element_stats, scores, out_path):
    rows = []

    for elem, stats in element_stats.items():
        # Only include elements that appear in at least one kanji
        if stats.get("kanji_count", 0) == 0:
            continue

        rows.append({
            "element": elem,
            "freq_score": scores.get(elem, 0.0),
            "kanji_count": stats.get("kanji_count", 0),
            "is_kanji": stats.get("is_kanji", False),
        })

    rows.sort(key=lambda r: (-r["freq_score"], r["element"]))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["element", "freq_score", "kanji_count", "is_kanji"]
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def main():
    element_stats = load_element_stats(ELEMENT_STATS_PATH)

    # Identify kanji
    kanji_set = {e for e, s in element_stats.items() if s.get("is_kanji", False)}
    print(f"Total kanji: {len(kanji_set)}")

    # Load frequency weights
    weights = load_frequency_weights(FREQ_CSV_PATH)
    print(f"Loaded {len(weights)} kanji frequency weights")

    # Compute element frequency scores
    scores = compute_frequency_scores(element_stats, weights)

    # Write CSV
    write_output_csv(element_stats, scores, OUTPUT_CSV_PATH)
    print(f"Wrote element frequency table to: {OUTPUT_CSV_PATH}")


if __name__ == "__main__":
    main()
