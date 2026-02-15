import json
import re
from pathlib import Path

# ---------------------------------------------------------
# 1. English IPA phoneme inventory (American English)
# ---------------------------------------------------------
# Order matters: multi-character phonemes must be matched first.
ENGLISH_PHONEMES = [
    # Affricates
    "tʃ", "dʒ",

    # Diphthongs
    "oʊ", "eɪ", "aɪ", "aʊ", "ɔɪ",

    # R-colored vowels
    "ɝ", "ɚ",

    # Vowels
    "i", "ɪ", "e", "ɛ", "æ", "ɑ", "ɔ", "o", "ʊ", "u",
    "ə", "ʌ",

    # Consonants
    "p", "b", "t", "d", "k", "ɡ",
    "f", "v", "θ", "ð", "s", "z", "ʃ", "ʒ", "h",
    "m", "n", "ŋ",
    "l", "ɫ", "ɹ", "j", "w",
]

# Sort by length (longest first) so digraphs match before single chars
ENGLISH_PHONEMES.sort(key=len, reverse=True)

# ---------------------------------------------------------
# 2. Normalize IPA string
# ---------------------------------------------------------

def normalize_ipa(ipa_raw):
    # Remove slashes
    ipa = ipa_raw.strip().strip("/")

    # Remove stress marks
    ipa = ipa.replace("ˈ", "").replace("ˌ", "")

    # Segment into phonemes
    segments = []
    i = 0
    while i < len(ipa):
        matched = False

        # Try to match multi-character phonemes first
        for ph in ENGLISH_PHONEMES:
            if ipa.startswith(ph, i):
                segments.append(ph)
                i += len(ph)
                matched = True
                break

        if matched:
            continue

        # If no phoneme matched, treat as single character fallback
        segments.append(ipa[i])
        i += 1

    # Join with dots
    return ".".join(segments)

# ---------------------------------------------------------
# 3. Load en_US.txt and build cache
# ---------------------------------------------------------

def build_english_ipa_cache(input_file="en_US.txt", output_file="english_ipa_cache.json"):
    cache = {}

    with open(input_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "\t" not in line:
                continue

            word, ipa_raw = line.split("\t", 1)

            # Some entries have multiple IPA variants separated by commas
            ipa_variants = [v.strip() for v in ipa_raw.split(",")]

            normalized_variants = [normalize_ipa(v) for v in ipa_variants]

            cache[word] = normalized_variants

    Path(output_file).write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Saved {len(cache)} English IPA entries to {output_file}")

# ---------------------------------------------------------
# 4. Run
# ---------------------------------------------------------

if __name__ == "__main__":
    build_english_ipa_cache()
