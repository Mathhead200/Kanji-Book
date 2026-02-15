"""Generate word-cloud weight dictionaries for kanji and radicals.

Functions:
- word_cloud_for_kanji(kanji, ...)
    Returns dict: english_word -> accumulated_weight (float)
- word_cloud_for_radical(radical_key, ...)
    Aggregates per-kanji word clouds for the radical's kanji list.

Algorithm details / assumptions:
- Loads `data/word_cache.json` which maps each kanji literal to an entry:
    {"count": n, "words": [ {"word":..., "meanings": [...], "frequency": rank_or_null}, ... ]}
- `frequency` is treated as a *rank* (1 = most frequent). We apply Zipf weighting: weight = 1.0 / rank**s (default s=1.0).
- Words with `frequency` == null are omitted as requested.
- For each meaning string, we tokenize to English words (lowercased, punctuation removed) and exclude a small stopword list. Each occurrence contributes the weight.

Notes:
- The script loads `data/word_cache.json` into memory using json.load(). If you expect memory issues, we can change to a streaming approach (ijson) later.
"""
from __future__ import annotations
import json
import os
import re
from collections import defaultdict
from typing import Dict, List, Optional, Set
import unicodedata
from tokenizer import tokenize, ensure_nltk_resources, split_tokens

# Optional image generation using `wordcloud` (install with `pip install wordcloud pillow numpy`)
try:
    from wordcloud import WordCloud  # type: ignore
    WORDCLOUD_AVAILABLE = True
except Exception:
    WordCloud = None  # type: ignore
    WORDCLOUD_AVAILABLE = False

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
WORD_CACHE = os.path.join(ROOT, 'data', 'word_cache.json')
RADICAL_JSON = os.path.join(ROOT, 'data', 'radical_data.json')  # 'radical_data_1.json'
ELEMENT_STATS_JSON = os.path.join(ROOT, 'data', 'element_stats.json')


def _load_json(path: str):
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def _load_element_stats(path=ELEMENT_STATS_JSON):
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return {}


def _rank_to_weight(rank: int, exponent: float = 1.0) -> float:
    # Zipf weight: 1 / rank**exponent
    if rank is None:
        return 0.0
    try:
        r = float(rank)
        if r <= 0:
            return 0.0
        return 1.0 / (r ** exponent)
    except Exception:
        return 0.0


def _normalize_weights(weights: Dict[str, float]) -> Dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return weights
    return {k: (v / total) for k, v in weights.items()}


def get_top_n(weights: Dict[str, object], n: int = 20) -> List[tuple]:
    """Return the top-n items sorted by weight descending.

    If `n <= 0`, return all items sorted. Supports weight dicts where the value
    is either a float or a dict with a 'weight' key (the latter is used when
    `include_sources=True`).
    """
    def _get_weight(it):
        v = it[1]
        if isinstance(v, dict):
            return v.get('weight', 0.0)
        try:
            return float(v)
        except Exception:
            return 0.0

    items = sorted(weights.items(), key=lambda x: _get_weight(x), reverse=True)
    if n is None or n <= 0:
        return items
    return items[:n]


def _sanitize_filename(s: str) -> str:
    """Sanitize a string to be safe for filenames while preserving unicode chars."""
    # Remove path separators and control characters
    s = re.sub(r"[\\/\x00-\x1f]", "", s)
    # Replace spaces with underscore and trim length
    s = s.replace(' ', '_')
    return s[:120]

def _generate_text_file_path(args, prefix_label: str, kind: str = 'kanji', top_n: Optional[int] = None) -> str:
    """Generate a file path for text output given CLI args.

    Mirrors _generate_image_file_path behavior and appends a unicode codepoint
    suffix for single non-ASCII characters to avoid collisions.
    Returns empty string when no --out or --out-dir is provided.
    """
    sanitized = _sanitize_filename(prefix_label or "")
    codepoint_suffix = ""
    try:
        if isinstance(prefix_label, str) and len(prefix_label) == 1 and ord(prefix_label) > 0x7f:
            codepoint_suffix = f"_u{ord(prefix_label):x}"
    except Exception:
        codepoint_suffix = ""
    label = f"{sanitized}{codepoint_suffix}"

    # top label
    top_label = None
    if top_n is not None:
        try:
            tn = int(top_n)
            top_label = 'all' if tn <= 0 else str(tn)
        except Exception:
            tstr = str(top_n).lower()
            top_label = 'all' if tstr in ('all', 'a') else _sanitize_filename(str(top_n))

    # base filename
    if top_label:
        if kind == 'kanji':
            base = f"kanji_{label}_{top_label}.txt"
        elif kind == 'radical':
            base = f"radical_{label}_{top_label}.txt"
        elif kind == 'element':
            base = f"element_{label}_{top_label}.txt"
        else:
            base = f"{label}_{top_label}.txt"
    else:
        if kind == 'kanji':
            base = f"kanji_{label}.txt"
        elif kind == 'radical':
            base = f"radical_{label}.txt"
        elif kind == 'element':
            base = f"element_{label}.txt"
        else:
            base = f"{label}.txt"

    out = None
    if getattr(args, 'out', None) is not None:
        val = args.out
        if val == '.':
            out = os.path.join('.', base)
        else:
            root, ext = os.path.splitext(val)
            if ext:
                out = val
            elif os.path.isdir(val):
                out = os.path.join(val, base)
            else:
                out = val if val.lower().endswith('.txt') else val + '.txt'
    elif getattr(args, 'out_dir', None) is not None:
        val = args.out_dir
        if val == '.':
            out = os.path.join('.', base)
        else:
            out = os.path.join(val, base)
    else:
        return ''

    d = os.path.dirname(out) or '.'
    os.makedirs(d, exist_ok=True)
    return out


def _generate_image_file_path(args, prefix_label: str, kind: str = 'kanji', top_n: Optional[int] = None) -> str:
    """Generate a file path for the word cloud image given CLI args.

    `prefix_label` should be the kanji, radical, or element label (single char or short label).
    `kind` should be 'kanji', 'radical', or 'element' and controls the filename prefix.
    `top_n` when provided will be included as `_all` for non-positive values or `_<n>` for positive integers.
    Returns a full filepath (string). If neither image flag is present returns the empty string.
    """
    # sanitize the visible label
    sanitized = _sanitize_filename(prefix_label or "")
    # append a unicode codepoint suffix for single non-ASCII characters to avoid collisions
    codepoint_suffix = ""
    try:
        if isinstance(prefix_label, str) and len(prefix_label) == 1 and ord(prefix_label) > 0x7f:
            codepoint_suffix = f"_u{ord(prefix_label):x}"
    except Exception:
        codepoint_suffix = ""
    label = f"{sanitized}{codepoint_suffix}"

    # determine top label
    top_label = None
    if top_n is not None:
        try:
            tn = int(top_n)
            top_label = 'all' if tn <= 0 else str(tn)
        except Exception:
            tstr = str(top_n).lower()
            top_label = 'all' if tstr in ('all', 'a') else _sanitize_filename(str(top_n))

    # build base filename with explicit element kind support
    if top_label:
        if kind == 'kanji':
            base = f"kanji_{label}_{top_label}.png"
        elif kind == 'radical':
            base = f"radical_{label}_{top_label}.png"
        elif kind == 'element':
            base = f"element_{label}_{top_label}.png"
        else:
            base = f"{label}_{top_label}.png"
    else:
        if kind == 'kanji':
            base = f"kanji_{label}.png"
        elif kind == 'radical':
            base = f"radical_{label}.png"
        elif kind == 'element':
            base = f"element_{label}.png"
        else:
            base = f"{label}.png"

    # determine where to place it
    out = None
    if getattr(args, 'image_out', None) is not None:
        val = args.image_out
        if val == '.':
            out = os.path.join('.', base)
        else:
            root, ext = os.path.splitext(val)
            if ext:
                out = val
            elif os.path.isdir(val):
                out = os.path.join(val, base)
            else:
                out = val if val.lower().endswith('.png') else val + '.png'
    elif getattr(args, 'image_out_dir', None) is not None:
        val = args.image_out_dir
        if val == '.':
            out = os.path.join('.', base)
        else:
            out = os.path.join(val, base)
    else:
        return ''

    # ensure directory exists
    d = os.path.dirname(out) or '.'
    os.makedirs(d, exist_ok=True)
    return out


def _generate_and_save_wordcloud(weights: Dict[str, float], out_path: str, width: int = 1000, height: int = 600) -> None:
    """Generate and save a word cloud image from weights dict (token -> weight)."""
    try:
        from wordcloud import WordCloud
    except Exception:
        raise RuntimeError("Missing dependency 'wordcloud'. Install with `pip install wordcloud` to enable image output.")
    wc = WordCloud(width=width, height=height, background_color='white', prefer_horizontal=0.9)
    wc.generate_from_frequencies(weights)
    wc.to_file(out_path)



def word_cloud_for_kanji_with_cache(
    kanji: str,
    data: dict,
    stopwords: Optional[Set[str]] = None,
    zipf_exponent: float = 1.0,
    include_sources: bool = False,
) -> Dict[str, object]:
    """Like word_cloud_for_kanji but uses preloaded `data` mapping.

    When `include_sources=True`, the returned mapping is:
        token -> { 'weight': float, 'ja': [source_word_1, ...] }
    Otherwise it remains token -> float for backward compatibility.

    `data` is expected to be the parsed JSON of `word_cache.json`.
    """
    if kanji not in data:
        return {}
    entry = data[kanji]
    words = entry.get('words', [])

    weights: Dict[str, float] = defaultdict(float)
    sources: Dict[str, Set[str]] = defaultdict(set)

    # build known word set from meanings in this kanji to help split compounds
    known_words: Set[str] = set()
    for w in words:
        meanings = w.get('meanings', []) or []
        for m in meanings:
            if isinstance(m, dict):
                text = m.get('meaning') or ' '.join(str(v) for v in m.values())
            else:
                text = str(m)
            toks = tokenize(text, stopwords=stopwords)
            known_words.update(toks)

    for w in words:
        # ensure we have the single target kanji char for filtering
        target = kanji
        # normalize target once
        try:
            target_norm = unicodedata.normalize('NFKC', target)
        except Exception:
            target_norm = target

        for w in words:
            source_word = w.get('word') or ''
            # normalize source_word for robust containment checks
            try:
                src_norm = unicodedata.normalize('NFKC', str(source_word))
            except Exception:
                src_norm = str(source_word)

            # --- NEW: skip entries whose written form does not contain the kanji ---
            # If the source_word does not contain the target kanji, skip it.
            # This prevents kana-only words (e.g., "いらだつ") from contributing.
            if target_norm and target_norm not in src_norm:
                # Optionally: collect a small sample for diagnostics
                # skipped_examples.append((kanji, source_word))
                continue
            # ---------------------------------------------------------------------
            # existing logic: check frequency, compute weight, tokenize meanings...

        rank = w.get('frequency')
        if rank is None:
            continue
        try:
            rank_num = int(rank)
        except Exception:
            continue
        weight = _rank_to_weight(rank_num, exponent=zipf_exponent)
        meanings = w.get('meanings', []) or []
        source_word = w.get('word') or None
        # collect readings (new required format: 'readings': [ { 'kana':..., 'ipa':... }, ... ])
        readings_field = w.get('readings')
        if not isinstance(readings_field, list):
            raise ValueError(
                f"Unsupported data format in word_cache.json for kanji '{kanji}'.\n"
                f"Offending entry:\n{json.dumps(w, ensure_ascii=False, indent=2)}\n\n"
                f"Reason: expected 'readings' to be a list, but got: {type(readings_field).__name__}\n"
                f"This means at least one entry under this kanji is still in an old format."
            )
        readings = []
        for rr in readings_field:
            if isinstance(rr, dict):
                # prefer kana for readability, include ipa as well
                if rr.get('kana'):
                    readings.append(rr.get('kana'))
                if rr.get('ipa'):
                    readings.append(rr.get('ipa'))

        for m in meanings:
            if isinstance(m, dict):
                text = m.get('meaning') or ' '.join(str(v) for v in m.values())
            else:
                text = str(m)
            tokens = tokenize(text, stopwords=stopwords, split_compounds=True, known_words=known_words)
            for tok in tokens:
                weights[tok] += weight
                if include_sources:
                    if source_word:
                        sources[tok].add(source_word)
                    for rd in readings:
                        sources[tok].add(rd)
    # normalize so sum(weights) == 1.0
    normalized = _normalize_weights(weights)
    if not include_sources:
        return dict(normalized)
    # attach sources lists
    return {k: {'weight': v, 'ja': sorted(list(sources.get(k, [])))} for k, v in normalized.items()}

def word_cloud_for_kanji(
    kanji: str,
    word_cache_path: str = WORD_CACHE,
    stopwords: Optional[Set[str]] = None,
    zipf_exponent: float = 1.0,
    include_sources: bool = False,
) -> Dict[str, object]:
    """Return dict mapping English words -> accumulated weights for the given kanji.

    When `include_sources=True`, returns token -> { 'weight': float, 'ja': [...] }

    This helper loads the word cache for you (simple wrapper around the cached
    version above).
    """
    data = _load_json(word_cache_path)
    return word_cloud_for_kanji_with_cache(kanji, data, stopwords=stopwords, zipf_exponent=zipf_exponent, include_sources=include_sources)


def word_cloud_for_radical(
    radical_key: str,
    radical_json_path: str = RADICAL_JSON,
    word_cache_path: str = WORD_CACHE,
    stopwords: Optional[Set[str]] = None,
    zipf_exponent: float = 1.0,
    include_sources: bool = False,
) -> Dict[str, object]:
    """Aggregate word cloud for a radical by combining each associated kanji's cloud.

    When `include_sources=True` the returned mapping will be:
      token -> { 'weight': float, 'ja': [word_sources...] }
    """
    radical_data = _load_json(radical_json_path)
    entry = radical_data.get(str(radical_key))
    if not entry:
        # Try if radical_key is provided as character (find by radical_char)
        for k, v in radical_data.items():
            if v.get('radical_char') == radical_key:
                entry = v
                break
    if not entry:
        return {}

    kanji_list = entry.get('kanji', [])
    # load cache once for speed
    data = _load_json(word_cache_path)
    # build a global known words set to improve compound splitting across kanji
    global_known: Set[str] = set()
    for v in data.values():
        for w in v.get('words', []) :
            meanings = w.get('meanings', []) or []
            for m in meanings:
                if isinstance(m, dict):
                    text = m.get('meaning') or ' '.join(str(vv) for vv in m.values())
                else:
                    text = str(m)
                toks = tokenize(text, stopwords=stopwords)
                global_known.update(toks)

    agg_weights: Dict[str, float] = defaultdict(float)
    agg_sources: Dict[str, Set[str]] = defaultdict(set)
    for k in kanji_list:
        # request sources when aggregating so we can merge them
        kc = word_cloud_for_kanji_with_cache(k, data, stopwords=stopwords, zipf_exponent=zipf_exponent, include_sources=include_sources)
        for tok, val in kc.items():
            if include_sources:
                # val is dict {weight, ja}
                wt = val.get('weight', 0.0) if isinstance(val, dict) else 0.0
                srcs = val.get('ja', []) if isinstance(val, dict) else []
            else:
                wt = val if isinstance(val, (int, float)) else 0.0
                srcs = []
            parts = split_tokens([tok], global_known)
            if len(parts) == 1:
                agg_weights[tok] += wt
                for s in srcs:
                    agg_sources[tok].add(s)
            else:
                for p in parts:
                    agg_weights[p] += wt
                    for s in srcs:
                        agg_sources[p].add(s)
    # normalize aggregated weights
    agg_norm = _normalize_weights(agg_weights)
    if not include_sources:
        return dict(agg_norm)
    return {k: {'weight': v, 'ja': sorted(list(agg_sources.get(k, [])))} for k, v in agg_norm.items()}


def word_cloud_for_element(
    element_key: str,
    element_stats_path: str = ELEMENT_STATS_JSON,
    word_cache_path: str = WORD_CACHE,
    stopwords: Optional[Set[str]] = None,
    zipf_exponent: float = 1.0,
    include_sources: bool = False,
) -> Dict[str, object]:
    """
    Aggregate word cloud for an element (KanjiVG element key or character).
    Uses element_stats.json -> 'kanji_list' to find member kanji.
    """
    element_stats = _load_element_stats(element_stats_path)
    entry = element_stats.get(str(element_key))
    if not entry:
        # try searching by element char in case keys differ
        for k, v in element_stats.items():
            if k == element_key or v.get('element') == element_key:
                entry = v
                break
    if not entry:
        return {}

    kanji_list = entry.get('kanji_list') or entry.get('kanji', []) or []
    if not kanji_list:
        return {}

    # reuse the same cache-loading and aggregation approach as word_cloud_for_radical
    data = _load_json(word_cache_path)
    # build a global known words set to improve compound splitting across kanji
    global_known: Set[str] = set()
    for v in data.values():
        for w in v.get('words', []) :
            meanings = w.get('meanings', []) or []
            for m in meanings:
                if isinstance(m, dict):
                    text = m.get('meaning') or ' '.join(str(vv) for vv in m.values())
                else:
                    text = str(m)
                toks = tokenize(text, stopwords=stopwords)
                global_known.update(toks)

    agg_weights: Dict[str, float] = defaultdict(float)
    agg_sources: Dict[str, Set[str]] = defaultdict(set)
    for k in kanji_list:
        kc = word_cloud_for_kanji_with_cache(k, data, stopwords=stopwords, zipf_exponent=zipf_exponent, include_sources=include_sources)
        for tok, val in kc.items():
            if include_sources:
                wt = val.get('weight', 0.0) if isinstance(val, dict) else 0.0
                srcs = val.get('ja', []) if isinstance(val, dict) else []
            else:
                wt = val if isinstance(val, (int, float)) else 0.0
                srcs = []
            parts = split_tokens([tok], global_known)
            if len(parts) == 1:
                agg_weights[tok] += wt
                for s in srcs:
                    agg_sources[tok].add(s)
            else:
                for p in parts:
                    agg_weights[p] += wt
                    for s in srcs:
                        agg_sources[p].add(s)
    agg_norm = _normalize_weights(agg_weights)
    if not include_sources:
        return dict(agg_norm)
    return {k: {'weight': v, 'ja': sorted(list(agg_sources.get(k, [])))} for k, v in agg_norm.items()}


# CLI convenience
if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--kanji', help='Generate word cloud for a kanji')
    group.add_argument('--radical', help='Generate word cloud for a radical (number or char)')
    group.add_argument('--element', help='Generate word cloud for a KanjiVG element (key or character)')
    p.add_argument('--top', default='40', help='Show top N words (int), or "all" / -1 for all')
    p.add_argument('--zipf-exponent', type=float, default=1.0, help='Zipf exponent (default 1.0)')
    p.add_argument('--include-sources', action='store_true', help='Include source words for each token in output')

    # Image output: --image-out accepts optional filename (or flag alone to write into '.')
    # Text output: --out accepts optional filename (or flag alone to write into '.')
    p.add_argument('--out', nargs='?', const='.', help='Write top tokens to FILE (TXT). If provided without value, defaults to current directory ".".')
    p.add_argument('--out-dir', nargs='?', const='.', help='Write top tokens into DIR (create if missing). If provided without value defaults to current directory "."')
    p.add_argument('--image-out', nargs='?', const='.', help='Write wordcloud image to FILE (PNG). If provided without value, defaults to current directory ".". Requires `wordcloud` package.')
    p.add_argument('--image-out-dir', nargs='?', const='.', help='Write wordcloud image into DIR (create if missing). If provided without value defaults to current directory "."')
    p.add_argument('--image-width', type=int, default=800, help='Image width in pixels')
    p.add_argument('--image-height', type=int, default=400, help='Image height in pixels')
    p.add_argument('--bg-color', default='white', help='Background color for image')
    p.add_argument('--ensure-nltk', action='store_true', help='Download NLTK wordnet resources once and exit')
    args = p.parse_args()

    # parse top argument (allow 'all' or -1 for all)
    try:
        if isinstance(args.top, str) and args.top.lower() in ('all', 'a'):
            top_n = -1
        else:
            top_n = int(args.top)
    except Exception:
        print('Invalid --top value; please provide integer or "all"')
        raise SystemExit(2)

    # ensure NLTK resources once and exit if requested
    if getattr(args, 'ensure_nltk', False):
        ok = ensure_nltk_resources()
        if ok:
            print('NLTK wordnet resources are available (or were downloaded).')
            raise SystemExit(0)
        else:
            print('Failed to ensure NLTK resources. Please install `nltk` and run again or use `pip install nltk`.')
            raise SystemExit(2)

    if args.kanji:
        res = word_cloud_for_kanji(args.kanji, zipf_exponent=args.zipf_exponent, include_sources=args.include_sources)
        label_for_image = args.kanji
    elif args.element:
        res = word_cloud_for_element(args.element, zipf_exponent=args.zipf_exponent, include_sources=args.include_sources)
        label_for_image = args.element
    else:
        res = word_cloud_for_radical(args.radical, zipf_exponent=args.zipf_exponent, include_sources=args.include_sources)
        # resolve radical label: if numeric, find corresponding radical_char
        label_for_image = args.radical
        try:
            rd = _load_json(RADICAL_JSON)
            if str(args.radical).isdigit() and rd.get(str(args.radical)):
                rc = rd[str(args.radical)].get('radical_char')
                if rc:
                    label_for_image = rc
        except Exception:
            pass

    # print results (top or all)
    top_list = get_top_n(res, top_n)

    # Determine kind (same logic used for images)
    if getattr(args, 'kanji', None):
        kind = 'kanji'
    elif getattr(args, 'radical', None):
        kind = 'radical'
    elif getattr(args, 'element', None):
        kind = 'element'
    else:
        kind = 'kanji'

    # Prepare a safe label (append codepoint for single CJK char)
    label_for_file = label_for_image
    if isinstance(label_for_file, str) and len(label_for_file) == 1 and ord(label_for_file) > 0x7f:
        label_for_file = f"{label_for_file}_u{ord(label_for_file):x}"

    # Generate text file path (if requested)
    text_out_path = _generate_text_file_path(args, label_for_file, kind=kind, top_n=top_n)
    if text_out_path:
        try:
            with open(text_out_path, 'w', encoding='utf-8') as fh:
                # header: show 'all' when top_n is None or <= 0
                top_label = 'all' if (top_n is None or top_n <= 0) else str(top_n)
                fh.write(f"# word cloud top {top_label} for {kind} {label_for_image}\n")
                fh.write("# token\tweight\t(optional sources)\n")
                for w, v in top_list:
                    if args.include_sources and isinstance(v, dict):
                        weight = float(v.get('weight', 0.0))
                        sources = v.get('ja', [])
                        # keep only kanji sources for compactness
                        kanji_only = [s for s in sources if re.search(r'[\u4E00-\u9FFF]', s)]
                        # deduplicate while preserving order
                        kanji_only = list(dict.fromkeys(kanji_only))
                        src_str = ','.join(kanji_only[:20]) + (',...' if len(kanji_only) > 20 else '')
                        fh.write(f"{w}\t{weight:.6f}\t{src_str}\n")
                    else:
                        val = v['weight'] if isinstance(v, dict) else v
                        fh.write(f"{w}\t{float(val):.6f}\n")
            print(f"Wrote top tokens to {text_out_path}")
        except Exception as e:
            print(f"Failed to write text output: {e}", file=sys.stderr)
    else:
        # fallback: print to stdout (same format as before)
        for w, v in top_list:
            if args.include_sources and isinstance(v, dict):
                sources = v.get('ja', [])
                kanji_only = [s for s in sources if re.search(r'[\u4E00-\u9FFF]', s)]
                kanji_only = list(dict.fromkeys(kanji_only))
                ja_out = ','.join(kanji_only[:20]) + (',...' if len(kanji_only) > 20 else '')
                print(f"{w}\t{v['weight']:.6f}\t{ja_out}")
            else:
                val = v['weight'] if isinstance(v, dict) else v
                print(f"{w}\t{float(val):.6f}")

    # generate image if requested via --image-out or --image-out-dir
    if args.image_out is not None or args.image_out_dir is not None:
        def _v_to_weight(v):
            return v['weight'] if isinstance(v, dict) else float(v)
        if top_n is None or top_n <= 0:
            freq_items = list(res.items())
        else:
            freq_items = list(top_list)
        # Build a display-friendly frequency dict. Internal tokens may use underscores
        # for multi-word phrases (e.g., 'bumper_crop'); replace underscores with
        # spaces for nicer image labels and sum weights if multiple tokens collapse
        # to the same display label.
        from collections import defaultdict as _dd
        _display = _dd(float)
        for k, v in freq_items:
            w = _v_to_weight(v)
            lbl = k.replace('_', ' ')
            _display[lbl] += w
        freq_dict = dict(_display)

        try:
            kind = 'kanji' if args.kanji else 'radical' if args.radical else 'element' if args.element else None
            assert kind is not None, "Cannot determine kind for image filename"
            out_path = _generate_image_file_path(args, label_for_image, kind=kind, top_n=top_n)
            if not out_path:
                print('Image output requested but no valid path could be determined.')
            else:
                try:
                    _generate_and_save_wordcloud(freq_dict, out_path, width=args.image_width, height=args.image_height)
                    print(f"Wrote image to {out_path}")
                except RuntimeError as e:
                    print('Cannot create image —', e)
                except Exception as e:
                    print('Failed to generate image:', e)
        except Exception as e:
            print('Failed to determine image path or write image:', e)
