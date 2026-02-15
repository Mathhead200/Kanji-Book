"""Add simplified English name (`en_name`) and Japanese reading (`jp_name`) to radicals.

- `en_name` is derived from `unicode_name` by stripping common prefixes like
  'KANGXI RADICAL' or 'CJK RADICAL' and title-casing the remainder.
- `jp_name` is scraped from the Kangxi radicals table on Wikipedia (where
  available). The script falls back to None when not found.

Usage:
    python scripts/add_radical_enname_and_jp.py [--apply]

Notes:
    - The script is a best-effort scraper of the Wikipedia table; fields may
      differ slightly depending on how the table is formatted. It prints a
      sample of proposed updates in dry-run mode.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
from typing import Dict, Optional

try:
    import requests
    from bs4 import BeautifulSoup
except Exception:
    print("Missing dependency: run `pip install requests beautifulsoup4` and retry.")
    raise

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RADICAL_JSON = os.path.join(ROOT, 'data', 'radical_data.json')
BACKUP_FMT = os.path.join(ROOT, 'data', 'radical_data.json.bak.%s')
WIKI_URL = 'https://en.wikipedia.org/wiki/Kangxi_radicals'
HEADERS = {'User-Agent': 'kanji-vibes-radical-meta/1.0 (https://github.com/)'}

PREFIX_RE = re.compile(r'^(?:KANGXI|CJK(?: RADICAL)?)(?: RADICAL)?\s*', flags=re.I)


def clean_en_name(unicode_name: Optional[str]) -> Optional[str]:
    if not unicode_name:
        return None
    name = PREFIX_RE.sub('', unicode_name).strip()
    # Title case it for readability
    return name.title() if name else None


def fetch_wikipedia_jp_names() -> Dict[int, str]:
    r = requests.get(WIKI_URL, timeout=30, headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    tables = soup.find_all('table')
    debug_tables = []
    for idx, tbl in enumerate(tables):
        headers = [th.get_text(strip=True) for th in tbl.find_all('th')]
        if headers:
            debug_tables.append((idx, headers[:12]))
        headers_l = [h.lower() for h in headers]
        # Look for typical headers: No and something mentioning Japanese
        if (any(h.startswith('no') for h in headers_l) or any('radical' in h for h in headers_l)) and any('japan' in h or '日本' in h or 'kana' in h or 'japanese' in h or 'hiragana' in h or 'romaji' in h for h in headers_l):
            # find jp index (hiragana/romaji or other indicators)
            try:
                jp_idx = next(i for i, h in enumerate(headers_l) if any(tok in h for tok in ('japan','日本','kana','japanese','hiragana','romaji')))
            except StopIteration:
                continue

            mapping: Dict[int, str] = {}
            for row in tbl.find_all('tr'):
                cells = row.find_all(['th', 'td'])
                if not cells:
                    continue
                # robustly find radical number by scanning cells for digits
                num = None
                for c in cells:
                    txt = c.get_text(strip=True)
                    digits = ''.join(ch for ch in txt if ch.isdigit())
                    if digits:
                        try:
                            num = int(digits)
                            break
                        except Exception:
                            continue
                if num is None:
                    continue
                if jp_idx >= len(cells):
                    continue
                jp_text = cells[jp_idx].get_text(' ', strip=True)
                if jp_text:
                    jp_text = ' '.join(jp_text.split())
                    mapping[num] = jp_text
            if mapping:
                return mapping
    # debug output to help diagnosis
    print('DEBUG: no Japanese column found. Sample table headers:')
    for i, hdr in debug_tables[:10]:
        print(f'  table {i}: {hdr}')
    return {}


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


def update_metadata(radical_json: Dict[str, dict], jp_mapping: Dict[int, str], apply: bool = False) -> Dict[str, dict]:
    changes: Dict[str, dict] = {}
    for key_str, entry in radical_json.items():
        try:
            idx = int(key_str)
        except Exception:
            continue
        updated: Dict[str, Optional[str]] = {}
        unicode_name = entry.get('unicode_name')
        en_name = clean_en_name(unicode_name)
        if en_name and entry.get('en_name') != en_name:
            updated['en_name'] = en_name
            if apply:
                entry['en_name'] = en_name
        # jp name
        jp = jp_mapping.get(idx)
        if jp and entry.get('jp_name') != jp:
            updated['jp_name'] = jp
            if apply:
                entry['jp_name'] = jp
        if updated:
            changes[key_str] = updated
    return changes


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--apply', action='store_true', help='Apply changes to data file')
    args = p.parse_args()

    print('Fetching Japanese names from Wikipedia Kangxi radicals table...')
    jp_mapping = fetch_wikipedia_jp_names()
    print(f'Found {len(jp_mapping)} Japanese names on Wikipedia (sample: {list(jp_mapping.items())[:5]})')

    radical_json = load_radical_json(RADICAL_JSON)
    changes = update_metadata(radical_json, jp_mapping, apply=False)
    print(f'Would update {len(changes)} radicals (dry run). Example:')
    for k in sorted(changes.keys(), key=lambda x: int(x))[:20]:
        print(f'  radical {k}: {changes[k]}')

    if args.apply:
        bk = backup_file(RADICAL_JSON)
        print('Backup saved to', bk)
        update_metadata(radical_json, jp_mapping, apply=True)
        write_radical_json(RADICAL_JSON, radical_json)
        print('Applied changes to', RADICAL_JSON)
    else:
        print('\nDry run complete. To apply, rerun with --apply')
    return 0


if __name__ == '__main__':
    sys.exit(main())
