"""Generate semantic word-cloud weight dictionaries for kanji and radicals (v3).

Version 3 improvements:
- Dual weighting: Zipf (Japanese word frequency) × TF-IDF (English token rarity)
- Synonym grouping using WordNet synsets
- Enhanced tokenization with POS filtering and dictionary validation
- Configurable representative selection from synonym groups
- Detailed cluster reporting in output

Functions:
- word_cloud_for_kanji(kanji, ...) → dict: english_word -> weight/cluster_info
- word_cloud_for_radical(radical_key, ...) → aggregated word cloud
- word_cloud_for_element(element_key, ...) → aggregated word cloud
"""
from __future__ import annotations
import json
import math
import os
import re
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple
import unicodedata

# Import enhanced tokenizer
try:
    from tokenizer_v2 import tokenize, ensure_nltk_resources, split_tokens
except ImportError:
    print("Error: tokenizer_v2.py not found. Please ensure it's in the same directory.")
    sys.exit(1)

# Optional image generation
try:
    from wordcloud import WordCloud  # type: ignore
    WORDCLOUD_AVAILABLE = True
except Exception:
    WordCloud = None  # type: ignore
    WORDCLOUD_AVAILABLE = False

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
WORD_CACHE = os.path.join(ROOT, 'data', 'word_cache.json')
RADICAL_JSON = os.path.join(ROOT, 'data', 'radical_data.json')
ELEMENT_STATS_JSON = os.path.join(ROOT, 'data', 'element_stats.json')

# WordNet resources (lazy loaded)
_WORDNET = None
_WORDNET_TRIED = False

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
    """Convert frequency rank to Zipf weight: 1 / rank^exponent"""
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
    """Normalize weights to sum to 1.0"""
    total = sum(weights.values())
    if total <= 0:
        return weights
    return {k: (v / total) for k, v in weights.items()}

def _get_wordnet():
    """Lazily load NLTK WordNet."""
    global _WORDNET, _WORDNET_TRIED
    if _WORDNET is not None:
        return _WORDNET
    if _WORDNET_TRIED:
        return None
    _WORDNET_TRIED = True
    
    try:
        import nltk
        from nltk.corpus import wordnet
        try:
            wordnet.synsets('test')  # Test if loaded
        except LookupError:
            nltk.download('wordnet', quiet=True)
            nltk.download('omw-1.4', quiet=True)
        _WORDNET = wordnet
        return _WORDNET
    except Exception as e:
        print(f"Warning: Could not load WordNet: {e}")
        print("Synonym grouping will be disabled.")
        return None

def _calculate_idf_scores(all_kanji_tokens: Dict[str, Set[str]]) -> Dict[str, float]:
    """Calculate IDF scores for all tokens across the corpus.
    
    Args:
        all_kanji_tokens: Dict mapping kanji -> set of tokens found in that kanji
    
    Returns:
        Dict mapping token -> IDF score (log(total_docs / doc_freq))
    """
    if not all_kanji_tokens:
        return {}
    
    # Count document frequency for each token
    doc_freq: Dict[str, int] = defaultdict(int)
    for tokens in all_kanji_tokens.values():
        for token in tokens:
            doc_freq[token] += 1
    
    # Calculate IDF: log(total_documents / documents_containing_term)
    total_docs = len(all_kanji_tokens)
    idf_scores = {}
    for token, freq in doc_freq.items():
        idf_scores[token] = math.log(total_docs / freq)
    
    return idf_scores

def _apply_tfidf_weighting(
    token_weights: Dict[str, float],
    idf_scores: Dict[str, float]
) -> Dict[str, float]:
    """Apply TF-IDF weighting by multiplying existing weights by IDF scores.
    
    Args:
        token_weights: Dict of token -> weight (already has Zipf weighting)
        idf_scores: Dict of token -> IDF score
    
    Returns:
        Dict of token -> TF-IDF weighted score
    """
    tfidf_weights = {}
    for token, weight in token_weights.items():
        idf = idf_scores.get(token, 1.0)  # Default IDF of 1.0 if not found
        tfidf_weights[token] = weight * idf
    
    return tfidf_weights

def _group_tokens_by_synset(
    tokens: List[str]
) -> Dict[str, List[str]]:
    """Group tokens by their WordNet synsets.
    
    Returns a dict mapping synset_id -> list of tokens in that synset.
    Tokens not in WordNet are returned in individual groups.
    
    Args:
        tokens: List of tokens to group
    
    Returns:
        Dict of synset_key -> [tokens...]
    """
    wordnet = _get_wordnet()
    if wordnet is None:
        # No WordNet available - return each token as its own group
        return {f"solo_{t}": [t] for t in tokens}
    
    synset_groups: Dict[str, List[str]] = defaultdict(list)
    ungrouped_tokens = []
    
    for token in tokens:
        synsets = wordnet.synsets(token)
        if synsets:
            # Use the first (most common) synset
            synset_key = synsets[0].name()
            synset_groups[synset_key].append(token)
        else:
            # No synset found - treat as solo token
            ungrouped_tokens.append(token)
    
    # Add ungrouped tokens as individual groups
    for token in ungrouped_tokens:
        synset_groups[f"solo_{token}"].append(token)
    
    return dict(synset_groups)

def _select_synset_representatives(
    synset_groups: Dict[str, List[str]],
    token_weights: Dict[str, float],
    max_per_synset: int = 1
) -> Tuple[Dict[str, float], Dict[str, List[str]]]:
    """Select top N representatives from each synset group.
    
    Args:
        synset_groups: Dict of synset_key -> [tokens...]
        token_weights: Dict of token -> weight
        max_per_synset: Maximum representatives per synset (default 1)
    
    Returns:
        Tuple of:
        - Dict of representative_token -> combined_weight
        - Dict of representative_token -> [all_tokens_in_synset]
    """
    representatives = {}
    clusters = {}
    
    for synset_key, tokens in synset_groups.items():
        # Sort tokens by weight descending
        sorted_tokens = sorted(
            tokens,
            key=lambda t: token_weights.get(t, 0.0),
            reverse=True
        )
        
        # Take top N representatives
        reps = sorted_tokens[:max_per_synset]
        
        # Sum weights for all tokens in synset
        total_weight = sum(token_weights.get(t, 0.0) for t in tokens)
        
        # Assign combined weight to representative(s)
        weight_per_rep = total_weight / len(reps) if reps else 0.0
        
        for rep in reps:
            representatives[rep] = weight_per_rep
            clusters[rep] = sorted_tokens  # Store full cluster
    
    return representatives, clusters

def get_top_n(weights: Dict[str, object], n: int = 20) -> List[tuple]:
    """Return the top-n items sorted by weight descending."""
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
    """Sanitize string for use in filenames."""
    s = re.sub(r"[\\/\x00-\x1f]", "", s)
    s = s.replace(' ', '_')
    return s[:120]

def _generate_text_file_path(args, prefix_label: str, kind: str = 'kanji', top_n: Optional[int] = None) -> str:
    """Generate output file path for text results."""
    sanitized = _sanitize_filename(prefix_label or "")
    codepoint_suffix = ""
    try:
        if isinstance(prefix_label, str) and len(prefix_label) == 1 and ord(prefix_label) > 0x7f:
            codepoint_suffix = f"_u{ord(prefix_label):x}"
    except Exception:
        codepoint_suffix = ""
    label = f"{sanitized}{codepoint_suffix}"
    
    top_label = None
    if top_n is not None:
        try:
            tn = int(top_n)
            top_label = 'all' if tn <= 0 else str(tn)
        except Exception:
            tstr = str(top_n).lower()
            top_label = 'all' if tstr in ('all', 'a') else _sanitize_filename(str(top_n))
    
    if top_label:
        base = f"{kind}_{label}_{top_label}.txt"
    else:
        base = f"{kind}_{label}.txt"
    
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
    """Generate output file path for word cloud image."""
    sanitized = _sanitize_filename(prefix_label or "")
    codepoint_suffix = ""
    try:
        if isinstance(prefix_label, str) and len(prefix_label) == 1 and ord(prefix_label) > 0x7f:
            codepoint_suffix = f"_u{ord(prefix_label):x}"
    except Exception:
        pass
    label = f"{sanitized}{codepoint_suffix}"
    
    top_label = None
    if top_n is not None:
        try:
            tn = int(top_n)
            top_label = 'all' if tn <= 0 else str(tn)
        except Exception:
            top_label = 'all'
    
    if top_label:
        base = f"{kind}_{label}_{top_label}.png"
    else:
        base = f"{kind}_{label}.png"
    
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
    
    d = os.path.dirname(out) or '.'
    os.makedirs(d, exist_ok=True)
    return out

def _generate_and_save_wordcloud(freq_dict: Dict[str, float], output_path: str, width: int = 800, height: int = 400, background_color: str = 'white') -> None:
    """Generate and save word cloud image."""
    if not WORDCLOUD_AVAILABLE:
        raise RuntimeError("wordcloud package not installed. Install with: pip install wordcloud pillow numpy")
    
    if not freq_dict:
        raise RuntimeError("No words to generate cloud from")
    
    wc = WordCloud(
        width=width,
        height=height,
        background_color=background_color,
        relative_scaling=0.5,
        min_font_size=8
    ).generate_from_frequencies(freq_dict)
    
    wc.to_file(output_path)

def word_cloud_for_kanji_with_cache(
    kanji: str,
    data: dict,
    stopwords: Optional[Set[str]] = None,
    zipf_exponent: float = 1.0,
    include_sources: bool = False,
    pos_filter: bool = True,
    dict_validate: bool = True,
    dictionary_path: Optional[str] = None,
    min_token_length: int = 3,
) -> Dict[str, object]:
    """Generate word cloud for a single kanji using cached word data.
    
    This version uses enhanced tokenization with POS filtering and
    dictionary validation. Returns raw token weights (not yet TF-IDF weighted).
    
    Args:
        kanji: The kanji character
        data: Pre-loaded word_cache.json data
        stopwords: Words to exclude
        zipf_exponent: Exponent for Zipf weighting
        include_sources: Whether to track source Japanese words
        pos_filter: Apply POS filtering
        dict_validate: Validate against English dictionary
        dictionary_path: Optional custom dictionary
        min_token_length: Minimum token length
    
    Returns:
        Dict of token -> weight (or -> {weight, ja} if include_sources=True)
    """
    entry = data.get(kanji)
    if not entry:
        return {}
    
    words = entry.get('words', [])
    if not words:
        return {}
    
    # Build known_words set for compound splitting
    known_words: Set[str] = set()
    for w in words:
        meanings = w.get('meanings', []) or []
        for m in meanings:
            if isinstance(m, dict):
                text = m.get('meaning') or ''
            else:
                text = str(m)
            toks = tokenize(
                text,
                stopwords=stopwords,
                pos_filter=False,  # Don't filter yet, just collect
                dict_validate=False,
                min_length=2
            )
            known_words.update(toks)
    
    weights: Dict[str, float] = defaultdict(float)
    sources: Dict[str, Set[str]] = defaultdict(set)
    
    for w in words:
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
        
        # Collect readings
        readings_field = w.get('readings')
        if not isinstance(readings_field, list):
            raise ValueError(
                f"Unsupported data format in word_cache.json for kanji '{kanji}'.\n"
                f"Expected 'readings' to be a list, got: {type(readings_field).__name__}"
            )
        
        readings = []
        for rr in readings_field:
            if isinstance(rr, dict):
                if rr.get('kana'):
                    readings.append(rr.get('kana'))
                if rr.get('ipa'):
                    readings.append(rr.get('ipa'))
        
        for m in meanings:
            if isinstance(m, dict):
                text = m.get('meaning') or ' '.join(str(v) for v in m.values())
            else:
                text = str(m)
            
            tokens = tokenize(
                text,
                stopwords=stopwords,
                split_compounds=True,
                known_words=known_words,
                pos_filter=pos_filter,
                dict_validate=dict_validate,
                dictionary_path=dictionary_path,
                min_length=min_token_length
            )
            
            for tok in tokens:
                weights[tok] += weight
                if include_sources:
                    if source_word:
                        sources[tok].add(source_word)
                    for rd in readings:
                        sources[tok].add(rd)
    
    # Normalize weights
    normalized = _normalize_weights(weights)
    
    if not include_sources:
        return dict(normalized)
    
    return {k: {'weight': v, 'ja': sorted(list(sources.get(k, [])))} for k, v in normalized.items()}

def word_cloud_for_kanji(
    kanji: str,
    word_cache_path: str = WORD_CACHE,
    stopwords: Optional[Set[str]] = None,
    zipf_exponent: float = 1.0,
    include_sources: bool = False,
    pos_filter: bool = True,
    dict_validate: bool = True,
    dictionary_path: Optional[str] = None,
    min_token_length: int = 3,
) -> Dict[str, object]:
    """Generate word cloud for a kanji (loads cache internally)."""
    data = _load_json(word_cache_path)
    return word_cloud_for_kanji_with_cache(
        kanji, data,
        stopwords=stopwords,
        zipf_exponent=zipf_exponent,
        include_sources=include_sources,
        pos_filter=pos_filter,
        dict_validate=dict_validate,
        dictionary_path=dictionary_path,
        min_token_length=min_token_length
    )

def word_cloud_for_element(
    element_key: str,
    element_stats_path: str = ELEMENT_STATS_JSON,
    word_cache_path: str = WORD_CACHE,
    stopwords: Optional[Set[str]] = None,
    zipf_exponent: float = 1.0,
    include_sources: bool = False,
    apply_tfidf: bool = True,
    group_synonyms: bool = True,
    max_synonyms: int = 1,
    pos_filter: bool = True,
    dict_validate: bool = True,
    dictionary_path: Optional[str] = None,
    min_token_length: int = 3,
) -> Dict[str, object]:
    """Generate word cloud for a KanjiVG element with TF-IDF and synonym grouping.
    
    Args:
        element_key: Element identifier (key or character)
        element_stats_path: Path to element_stats.json
        word_cache_path: Path to word_cache.json
        stopwords: Words to exclude
        zipf_exponent: Zipf weighting exponent
        include_sources: Track source Japanese words
        apply_tfidf: Apply TF-IDF weighting
        group_synonyms: Group by WordNet synsets
        max_synonyms: Max representatives per synset
        pos_filter: Apply POS filtering
        dict_validate: Dictionary validation
        dictionary_path: Custom dictionary path
        min_token_length: Minimum token length
    
    Returns:
        Dict of token -> weight/cluster_info
    """
    stats = _load_element_stats(element_stats_path)
    data = _load_json(word_cache_path)
    
    # Find kanji list for this element
    kanji_list = []
    for k, v in stats.items():
        if element_key in (k, v.get('element_char')):
            kanji_list = v.get('kanji', [])
            break
    
    if not kanji_list:
        return {}
    
    # Build global known words set
    global_known: Set[str] = set()
    for k in kanji_list:
        entry = data.get(k)
        if not entry:
            continue
        words = entry.get('words', [])
        for w in words:
            meanings = w.get('meanings', []) or []
            for m in meanings:
                if isinstance(m, dict):
                    text = m.get('meaning') or ''
                else:
                    text = str(m)
                toks = tokenize(text, stopwords=stopwords, pos_filter=False, dict_validate=False, min_length=2)
                global_known.update(toks)
    
    # Aggregate weights and collect tokens per kanji (for IDF calculation)
    agg_weights: Dict[str, float] = defaultdict(float)
    agg_sources: Dict[str, Set[str]] = defaultdict(set)
    kanji_tokens: Dict[str, Set[str]] = {}  # For TF-IDF
    
    for k in kanji_list:
        kc = word_cloud_for_kanji_with_cache(
            k, data,
            stopwords=stopwords,
            zipf_exponent=zipf_exponent,
            include_sources=include_sources,
            pos_filter=pos_filter,
            dict_validate=dict_validate,
            dictionary_path=dictionary_path,
            min_token_length=min_token_length
        )
        
        # Track tokens for this kanji (for IDF)
        kanji_tokens[k] = set(kc.keys())
        
        for tok, val in kc.items():
            if include_sources:
                wt = val.get('weight', 0.0) if isinstance(val, dict) else 0.0
                srcs = val.get('ja', []) if isinstance(val, dict) else []
            else:
                wt = val if isinstance(val, (int, float)) else 0.0
                srcs = []
            
            # Apply compound splitting at aggregation level
            parts = split_tokens(
                [tok], global_known,
                pos_filter=pos_filter,
                dict_validate=dict_validate,
                dictionary_path=dictionary_path,
                min_length=min_token_length
            )
            
            if len(parts) == 1:
                agg_weights[tok] += wt
                for s in srcs:
                    agg_sources[tok].add(s)
            else:
                for p in parts:
                    agg_weights[p] += wt
                    for s in srcs:
                        agg_sources[p].add(s)
    
    # Apply TF-IDF if requested
    if apply_tfidf:
        idf_scores = _calculate_idf_scores(kanji_tokens)
        agg_weights = _apply_tfidf_weighting(agg_weights, idf_scores)
    
    # Normalize after TF-IDF
    agg_norm = _normalize_weights(agg_weights)
    
    # Group synonyms if requested
    if group_synonyms:
        synset_groups = _group_tokens_by_synset(list(agg_norm.keys()))
        representatives, clusters = _select_synset_representatives(
            synset_groups, agg_norm, max_per_synset=max_synonyms
        )
        
        # Build output with cluster information
        if not include_sources:
            return {
                rep: {
                    'weight': weight,
                    'cluster': clusters[rep]
                }
                for rep, weight in representatives.items()
            }
        else:
            return {
                rep: {
                    'weight': weight,
                    'cluster': clusters[rep],
                    'ja': sorted(list(set().union(*[agg_sources.get(t, set()) for t in clusters[rep]])))
                }
                for rep, weight in representatives.items()
            }
    
    # No synonym grouping - return as-is
    if not include_sources:
        return dict(agg_norm)
    return {k: {'weight': v, 'ja': sorted(list(agg_sources.get(k, [])))} for k, v in agg_norm.items()}

def word_cloud_for_radical(
    radical_key: str,
    radical_json_path: str = RADICAL_JSON,
    word_cache_path: str = WORD_CACHE,
    stopwords: Optional[Set[str]] = None,
    zipf_exponent: float = 1.0,
    include_sources: bool = False,
    apply_tfidf: bool = True,
    group_synonyms: bool = True,
    max_synonyms: int = 1,
    pos_filter: bool = True,
    dict_validate: bool = True,
    dictionary_path: Optional[str] = None,
    min_token_length: int = 3,
) -> Dict[str, object]:
    """Generate word cloud for a radical with TF-IDF and synonym grouping."""
    rd = _load_json(radical_json_path)
    data = _load_json(word_cache_path)
    
    # Find kanji list for this radical
    radical_entry = rd.get(str(radical_key))
    if not radical_entry:
        # Try searching by radical_char
        for k, v in rd.items():
            if v.get('radical_char') == radical_key:
                radical_entry = v
                break
    
    if not radical_entry:
        return {}
    
    kanji_list = radical_entry.get('kanji', [])
    if not kanji_list:
        return {}
    
    # Build global known words
    global_known: Set[str] = set()
    for k in kanji_list:
        entry = data.get(k)
        if not entry:
            continue
        words = entry.get('words', [])
        for w in words:
            meanings = w.get('meanings', []) or []
            for m in meanings:
                if isinstance(m, dict):
                    text = m.get('meaning') or ''
                else:
                    text = str(m)
                toks = tokenize(text, stopwords=stopwords, pos_filter=False, dict_validate=False, min_length=2)
                global_known.update(toks)
    
    # Aggregate
    agg_weights: Dict[str, float] = defaultdict(float)
    agg_sources: Dict[str, Set[str]] = defaultdict(set)
    kanji_tokens: Dict[str, Set[str]] = {}
    
    for k in kanji_list:
        kc = word_cloud_for_kanji_with_cache(
            k, data,
            stopwords=stopwords,
            zipf_exponent=zipf_exponent,
            include_sources=include_sources,
            pos_filter=pos_filter,
            dict_validate=dict_validate,
            dictionary_path=dictionary_path,
            min_token_length=min_token_length
        )
        
        kanji_tokens[k] = set(kc.keys())
        
        for tok, val in kc.items():
            if include_sources:
                wt = val.get('weight', 0.0) if isinstance(val, dict) else 0.0
                srcs = val.get('ja', []) if isinstance(val, dict) else []
            else:
                wt = val if isinstance(val, (int, float)) else 0.0
                srcs = []
            
            parts = split_tokens(
                [tok], global_known,
                pos_filter=pos_filter,
                dict_validate=dict_validate,
                dictionary_path=dictionary_path,
                min_length=min_token_length
            )
            
            if len(parts) == 1:
                agg_weights[tok] += wt
                for s in srcs:
                    agg_sources[tok].add(s)
            else:
                for p in parts:
                    agg_weights[p] += wt
                    for s in srcs:
                        agg_sources[p].add(s)
    
    # TF-IDF
    if apply_tfidf:
        idf_scores = _calculate_idf_scores(kanji_tokens)
        agg_weights = _apply_tfidf_weighting(agg_weights, idf_scores)
    
    agg_norm = _normalize_weights(agg_weights)
    
    # Synonym grouping
    if group_synonyms:
        synset_groups = _group_tokens_by_synset(list(agg_norm.keys()))
        representatives, clusters = _select_synset_representatives(
            synset_groups, agg_norm, max_per_synset=max_synonyms
        )
        
        if not include_sources:
            return {
                rep: {
                    'weight': weight,
                    'cluster': clusters[rep]
                }
                for rep, weight in representatives.items()
            }
        else:
            return {
                rep: {
                    'weight': weight,
                    'cluster': clusters[rep],
                    'ja': sorted(list(set().union(*[agg_sources.get(t, set()) for t in clusters[rep]])))
                }
                for rep, weight in representatives.items()
            }
    
    if not include_sources:
        return dict(agg_norm)
    return {k: {'weight': v, 'ja': sorted(list(agg_sources.get(k, [])))} for k, v in agg_norm.items()}

# CLI
if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description='Generate semantic word clouds for kanji/radicals/elements')
    
    # Input selection
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--kanji', help='Generate word cloud for a kanji')
    group.add_argument('--radical', help='Generate word cloud for a radical (number or char)')
    group.add_argument('--element', help='Generate word cloud for a KanjiVG element')
    
    # Weighting options
    p.add_argument('--zipf-exponent', type=float, default=1.0, help='Zipf exponent for Japanese word frequency (default 1.0)')
    p.add_argument('--no-tfidf', action='store_true', help='Disable TF-IDF weighting (use Zipf only)')
    
    # Synonym grouping
    p.add_argument('--no-synonyms', action='store_true', help='Disable synonym grouping')
    p.add_argument('--max-synonyms', type=int, default=1, help='Max representatives per synset (default 1)')
    
    # Tokenization options
    p.add_argument('--no-pos-filter', action='store_true', help='Disable POS filtering')
    p.add_argument('--no-dict-validate', action='store_true', help='Disable dictionary validation')
    p.add_argument('--dictionary', help='Path to custom English word list')
    p.add_argument('--min-length', type=int, default=3, help='Minimum token length (default 3)')
    
    # Output options
    p.add_argument('--top', default='40', help='Show top N words or "all"')
    p.add_argument('--include-sources', action='store_true', help='Include source Japanese words')
    p.add_argument('--out', nargs='?', const='.', help='Write results to text file')
    p.add_argument('--out-dir', nargs='?', const='.', help='Write results to directory')
    p.add_argument('--image-out', nargs='?', const='.', help='Write word cloud image')
    p.add_argument('--image-out-dir', nargs='?', const='.', help='Write image to directory')
    p.add_argument('--image-width', type=int, default=800, help='Image width')
    p.add_argument('--image-height', type=int, default=400, help='Image height')
    p.add_argument('--bg-color', default='white', help='Background color')
    p.add_argument('--ensure-nltk', action='store_true', help='Download NLTK resources and exit')
    
    args = p.parse_args()
    
    # Parse top
    try:
        if isinstance(args.top, str) and args.top.lower() in ('all', 'a'):
            top_n = -1
        else:
            top_n = int(args.top)
    except Exception:
        print('Invalid --top value')
        sys.exit(2)
    
    # Ensure NLTK
    if args.ensure_nltk:
        ok = ensure_nltk_resources()
        if ok:
            print('NLTK resources ready.')
            sys.exit(0)
        else:
            print('Failed to ensure NLTK resources.')
            sys.exit(2)
    
    # Generate word cloud
    kwargs = {
        'zipf_exponent': args.zipf_exponent,
        'include_sources': args.include_sources,
        'apply_tfidf': not args.no_tfidf,
        'group_synonyms': not args.no_synonyms,
        'max_synonyms': args.max_synonyms,
        'pos_filter': not args.no_pos_filter,
        'dict_validate': not args.no_dict_validate,
        'dictionary_path': args.dictionary,
        'min_token_length': args.min_length,
    }
    
    if args.kanji:
        res = word_cloud_for_kanji(args.kanji, **{k: v for k, v in kwargs.items() if k in ['zipf_exponent', 'include_sources', 'pos_filter', 'dict_validate', 'dictionary_path', 'min_token_length']})
        label = args.kanji
        kind = 'kanji'
    elif args.element:
        res = word_cloud_for_element(args.element, **kwargs)
        label = args.element
        kind = 'element'
    else:
        res = word_cloud_for_radical(args.radical, **kwargs)
        label = args.radical
        kind = 'radical'
        # Resolve label
        try:
            rd = _load_json(RADICAL_JSON)
            if str(args.radical).isdigit() and rd.get(str(args.radical)):
                rc = rd[str(args.radical)].get('radical_char')
                if rc:
                    label = rc
        except Exception:
            pass
    
    # Get top results
    top_list = get_top_n(res, top_n)
    
    # Print to stdout or file
    text_out_path = _generate_text_file_path(args, label, kind=kind, top_n=top_n)
    
    def format_output(w, v):
        """Format a single result line."""
        if isinstance(v, dict) and 'cluster' in v:
            # Has cluster info
            weight = v.get('weight', 0.0)
            cluster = v.get('cluster', [])
            cluster_str = ','.join(cluster) if cluster else ''
            
            if args.include_sources:
                sources = v.get('ja', [])
                kanji_only = [s for s in sources if re.search(r'[\u4E00-\u9FFF]', s)]
                kanji_only = list(dict.fromkeys(kanji_only))
                src_str = ','.join(kanji_only[:20]) + (',...' if len(kanji_only) > 20 else '')
                return f"{w}\t{weight:.6f}\t[{cluster_str}]\t{src_str}"
            else:
                return f"{w}\t{weight:.6f}\t[{cluster_str}]"
        else:
            # No cluster info
            if args.include_sources and isinstance(v, dict):
                weight = v.get('weight', 0.0)
                sources = v.get('ja', [])
                kanji_only = [s for s in sources if re.search(r'[\u4E00-\u9FFF]', s)]
                kanji_only = list(dict.fromkeys(kanji_only))
                src_str = ','.join(kanji_only[:20]) + (',...' if len(kanji_only) > 20 else '')
                return f"{w}\t{weight:.6f}\t{src_str}"
            else:
                weight = v['weight'] if isinstance(v, dict) else v
                return f"{w}\t{float(weight):.6f}"
    
    if text_out_path:
        with open(text_out_path, 'w', encoding='utf-8') as fh:
            top_label = 'all' if (top_n is None or top_n <= 0) else str(top_n)
            fh.write(f"# word cloud top {top_label} for {kind} {label}\n")
            fh.write(f"# token\tweight\t[synset_cluster]\t(sources)\n")
            for w, v in top_list:
                fh.write(format_output(w, v) + "\n")
        print(f"Wrote results to {text_out_path}")
    else:
        for w, v in top_list:
            print(format_output(w, v))
    
    # Generate image if requested
    if args.image_out is not None or args.image_out_dir is not None:
        def _v_to_weight(v):
            return v['weight'] if isinstance(v, dict) else float(v)
        
        freq_items = list(top_list) if top_n > 0 else list(res.items())
        
        from collections import defaultdict as _dd
        _display = _dd(float)
        for k, v in freq_items:
            w = _v_to_weight(v)
            lbl = k.replace('_', ' ')
            _display[lbl] += w
        freq_dict = dict(_display)
        
        out_path = _generate_image_file_path(args, label, kind=kind, top_n=top_n)
        if out_path:
            try:
                _generate_and_save_wordcloud(freq_dict, out_path, width=args.image_width, height=args.image_height, background_color=args.bg_color)
                print(f"Wrote image to {out_path}")
            except Exception as e:
                print(f"Failed to generate image: {e}")
