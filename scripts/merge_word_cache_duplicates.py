"""
Full migration script: normalize ALL word entries in data/word_cache.json
to the new format:

{
  "word": "...",
  "meanings": [...],
  "frequency": int or null,
  "readings": [ { "kana": "...", "ipa": "..." }, ... ]
}

This script:
- Converts old-format entries (with top-level 'kana'/'ipa') into new format
- Ensures 'readings' is always a list
- Merges duplicates (same word + same meanings)
- Normalizes frequency to int or None
"""

from __future__ import annotations
import json
import os
import shutil
import time
from typing import Dict, List, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
WORD_CACHE = os.path.join(ROOT, 'data', 'word_cache.json')


def normalize_readings(entry: dict) -> List[dict]:
    """Convert old-format kana/ipa fields into a readings list."""
    readings = []

    # Case 1: already correct
    if isinstance(entry.get("readings"), list):
        for r in entry["readings"]:
            if isinstance(r, dict):
                clean = {}
                if r.get("kana"):
                    clean["kana"] = r["kana"]
                if r.get("ipa"):
                    clean["ipa"] = r["ipa"]
                if clean:
                    readings.append(clean)
        return readings

    # Case 2: old format: top-level kana/ipa
    kana = entry.get("kana")
    ipa = entry.get("ipa")
    if kana or ipa:
        r = {}
        if kana:
            r["kana"] = kana
        if ipa:
            r["ipa"] = ipa
        readings.append(r)

    return readings


def normalize_frequency(entry: dict):
    """Ensure frequency is int or None."""
    freq = entry.get("frequency")
    if freq is None:
        return None
    try:
        return int(freq)
    except Exception:
        return None


def meaning_key(meanings: list) -> tuple:
    """Canonical key for duplicate detection."""
    out = []
    for m in meanings:
        if isinstance(m, dict):
            text = m.get("meaning") or " ".join(str(v) for v in m.values())
        else:
            text = str(m)
        out.append(text.strip().lower())
    return tuple(sorted(out))


def migrate_word_list(words: List[dict]) -> List[dict]:
    """Normalize all entries and merge duplicates."""
    grouped = {}

    for w in words:
        new_entry = {
            "word": w.get("word"),
            "meanings": w.get("meanings", []),
            "frequency": normalize_frequency(w),
        }

        # normalize readings
        readings = normalize_readings(w)
        new_entry["readings"] = readings

        # remove old fields
        for old in ("kana", "ipa"):
            if old in new_entry:
                del new_entry[old]

        key = (new_entry["word"], meaning_key(new_entry["meanings"]))

        if key not in grouped:
            grouped[key] = new_entry
        else:
            # merge readings
            existing = grouped[key]
            for r in readings:
                if r not in existing["readings"]:
                    existing["readings"].append(r)

            # merge frequency (take smallest rank)
            old_f = existing.get("frequency")
            new_f = new_entry.get("frequency")
            if new_f is not None:
                if old_f is None or new_f < old_f:
                    existing["frequency"] = new_f

    return list(grouped.values())


def migrate_word_cache(path: str = WORD_CACHE):
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    new_data = {}
    for kanji, entry in data.items():
        words = entry.get("words", [])
        migrated = migrate_word_list(words)
        new_entry = dict(entry)
        new_entry["words"] = migrated
        new_entry["count"] = len(migrated)
        new_data[kanji] = new_entry

    # backup
    bak = path + ".bak." + time.strftime("%Y%m%dT%H%M%S")
    shutil.copy2(path, bak)

    # write
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(new_data, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

    print("Migration complete.")
    print("Backup saved to:", bak)


if __name__ == "__main__":
    migrate_word_cache()