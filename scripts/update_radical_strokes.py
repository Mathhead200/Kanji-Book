"""Update radical stroke counts in data/radical_data.json

This script fetches the Kangxi radicals table from Wikipedia and updates
`data/radical_data.json` by setting the `stroke_count` for each radical key.

Usage:
    python scripts/update_radical_strokes.py [--apply]

Options:
    --apply    Actually modify `data/radical_data.json`. Without it the script will
               perform a dry run and print proposed changes.

Dependencies:
    requests, beautifulsoup4
    pip install requests beautifulsoup4

Notes:
    - The script maps radicals by their Kangxi index (1..214), which should match
      the keys in `radical_data.json` (stored as strings).
    - It creates a timestamped backup of `data/radical_data.json` before applying
      changes.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from typing import Dict, Optional

try:
    import requests
    from bs4 import BeautifulSoup
except Exception as e:
    print("Missing dependency: run `pip install requests beautifulsoup4` and retry.")
    raise

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RADICAL_JSON = os.path.join(ROOT, 'data', 'radical_data.json')
BACKUP_FMT = os.path.join(ROOT, 'data', 'radical_data.json.bak.%s')
WIKI_URL = 'https://en.wikipedia.org/wiki/Kangxi_radicals'


def fetch_kangxi_table() -> Dict[int, int]:
    """Fetch Kangxi radicals table and return mapping number->stroke_count."""
    headers = {'User-Agent': 'kanji-vibes-stroke-updater/1.0 (https://github.com/)'}
    r = requests.get(WIKI_URL, timeout=30, headers=headers)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')

    # Find table that contains the radical list. The page contains multiple tables; pick the one
    # that has header cells like 'No' and 'Strokes' or 'Strokes' column.
    tables = soup.find_all('table')
    for tbl in tables:
        headers = [th.get_text(strip=True).lower() for th in tbl.find_all('th')]
        # Accept tables where first header contains 'No' and some header contains 'Stroke' or 'Strokes'
        if headers and (any(h.startswith('no') for h in headers) or any('radical' in h for h in headers)) and any('stroke' in h for h in headers):
            mapping: Dict[int, int] = {}
            for row in tbl.find_all('tr'):
                cells = row.find_all(['th', 'td'])
                if len(cells) < 3:
                    continue
                try:
                    num_text = cells[0].get_text(strip=True)
                    # remove non-digits
                    num = int(''.join(ch for ch in num_text if ch.isdigit()))
                    strokes_text = cells[2].get_text(strip=True)
                    strokes = int(''.join(ch for ch in strokes_text if ch.isdigit()))
                    mapping[num] = strokes
                except Exception:
                    # skip header or malformed rows
                    continue
            if mapping:
                return mapping

    raise RuntimeError('Could not find Kangxi radicals table on Wikipedia page')


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


def update_radicals(radical_json: Dict[str, dict], mapping: Dict[int, int], apply: bool = False) -> Dict[str, Optional[int]]:
    """Return dict of {radical_key: new_stroke_value or None if unchanged} and optionally apply changes."""
    changes: Dict[str, Optional[int]] = {}
    for key_str, entry in radical_json.items():
        try:
            k = int(key_str)
        except Exception:
            continue
        new = mapping.get(k)
        old = entry.get('stroke_count')
        if new is not None and old != new:
            changes[key_str] = new
            if apply:
                entry['stroke_count'] = new
        else:
            changes[key_str] = None
    return changes


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--apply', action='store_true', help='Apply changes to data file')
    p.add_argument('--show-missing', action='store_true', help='Show radicals missing from fetched mapping')
    args = p.parse_args()

    print('Fetching Kangxi radicals table from Wikipedia...')
    mapping = fetch_kangxi_table()
    print(f'Fetched {len(mapping)} radical stroke counts (sample: {list(mapping.items())[:5]})')

    print(f'Loading {RADICAL_JSON}...')
    radical_json = load_radical_json(RADICAL_JSON)

    changes = update_radicals(radical_json, mapping, apply=False)
    changed_items = {k: v for k, v in changes.items() if v is not None}
    print(f'Found {len(changed_items)} radicals that would be updated.')

    if args.apply:
        print('Creating backup...')
        bk = backup_file(RADICAL_JSON)
        print('Backup saved to', bk)
        # Apply and write
        update_radicals(radical_json, mapping, apply=True)
        write_radical_json(RADICAL_JSON, radical_json)
        print('Applied changes and wrote', RADICAL_JSON)
    else:
        # Dry run: print a few examples
        print('\nDry run (no file changes). To apply, rerun with --apply. Example updates:')
        for k in sorted(changed_items.keys(), key=lambda x: int(x))[:30]:
            print(f'  radical {k}: -> {changed_items[k]}')

    if args.show_missing:
        missing = [str(i) for i in range(1, 215) if i not in mapping]
        if missing:
            print('Missing radicals from fetched mapping:', ','.join(missing))
        else:
            print('No missing radicals in mapping.')

    return 0


if __name__ == '__main__':
    sys.exit(main())
