import csv
from pathlib import Path

def build_frequency_from_unidic(
    unidic_dir="unidic-csj-3.1.0",
    output_tsv="word_frequency.tsv"
):
    unidic_path = Path(unidic_dir)
    if not unidic_path.exists():
        raise FileNotFoundError(f"UniDic directory not found: {unidic_path}")

    print(f"Scanning {unidic_path} for lexicon CSV...")

    # Find lex_*.csv (e.g., lex_3_1.csv)
    lex_candidates = list(unidic_path.glob("lex_*.csv"))
    if not lex_candidates:
        raise RuntimeError("No lex_*.csv file found in UniDic directory.")

    lex_file = lex_candidates[0]
    print(f"Found lexicon file: {lex_file.name}")

    print("Reading lexicon...")

    entries = []
    with open(lex_file, encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue

            word = row[0]
            freq = row[-1]  # last column = token count

            if freq.isdigit():
                entries.append((word, int(freq)))

    print("Sorting by frequency...")

    entries.sort(key=lambda x: x[1], reverse=True)

    ranked = [(word, rank + 1) for rank, (word, _) in enumerate(entries)]

    print(f"Saving cleaned TSV to {output_tsv}...")

    with open(output_tsv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        for word, rank in ranked:
            writer.writerow([word, rank])

    print("Done.")

if __name__ == "__main__":
    build_frequency_from_unidic()
