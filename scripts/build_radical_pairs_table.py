import json
import csv
from itertools import combinations

KANJI_PATH = "data/kanji_data_1.json"
RADICAL_PATH = "data/radical_data.json"
OUTPUT_CSV = "radical_cooccurrence_matrix.csv"

# ------------------------------------------------------------
# Load data
# ------------------------------------------------------------
with open(KANJI_PATH, "r", encoding="utf-8") as f:
    kanji_data = json.load(f)

with open(RADICAL_PATH, "r", encoding="utf-8") as f:
    radical_info = json.load(f)

# ------------------------------------------------------------
# Build radical index → radical_char mapping
# ------------------------------------------------------------
radical_numbers = sorted(int(k) for k in radical_info.keys())
radical_chars = {int(k): radical_info[k]["radical_char"] for k in radical_info}
radical_labels = {r: f"{r}. {radical_chars[r]}" for r in radical_numbers}

# ------------------------------------------------------------
# Initialize matrix counts
# ------------------------------------------------------------
matrix = {r: {c: 0 for c in radical_numbers} for r in radical_numbers}

# ------------------------------------------------------------
# Count co-occurrences
# ------------------------------------------------------------
for entry in kanji_data.values():
    rads = entry.get("radicals", [])
    unique_rads = sorted(set(rads))

    # Diagonal counts
    for r in unique_rads:
        if r in matrix:
            matrix[r][r] += 1

    # Off-diagonal unordered pairs
    for a, b in combinations(unique_rads, 2):
        if a in matrix and b in matrix[a]:
            matrix[a][b] += 1
            matrix[b][a] += 1

# ------------------------------------------------------------
# Sort radicals by diagonal frequency (descending)
# ------------------------------------------------------------
sorted_radicals = sorted(
    radical_numbers,
    key=lambda r: matrix[r][r],
    reverse=True
)

# ------------------------------------------------------------
# Write CSV
# ------------------------------------------------------------
with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)

    # Header row
    header = [""] + [radical_labels[r] for r in sorted_radicals]
    writer.writerow(header)

    # Rows in sorted order
    for r in sorted_radicals:
        row = [radical_labels[r]] + [matrix[r][c] for c in sorted_radicals]
        writer.writerow(row)
