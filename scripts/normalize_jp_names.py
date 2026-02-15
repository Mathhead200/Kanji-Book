"""Normalize `jp_name` strings into structured arrays in data/radical_data.json

Transforms entries like:
  "jp_name": "にんにょう / ninnyō , ひとあし / hitoashi"
into:
  "jp_name": [ {"kana": "にんにょう", "romaji": "ninnyō"}, {"kana": "ひとあし", "romaji": "hitoashi"} ]

Usage:
    python scripts/normalize_jp_names.py [--apply]

Options:
    --apply    Actually write changes to `data/radical_data.json` (creates a backup).

This script performs only string parsing on current `jp_name` fields — it does not
query the web.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
from typing import Dict, List, Optional, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RADICAL_JSON = os.path.join(ROOT, 'data', 'radical_data.json')
BACKUP_FMT = os.path.join(ROOT, 'data', 'radical_data.json.bak.%s')

HIRAGANA_KATAKANA_RE = re.compile(r'[\u3040-\u30ff]')
ROMAJI_RE = re.compile(r'[A-Za-z]')


def split_top_level_commas(s: str) -> List[str]:
    parts: List[str] = []
    cur = []
    depth = 0
    for ch in s:
        if ch == '(':
            depth += 1
            cur.append(ch)
        elif ch == ')':
            depth = max(0, depth - 1)
            cur.append(ch)
        elif ch == ',' and depth == 0:
            part = ''.join(cur).strip()
            if part:
                parts.append(part)
            cur = []
        else:
            cur.append(ch)
    part = ''.join(cur).strip()
    if part:
        parts.append(part)
    return parts


def parse_tokens_from_text(text: str) -> List[Tuple[Optional[str], Optional[str]]]:
    # Split on slash separators
    tokens = [t.strip() for t in re.split(r'\s*/\s*', text) if t.strip()]
    pairs: List[Tuple[Optional[str], Optional[str]]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        # If token contains both kana and romaji separated by whitespace, split
        if HIRAGANA_KATAKANA_RE.search(tok) and ROMAJI_RE.search(tok):
            sp = tok.split()
            kana = sp[0]
            romaji = ' '.join(sp[1:]) if len(sp) > 1 else None
            pairs.append((kana or None, romaji or None))
            i += 1
            continue
        # classify token
        is_kana = bool(HIRAGANA_KATAKANA_RE.search(tok))
        is_romaji = bool(ROMAJI_RE.search(tok))
        if is_kana:
            # expect next token to be romaji
            if i + 1 < len(tokens) and ROMAJI_RE.search(tokens[i + 1]):
                pairs.append((tok, tokens[i + 1]))
                i += 2
            else:
                pairs.append((tok, None))
                i += 1
        elif is_romaji:
            # may be romaji that follows an un-paired kana
            if pairs and pairs[-1][1] is None:
                prev_kana = pairs[-1][0]
                pairs[-1] = (prev_kana, tok)
            else:
                pairs.append((None, tok))
            i += 1
        else:
            # neither kana nor romaji (fallback)
            sp = tok.split()
            if sp and HIRAGANA_KATAKANA_RE.search(sp[0]):
                kana = sp[0]
                romaji = ' '.join(sp[1:]) if len(sp) > 1 else None
                pairs.append((kana or None, romaji or None))
            else:
                # attach to previous if previous has kana but no romaji
                if pairs and pairs[-1][1] is None:
                    prev_kana = pairs[-1][0]
                    pairs[-1] = (prev_kana, tok)
                else:
                    pairs.append((tok, None))
            i += 1
    return pairs


def parse_jp_name_field(s: str) -> List[Dict[str, Optional[str]]]:
    # Split top-level by commas (not inside parentheses)
    parts = split_top_level_commas(s)
    results: List[Dict[str, Optional[str]]] = []
    for part in parts:
        # extract parenthesis content and main
        m = re.match(r'^(.*?)\s*(?:\((.*)\))?\s*$', part)
        if not m:
            continue
        main_text = m.group(1) or ''
        paren = m.group(2) or ''
        # parse main and parenthese content
        pairs = parse_tokens_from_text(main_text) if main_text.strip() else []
        if paren.strip():
            pairs += parse_tokens_from_text(paren)
        # convert pairs to dicts
        for kana, romaji in pairs:
            results.append({
                'kana': kana if kana is not None else None,
                'romaji': romaji if romaji is not None else None,
            })
    return results


def load_json(path: str) -> Dict[str, dict]:
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def write_json(path: str, data: Dict[str, dict]) -> None:
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)


def backup(path: str) -> str:
    ts = time.strftime('%Y%m%dT%H%M%S')
    bk = BACKUP_FMT % ts
    with open(path, 'rb') as src, open(bk, 'wb') as dst:
        dst.write(src.read())
    return bk


def run(dry_run: bool = True) -> int:
    data = load_json(RADICAL_JSON)
    changes = {}
    for key, entry in data.items():
        jp = entry.get('jp_name')
        if not jp or isinstance(jp, list):
            continue
        parsed = parse_jp_name_field(jp)
        # if parse result empty, leave as original string
        if parsed:
            changes[key] = parsed
    print(f'Parsed {len(changes)} jp_name fields into structured arrays.')
    sample_keys = sorted(list(changes.keys()), key=lambda x: int(x))[:10]
    for k in sample_keys:
        print(f'  radical {k}: {changes[k]}')
    if dry_run:
        print('\nDry run: no changes written. To apply, rerun with --apply')
        return 0
    # apply changes
    bk = backup(RADICAL_JSON)
    print('Backup saved to', bk)
    for key, parsed in changes.items():
        data[key]['jp_name'] = parsed
    write_json(RADICAL_JSON, data)
    print('Applied changes to', RADICAL_JSON)
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--apply', action='store_true', help='Apply changes')
    args = p.parse_args()
    return run(dry_run=not args.apply)


if __name__ == '__main__':
    sys.exit(main())
