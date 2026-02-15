import csv
import json
from pathlib import Path


# ---------------------------------------------------------
# 1. English phoneme inventory (from your normalization script)
# ---------------------------------------------------------
from en_IPA_normalizer import ENGLISH_PHONEMES

# ---------------------------------------------------------
# 2. Japanese phoneme inventory (derived from your kana → IPA)
# ---------------------------------------------------------
from script4 import KANA_TO_IPA, YOON

# ---------------------------------------------------------
# 3. Extract Japanese phonemes (single segments)
# ---------------------------------------------------------

def extract_japanese_phonemes():
    phonemes = set()

    # From simple kana
    for ipa in KANA_TO_IPA.values():
        for ch in ipa:
            phonemes.add(ch)

    # From yoon combinations
    for ipa in YOON.values():
        for ch in ipa:
            phonemes.add(ch)

    return phonemes

JAPANESE_PHONEMES = extract_japanese_phonemes()

# ---------------------------------------------------------
# 4. Build the full target phoneme set
# ---------------------------------------------------------

TARGET_PHONEMES = set(ENGLISH_PHONEMES) | set(JAPANESE_PHONEMES)

# ---------------------------------------------------------
# 5. Load PHOIBLE CSV and extract feature vectors
# ---------------------------------------------------------

def build_phoneme_features(phoible_csv="phoible.csv", output="phoneme_features.json"):
    feature_vectors = {}
    feature_columns = None

    with open(phoible_csv, encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # Identify feature columns (everything after "SegmentClass")
        all_columns = reader.fieldnames
        idx = all_columns.index("SegmentClass") + 1
        feature_columns = all_columns[idx:]

        for row in reader:
            seg = row["Phoneme"]

            if seg not in TARGET_PHONEMES:
                continue

            # Extract feature vector
            features = {col: row[col] for col in feature_columns}

            # If phoneme appears multiple times, keep the first
            if seg not in feature_vectors:
                feature_vectors[seg] = features

    Path(output).write_text(
        json.dumps(feature_vectors, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Saved {len(feature_vectors)} phoneme feature vectors to {output}")

# ---------------------------------------------------------
# 6. Run
# ---------------------------------------------------------

if __name__ == "__main__":
    build_phoneme_features()
