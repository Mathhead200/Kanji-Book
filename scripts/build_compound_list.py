#!/usr/bin/env python3
"""Build a compound-words mapping from WordNet (NLTK) and write it to JSON.

Usage:
    python scripts/build_compound_list.py --out data/compound_words.json

The script attempts to download the WordNet corpus automatically if needed.
"""
from __future__ import annotations
import argparse
import json
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DEFAULT_OUT = os.path.join(ROOT, 'data', 'compound_words.json')


def _ensure_wordnet():
    """Ensure WordNet is available, downloading it automatically if missing.

    This handles the common LookupError that occurs when the NLTK package is
    installed but the 'wordnet' corpus data hasn't been downloaded yet.
    """
    try:
        from nltk.corpus import wordnet as wn
    except Exception:
        try:
            import nltk
        except Exception:
            raise RuntimeError("NLTK is not installed. Install it with `pip install nltk` and try again.")
        print("NLTK installed but WordNet corpus missing; downloading 'wordnet' now...")
        nltk.download('wordnet', quiet=False)
        from nltk.corpus import wordnet as wn

    # Access a small iterator to trigger a LookupError if the corpus files are missing
    try:
        _ = next(wn.all_synsets(), None)
    except LookupError:
        import nltk
        print("WordNet resource not found; attempting to download 'wordnet' corpus...")
        nltk.download('wordnet', quiet=False)
    return wn


def build(min_part_len: int = 2, min_total_len: int = 6, max_entries: int | None = None):
    """Return a mapping: compact_compound -> [part1, part2, ...].

    - `min_part_len`: minimum length of each part
    - `min_total_len`: minimum length of concatenated compound
    - `max_entries`: limit number of entries (None = no limit)
    """
    wn = _ensure_wordnet()

    mapping: dict = {}
    for syn in wn.all_synsets():
        for lemma in syn.lemmas():
            name = lemma.name()
            # Look for multi-word lemmas (underscores or hyphens)
            if '_' in name or '-' in name:
                parts = re.split(r'[_\-]', name)
                parts = [p.lower() for p in parts if p.isalpha() and len(p) >= min_part_len]
                if len(parts) >= 2:
                    key = ''.join(parts)
                    if len(key) >= min_total_len and key not in mapping:
                        mapping[key] = parts
                        if max_entries is not None and len(mapping) >= max_entries:
                            return mapping
    return mapping


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', default=DEFAULT_OUT, help='Output JSON file path')
    p.add_argument('--min-part-len', type=int, default=2)
    p.add_argument('--min-total-len', type=int, default=6)
    p.add_argument('--max', type=int, default=0, help='Max entries to write (0 = all)')
    args = p.parse_args()

    max_entries = args.max if args.max > 0 else None
    mapping = build(min_part_len=args.min_part_len, min_total_len=args.min_total_len, max_entries=max_entries)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(mapping, fh, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Wrote {len(mapping)} compound entries to {args.out}")


if __name__ == '__main__':
    main()
