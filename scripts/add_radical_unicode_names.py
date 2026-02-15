"""Populate Unicode documentation names for radicals in data/radical_data.json

This script uses Python's `unicodedata.name()` to get the official Unicode name
for the radical character stored in each entry's `radical_char`. It adds a new
field `unicode_name` to each radical entry.

Usage:
    python scripts/add_radical_unicode_names.py [--apply]

Options:
    --apply    Actually modify `data/radical_data.json`. Without it the script
               performs a dry run and prints proposed changes.

Notes:
    - If `radical_char` is missing or name lookup fails, the script will try
      to compute the Kangxi radical code point using the radical number (U+2F00 + n - 1)
      and read its name as a fallback.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
import unicodedata
from typing import Dict, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RADICAL_JSON = os.path.join(ROOT, 'data', 'radical_data.json')
BACKUP_FMT = os.path.join(ROOT, 'data', 'radical_data.json.bak.%s')


def load_radical_json(path: str) -> Dict[str, dict]:
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def write_radical_json(path: str, data: Dict[str, dict]) -> None:
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)


def backup_file(path: str) -> str:
    ts = time.strftime('%Y%m%dT%H%M%S')
    bk = BACKUP_FMT % ts
    with open(path, 'rb') as src, open(bk, 'wb') as dst:
        dst.write(src.read())
    return bk


def get_unicode_name(char: Optional[str], radical_index: int) -> Optional[str]:
    if char:
        try:
            return unicodedata.name(char)
        except ValueError:
            pass
    # fallback: try Kangxi radical block U+2F00 + index - 1
    try:
        cp = 0x2F00 + (radical_index - 1)
        return unicodedata.name(chr(cp))
    except Exception:
        return None


def update_names(radical_json: Dict[str, dict], apply: bool = False) -> Dict[str, Optional[str]]:
    changes: Dict[str, Optional[str]] = {}
    for key_str, entry in radical_json.items():
        try:
            idx = int(key_str)
        except Exception:
            continue
        char = entry.get('radical_char')
        existing = entry.get('unicode_name')
        name = get_unicode_name(char, idx)
        if name and name != existing:
            changes[key_str] = name
            if apply:
                entry['unicode_name'] = name
        else:
            changes[key_str] = None
    return changes


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--apply', action='store_true', help='Apply changes to data file')
    args = p.parse_args()

    radical_json = load_radical_json(RADICAL_JSON)
    changes = update_names(radical_json, apply=False)
    changed_items = {k: v for k, v in changes.items() if v is not None}

    print(f'Found {len(changed_items)} radicals missing or with different unicode names.')
    print('Example updates:')
    for k in sorted(changed_items.keys(), key=lambda x: int(x))[:20]:
        print(f'  radical {k}: -> {changed_items[k]}')

    if args.apply:
        bk = backup_file(RADICAL_JSON)
        print('Backup saved to', bk)
        update_names(radical_json, apply=True)
        write_radical_json(RADICAL_JSON, radical_json)
        print('Applied changes to', RADICAL_JSON)
    else:
        print('\nDry run complete. To apply changes, rerun with --apply')

    return 0


if __name__ == '__main__':
    sys.exit(main())
