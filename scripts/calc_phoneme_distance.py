import json
import csv
import math

# -----------------------------
# 1. Load feature JSON
# -----------------------------
with open("phoneme_features.json", "r", encoding="utf8") as f:
    FEATURES = json.load(f)

# -----------------------------
# 2. Encode +, -, 0 → numeric
# -----------------------------
def encode_value(v):
    if v == "+":
        return 1
    if v == "-":
        return -1
    return 0

def encode_feature_vector(feat_dict):
    return {k: encode_value(v) for k, v in feat_dict.items() if k != "Source"}

ENCODED = {p: encode_feature_vector(f) for p, f in FEATURES.items()}

# -----------------------------
# 3. Perceptual weights (English listener)
# -----------------------------
# Why these weights: https://copilot.microsoft.com/shares/49cwALcFh96ht2bR39qVj
WEIGHTS = {
    # Manner
    "consonantal": 2.0,
    "sonorant": 2.0,
    "continuant": 2.0,
    "nasal": 2.0,
    "lateral": 2.0,
    "approximant": 1.5,
    "tap": 1.5,
    "trill": 1.5,

    # Place
    "labial": 3.0,
    "labiodental": 3.0,
    "coronal": 3.0,
    "anterior": 3.0,
    "distributed": 3.0,
    "dorsal": 3.0,

    # Vowel space
    "high": 3.0,
    "low": 3.0,
    "front": 3.0,
    "back": 3.0,
    "round": 2.0,
    "tense": 2.0,

    # Laryngeal
    "periodicGlottalSource": 2.0,
    "spreadGlottis": 2.0,
    "constrictedGlottis": 2.0,

    # Other
    "delayedRelease": 1.0,
    "strident": 1.0,
    "retractedTongueRoot": 1.0,
    "advancedTongueRoot": 1.0,
    "fortis": 1.0,
    "lenis": 1.0,
    "raisedLarynxEjective": 1.0,
    "loweredLarynxImplosive": 1.0,
    "click": 1.0,
}

# Default weight for any feature not listed
DEFAULT_WEIGHT = 1.0

# -----------------------------
# 4. Weighted Manhattan distance
# -----------------------------
def confusion_distance(p1, p2):
    f1 = ENCODED[p1]
    f2 = ENCODED[p2]
    dist = 0.0

    for feat in f1:
        w = WEIGHTS.get(feat, DEFAULT_WEIGHT)
        dist += w * abs(f1[feat] - f2[feat])

    return dist

# -----------------------------
# 5. Compute full matrix
# -----------------------------
phonemes = sorted(ENCODED.keys())
matrix = []

for a in phonemes:
    row = []
    for b in phonemes:
        d = confusion_distance(a, b)
        row.append(d)
    matrix.append(row)

# -----------------------------
# 6. Write CSV
# -----------------------------
with open("phoneme_confusion_matrix.csv", "w", newline="", encoding="utf8") as f:
    writer = csv.writer(f)
    writer.writerow([""] + phonemes)
    for i, p in enumerate(phonemes):
        writer.writerow([p] + matrix[i])

print("Wrote phoneme_confusion_matrix.csv")
import json
import csv
import math

# -----------------------------
# 1. Load feature JSON
# -----------------------------
with open("phoneme_features.json", "r", encoding="utf8") as f:
    FEATURES = json.load(f)

# -----------------------------
# 2. Encode +, -, 0 → numeric
# -----------------------------
def encode_value(v):
    if v == "+":
        return 1
    if v == "-":
        return -1
    return 0

def encode_feature_vector(feat_dict):
    return {k: encode_value(v) for k, v in feat_dict.items() if k != "Source"}

ENCODED = {p: encode_feature_vector(f) for p, f in FEATURES.items()}

# -----------------------------
# 3. Perceptual weights (English listener)
# -----------------------------
WEIGHTS = {
    # Manner
    "consonantal": 2.0,
    "sonorant": 2.0,
    "continuant": 2.0,
    "nasal": 2.0,
    "lateral": 2.0,
    "approximant": 1.5,
    "tap": 1.5,
    "trill": 1.5,

    # Place
    "labial": 3.0,
    "labiodental": 3.0,
    "coronal": 3.0,
    "anterior": 3.0,
    "distributed": 3.0,
    "dorsal": 3.0,

    # Vowel space
    "high": 3.0,
    "low": 3.0,
    "front": 3.0,
    "back": 3.0,
    "round": 2.0,
    "tense": 2.0,

    # Laryngeal
    "periodicGlottalSource": 2.0,
    "spreadGlottis": 2.0,
    "constrictedGlottis": 2.0,

    # Other
    "delayedRelease": 1.0,
    "strident": 1.0,
    "retractedTongueRoot": 1.0,
    "advancedTongueRoot": 1.0,
    "fortis": 1.0,
    "lenis": 1.0,
    "raisedLarynxEjective": 1.0,
    "loweredLarynxImplosive": 1.0,
    "click": 1.0,
}

# Default weight for any feature not listed
DEFAULT_WEIGHT = 1.0

# -----------------------------
# 4. Weighted Manhattan distance
# -----------------------------
def confusion_distance(p1, p2):
    f1 = ENCODED[p1]
    f2 = ENCODED[p2]
    dist = 0.0

    for feat in f1:
        w = WEIGHTS.get(feat, DEFAULT_WEIGHT)
        dist += w * abs(f1[feat] - f2[feat])

    return dist

# -----------------------------
# 5. Compute full matrix
# -----------------------------
phonemes = sorted(ENCODED.keys())
matrix = []

for a in phonemes:
    row = []
    for b in phonemes:
        d = confusion_distance(a, b)
        row.append(d)
    matrix.append(row)

# -----------------------------
# 6. Write CSV
# -----------------------------
with open("phoneme_confusion_matrix.csv", "w", newline="", encoding="utf8") as f:
    writer = csv.writer(f)
    writer.writerow([""] + phonemes)
    for i, p in enumerate(phonemes):
        writer.writerow([p] + matrix[i])

print("Wrote phoneme_confusion_matrix.csv")
