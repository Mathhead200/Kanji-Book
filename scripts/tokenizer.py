from __future__ import annotations
import json
import os
import re
from typing import Dict, List, Optional, Set

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
COMPOUND_JSON = os.path.join(ROOT, 'data', 'compound_words.json')
MULTIWORD_JSON = os.path.join(ROOT, 'data', 'multiword_phrases.json')
NLTK_SENTINEL = os.path.join(ROOT, '.nltk_ready')

_COMPOUND_MAP: Optional[Dict[str, List[str]]] = None  # loaded lazily from COMPOUND_JSON
_MULTIWORD_SET: Optional[Set[str]] = None  # loaded lazily from MULTIWORD_JSON

# Minimal English stopwords (expandable)
DEFAULT_STOPWORDS: Set[str] = {
    'a','an','the','to','of','in','on','for','and','or','by','with','from','as',
    'be','is','are','was','were','that','this','these','those','it','its','at',
    'which','also','have','has','had','but','not','into','about','than','then',
    'such','their','they','them','may','can',
    # ordinal suffixes and common tokens that come from numerals like '6th' -> 'th'
    'st','nd','rd','th'
}

WORD_RE = re.compile(r"[a-zA-Z_']+")  # allow underscores for multi-word phrases (e.g., 'bumper_crop')

# Simple lemmatizer for English nouns/verbs to cover plurals and common forms.
# Prefer using NLTK's WordNet lemmatizer when available; fall back to the
# heuristic implementation below if NLTK is missing or fails.
_NLTK_LEMMATIZER = None
_NLTK_TRIED = False

_IRREGULAR_LEMMAS = {
    # common irregulars
    'analyses': 'analysis',
    'children': 'child',
    'mice': 'mouse',
    'teeth': 'tooth',
    'feet': 'foot',
    'oxen': 'ox',
    'geese': 'goose',
    'men': 'man',
    'women': 'woman',
}

def _get_nltk_lemmatizer():
    """Lazily import and return an NLTK WordNetLemmatizer if available.

    This function will try to avoid repeated expensive checks/downloads by
    consulting a sentinel file (`NLTK_SENTINEL`) created after a successful
    resource download. If NLTK is not installed or an error occurs, returns
    None and the code falls back to the heuristics.
    """
    global _NLTK_LEMMATIZER, _NLTK_TRIED
    if _NLTK_LEMMATIZER is not None:
        return _NLTK_LEMMATIZER
    if _NLTK_TRIED:
        return None
    _NLTK_TRIED = True
    try:
        import nltk
        from nltk.stem import WordNetLemmatizer
        # If we've previously created the sentinel file, skip corpus existence checks
        if not os.path.exists(NLTK_SENTINEL):
            try:
                nltk.data.find('corpora/wordnet')
            except LookupError:
                nltk.download('wordnet', quiet=True)
            try:
                nltk.data.find('corpora/omw-1.4')
            except LookupError:
                nltk.download('omw-1.4', quiet=True)
            # if downloads succeed, touch sentinel
            try:
                with open(NLTK_SENTINEL, 'w', encoding='utf-8') as fh:
                    fh.write('ready')
            except Exception:
                # non-fatal: if we cannot write sentinel, continue but avoid crash
                pass
        _NLTK_LEMMATIZER = WordNetLemmatizer()
    except Exception:
        _NLTK_LEMMATIZER = None
    return _NLTK_LEMMATIZER

def ensure_nltk_resources() -> bool:
    """Ensure required NLTK corpora are present and create sentinel file.

    Returns True if resources are available (or successfully downloaded),
    False on failure.
    """
    le = _get_nltk_lemmatizer()
    return le is not None

def _heuristic_lemmatize(token: str) -> str:
    """Original heuristic lemmatizer retained as fallback."""
    # Preserve tokens that are too short
    if len(token) <= 3:
        return token
    # rules for plurals: 'ies' -> 'y', 's' -> '' (not for 'ss')
    if token.endswith('ies') and len(token) > 4:
        return token[:-3] + 'y'
    if token.endswith("'s") and len(token) > 3:
        return token[:-2]
    if token.endswith('s') and not token.endswith('ss') and len(token) > 3:
        # Avoid stripping 's' from adjectives and other word endings where
        # removing the 's' would create an invalid/stemless token (e.g. 'glorious' -> 'gloriou').
        # Common suffixes to preserve include: -ous, -ious, -less, -ness, -ful, -able, -ible, -ic, -al
        if re.search(r'(ous|ious|less|ness|ful|able|ible|istic|ic|ial|al|ent|ant)$', token):
            return token
        # handle common plural 'es' -> remove 'es' when appropriate
        # but avoid chopping off the 'e' in words like 'vegetables' -> 'vegetable'
        if token.endswith('es') and len(token) > 4:
            if token.endswith('les'):
                # words like 'vegetables' -> 'vegetable'
                return token[:-1]
            return token[:-2]
        return token[:-1]
    # gerunds/participles -> remove 'ing' or 'ed'
    if token.endswith('ing') and len(token) > 5:
        stem = token[:-3]
        # don't strip 'ing' if the stem would have no vowel (avoids 'spring' -> 'spr')
        if not re.search(r'[aeiou]', stem):
            return token
        # handle doubled consonant like 'running' -> 'run'
        if len(stem) > 2 and stem[-1] == stem[-2]:
            return stem[:-1]
        # heuristic: if stem ends in CVC (consonant-vowel-consonant) it's likely
        # the source had a trailing 'e' that was dropped (make -> making)
        if len(stem) >= 3 and re.match(r'^[^aeiou][aeiou][^aeiou]$', stem[-3:]):
            return stem + 'e'
        # otherwise return the stem as-is
        return stem
    if token.endswith('ed') and len(token) > 4:
        stem = token[:-2]
        if stem.endswith('i'):
            stem = stem[:-1] + 'y'
        return stem
    return token

def _lemmatize_token(token: str) -> str:
    # use irregular map first
    if not token:
        return token
    low = token.lower()
    if low in _IRREGULAR_LEMMAS:
        return _IRREGULAR_LEMMAS[low]
    # try NLTK lemmatizer if available
    le = _get_nltk_lemmatizer()
    if le is not None:
        try:
            # try noun first, then verb
            n = le.lemmatize(low, pos='n')
            if n != low:
                return n
            v = le.lemmatize(low, pos='v')
            if v != low:
                return v
        except Exception:
            # if NLTK fails for any reason, fall back to heuristics
            pass
    # fallback heuristic
    return _heuristic_lemmatize(token)

# Attempt to split compound tokens into two known parts using a known word set
def _load_compound_map() -> Dict[str, List[str]]:
    """Load and cache explicit compound -> [parts] mapping from `COMPOUND_JSON`.

    The JSON is expected to map compacted compound form (e.g., 'blackbird') to an
    array of its parts (e.g., ['black', 'bird']).
    """
    global _COMPOUND_MAP
    if _COMPOUND_MAP is not None:
        return _COMPOUND_MAP
    try:
        with open(COMPOUND_JSON, 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
            normalized = {k.lower(): v for k, v in raw.items()}
    except Exception:
        normalized = {}
    _COMPOUND_MAP = normalized
    return _COMPOUND_MAP

def _split_compound_token(token: str, known_words: Set[str]) -> List[str]:
    # Prefer an explicit compound mapping when available
    if len(token) < 6:
        return [token]
    t = token.lower()
    cmap = _load_compound_map()
    if cmap:
        # direct match
        if t in cmap:
            return cmap[t]
        # try removing common punctuation/hyphens/underscores
        t_no_punc = re.sub(r"[_\-\s]+", "", t)
        if t_no_punc in cmap:
            return cmap[t_no_punc]
    # Fallback: try splitting by known word membership (heuristic)
    # Avoid producing poor 3+3 splits like 'bum'+'per' from 'bumper' by requiring
    # that at least one part is length >= 4 (this keeps many valid splits while
    # avoiding short nonsense parts).
    for i in range(3, len(token) - 2):
        a = token[:i]
        b = token[i:]
        if a in known_words and b in known_words:
            if max(len(a), len(b)) < 4:
                # both parts are short (<=3), skip this split
                continue
            return [a, b]
    return [token]

def _load_multiword_phrases() -> Set[str]:
    """Load and cache explicit multi-word phrases from `MULTIWORD_JSON`.

    The JSON should be a list of phrases (strings) such as:
        ["bumper crop", "jack o'lantern"]
    Phrases are normalized to lowercase for matching and replacement in meanings.
    """
    global _MULTIWORD_SET
    if _MULTIWORD_SET is not None:
        return _MULTIWORD_SET
    try:
        with open(MULTIWORD_JSON, 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
            # normalize to lowercase and strip
            s = {str(p).lower().strip(): True for p in raw if p}
            result = set(s.keys())
    except Exception:
        result = set()
    _MULTIWORD_SET = result
    return _MULTIWORD_SET

def _apply_multiword_phrases(meaning: str) -> str:
    """Replace known multi-word phrases in `meaning` with underscore-joined tokens.

    For example, "bumper crop" -> "bumper_crop" so the phrase is treated as a
    single token by the tokenizer. Matching is case-insensitive and respects
    word boundaries.
    """
    if not meaning:
        return meaning
    phrases = _load_multiword_phrases()
    if not phrases:
        return meaning
    # sort by length desc to avoid partial replacements
    for ph in sorted(phrases, key=lambda x: len(x), reverse=True):
        # build regex that respects word boundaries and punctuation
        try:
            pat = re.compile(r"\b" + re.escape(ph) + r"\b", flags=re.IGNORECASE)
            if pat.search(meaning):
                replacement = ph.replace(' ', '_')
                meaning = pat.sub(replacement, meaning)
        except re.error:
            # skip bad regex
            continue
    return meaning

def tokenize(meaning: str, stopwords: Optional[Set[str]] = None, split_compounds: bool = False, known_words: Optional[Set[str]] = None) -> List[str]:
    """Tokenize a meaning string into English words.
    
    Args:
        meaning: The text to tokenize
        stopwords: Set of words to exclude (defaults to DEFAULT_STOPWORDS)
        split_compounds: If True, attempt to split compound words using known_words
        known_words: Set of known words for compound splitting (required if split_compounds=True)
    
    Returns:
        List of normalized, lemmatized tokens
    """
    if not meaning:
        return []
    stopwords = stopwords or DEFAULT_STOPWORDS
    # remove parentheses content that often contains examples or notes
    meaning = re.sub(r"\([^)]*\)", " ", meaning)
    # apply multi-word-phrase normalization (e.g., "bumper crop" -> "bumper_crop")
    meaning = _apply_multiword_phrases(meaning)
    # find alphabetic tokens (underscores from phrases are preserved)
    tokens = WORD_RE.findall(meaning)
    # normalize tokens: lowercase and strip leading/trailing apostrophes/quotes/punctuation
    normalized = []
    for t in tokens:
        t = t.lower()
        t = re.sub(r"^[^a-zA-Z_]+|[^a-zA-Z_]+$", "", t)
        if not t:
            continue
        if t in stopwords or len(t) <= 1:
            continue
        # lemmatize common inflections
        t = _lemmatize_token(t)
        normalized.append(t)
    
    # optionally split compound words
    if split_compounds and known_words:
        result = []
        for tok in normalized:
            sub_tokens = _split_compound_token(tok, known_words)
            result.extend(sub_tokens)
        return result
    
    return normalized

def split_tokens(tokens: List[str], known_words: Set[str]) -> List[str]:
    """Split a list of tokens, breaking compound words into their components.
    
    This is useful when you have already-tokenized text and want to apply
    compound splitting as a post-processing step.
    
    Args:
        tokens: List of tokens to process
        known_words: Set of known words for identifying valid compound splits
    
    Returns:
        List of tokens with compounds split into their components
    """
    result = []
    for tok in tokens:
        sub_tokens = _split_compound_token(tok, known_words)
        result.extend(sub_tokens)
    return result
