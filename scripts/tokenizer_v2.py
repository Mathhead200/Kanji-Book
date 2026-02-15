"""Enhanced tokenizer with POS filtering, dictionary validation, and semantic quality controls.

Key improvements over v1:
- POS tagging to keep only nouns, verbs, adjectives
- Dictionary validation against NLTK words corpus or custom wordlist
- Disabled heuristic compound splitting (explicit dictionary only)
- Morpheme blacklist to filter suffix/prefix fragments
- Enhanced stopwords for semantically weak but common words
"""
from __future__ import annotations
import json
import os
import re
from typing import Dict, List, Optional, Set

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
COMPOUND_JSON = os.path.join(ROOT, 'data', 'compound_words.json')
MULTIWORD_JSON = os.path.join(ROOT, 'data', 'multiword_phrases.json')
NLTK_SENTINEL = os.path.join(ROOT, '.nltk_ready')

_COMPOUND_MAP: Optional[Dict[str, List[str]]] = None
_MULTIWORD_SET: Optional[Set[str]] = None
_ENGLISH_DICTIONARY: Optional[Set[str]] = None
_CUSTOM_DICTIONARY_PATH: Optional[str] = None

# Enhanced stopwords: common but semantically weak words
DEFAULT_STOPWORDS: Set[str] = {
    # Original stopwords
    'a','an','the','to','of','in','on','for','and','or','by','with','from','as',
    'be','is','are','was','were','that','this','these','those','it','its','at',
    'which','also','have','has','had','but','not','into','about','than','then',
    'such','their','they','them','may','can',
    # Ordinal suffixes
    'st','nd','rd','th',
    # Generic/vague words that appear frequently but lack semantic value
    'one', 'two', 'three', 'self', 'person', 'thing', 'way', 'time',
    'make', 'take', 'get', 'go', 'come', 'use', 'give', 'put',
    'some', 'other', 'most', 'part', 'over', 'down', 'up', 'out', 'in',
    'very', 'more', 'much', 'many', 'so', 'too', 'well',
}

# Morpheme blacklist: suffixes and prefixes that shouldn't appear as standalone tokens
MORPHEME_BLACKLIST: Set[str] = {
    # Noun suffixes
    'ion', 'tion', 'ation', 'sion', 'ment', 'ness', 'ity', 'ty',
    # Adjective suffixes
    'ese', 'ish', 'an', 'ian', 'ous', 'ious', 'eous', 'ful', 'less',
    'ical', 'ic', 'al', 'ive', 'able', 'ible',
    # Adverb suffixes
    'ly', 'ally',
    # Verb suffixes
    'ize', 'ise', 'ate', 'fy',
    # Common fragments from aggressive lemmatization
    'ing', 'ed', 'er', 'est',
}

WORD_RE = re.compile(r"[a-zA-Z_']+")

# NLTK resources
_NLTK_LEMMATIZER = None
_NLTK_POS_TAGGER = None
_NLTK_TRIED = False

_IRREGULAR_LEMMAS = {
    'analyses': 'analysis', 'children': 'child', 'mice': 'mouse',
    'teeth': 'tooth', 'feet': 'foot', 'oxen': 'ox', 'geese': 'goose',
    'men': 'man', 'women': 'woman',
}

def _get_nltk_lemmatizer():
    """Lazily import and return NLTK WordNetLemmatizer."""
    global _NLTK_LEMMATIZER, _NLTK_TRIED
    if _NLTK_LEMMATIZER is not None:
        return _NLTK_LEMMATIZER
    if _NLTK_TRIED:
        return None
    _NLTK_TRIED = True
    try:
        import nltk
        from nltk.stem import WordNetLemmatizer
        if not os.path.exists(NLTK_SENTINEL):
            try:
                nltk.data.find('corpora/wordnet')
            except LookupError:
                nltk.download('wordnet', quiet=True)
            try:
                nltk.data.find('corpora/omw-1.4')
            except LookupError:
                nltk.download('omw-1.4', quiet=True)
            try:
                with open(NLTK_SENTINEL, 'w', encoding='utf-8') as fh:
                    fh.write('ready')
            except Exception:
                pass
        _NLTK_LEMMATIZER = WordNetLemmatizer()
    except Exception as e:
        print(f"Warning: Could not initialize NLTK lemmatizer: {e}")
        _NLTK_LEMMATIZER = None
    return _NLTK_LEMMATIZER

def _get_pos_tagger():
    """Lazily load NLTK POS tagger."""
    global _NLTK_POS_TAGGER
    if _NLTK_POS_TAGGER is not None:
        return _NLTK_POS_TAGGER
    try:
        import nltk
        # Ensure averaged_perceptron_tagger is downloaded
        try:
            nltk.data.find('taggers/averaged_perceptron_tagger')
        except LookupError:
            nltk.download('averaged_perceptron_tagger', quiet=True)
        _NLTK_POS_TAGGER = True  # Just a flag indicating it's ready
        return _NLTK_POS_TAGGER
    except Exception as e:
        print(f"Warning: Could not initialize NLTK POS tagger: {e}")
        return None

def ensure_nltk_resources() -> bool:
    """Ensure required NLTK resources are present.
    
    Returns True if all resources available, False on failure.
    """
    lem = _get_nltk_lemmatizer()
    pos = _get_pos_tagger()
    return lem is not None and pos is not None

def _load_english_dictionary(custom_path: Optional[str] = None) -> Set[str]:
    """Load English dictionary from NLTK words corpus or custom file.
    
    Args:
        custom_path: Optional path to custom word list (one word per line)
    
    Returns:
        Set of lowercase English words
    """
    global _ENGLISH_DICTIONARY, _CUSTOM_DICTIONARY_PATH
    
    # Return cached if same path
    if _ENGLISH_DICTIONARY is not None and custom_path == _CUSTOM_DICTIONARY_PATH:
        return _ENGLISH_DICTIONARY
    
    _CUSTOM_DICTIONARY_PATH = custom_path
    
    if custom_path:
        # Load custom dictionary
        try:
            with open(custom_path, 'r', encoding='utf-8') as fh:
                words = {line.strip().lower() for line in fh if line.strip()}
            _ENGLISH_DICTIONARY = words
            return _ENGLISH_DICTIONARY
        except Exception as e:
            print(f"Warning: Could not load custom dictionary from {custom_path}: {e}")
            print("Falling back to NLTK words corpus...")
    
    # Load NLTK words corpus (default)
    try:
        import nltk
        try:
            nltk.data.find('corpora/words')
        except LookupError:
            nltk.download('words', quiet=True)
        from nltk.corpus import words
        _ENGLISH_DICTIONARY = {w.lower() for w in words.words()}
        return _ENGLISH_DICTIONARY
    except Exception as e:
        print(f"Error: Could not load NLTK words corpus: {e}")
        print("Dictionary validation will be disabled.")
        _ENGLISH_DICTIONARY = set()  # Empty set means no validation
        return _ENGLISH_DICTIONARY

def _is_valid_english_word(token: str, dictionary: Set[str]) -> bool:
    """Check if token is a valid English word.
    
    Args:
        token: The token to validate
        dictionary: Set of valid English words
    
    Returns:
        True if valid, False otherwise
    """
    if not dictionary:  # Empty dictionary means validation disabled
        return True
    return token.lower() in dictionary

def _pos_filter_tokens(tokens: List[str]) -> List[str]:
    """Filter tokens to keep only nouns, verbs, and adjectives.
    
    Uses NLTK POS tagger. Keeps tokens tagged as:
    - NN* (nouns)
    - VB* (verbs)
    - JJ* (adjectives)
    
    Args:
        tokens: List of tokens to filter
    
    Returns:
        Filtered list containing only content words
    """
    if not tokens:
        return []
    
    # Ensure POS tagger is available
    if _get_pos_tagger() is None:
        print("Warning: POS tagger unavailable, skipping POS filtering")
        return tokens
    
    try:
        import nltk
        # Tag the tokens
        tagged = nltk.pos_tag(tokens)
        
        # Keep only nouns, verbs, adjectives
        filtered = []
        for word, tag in tagged:
            if tag.startswith(('NN', 'VB', 'JJ')):
                filtered.append(word)
        
        return filtered
    except Exception as e:
        print(f"Warning: POS filtering failed: {e}")
        return tokens

def _heuristic_lemmatize(token: str) -> str:
    """Heuristic lemmatizer as fallback when NLTK unavailable."""
    if len(token) <= 3:
        return token
    
    # Plural rules
    if token.endswith('ies') and len(token) > 4:
        return token[:-3] + 'y'
    if token.endswith("'s") and len(token) > 3:
        return token[:-2]
    if token.endswith('s') and not token.endswith('ss') and len(token) > 3:
        if re.search(r'(ous|ious|less|ness|ful|able|ible|istic|ic|ial|al|ent|ant)$', token):
            return token
        if token.endswith('es') and len(token) > 4:
            if token.endswith('les'):
                return token[:-1]
            return token[:-2]
        return token[:-1]
    
    # Gerunds/participles
    if token.endswith('ing') and len(token) > 5:
        stem = token[:-3]
        if not re.search(r'[aeiou]', stem):
            return token
        if len(stem) > 2 and stem[-1] == stem[-2]:
            return stem[:-1]
        if len(stem) >= 3 and re.match(r'^[^aeiou][aeiou][^aeiou]$', stem[-3:]):
            return stem + 'e'
        return stem
    
    if token.endswith('ed') and len(token) > 4:
        stem = token[:-2]
        if stem.endswith('i'):
            stem = stem[:-1] + 'y'
        return stem
    
    return token

def _lemmatize_token(token: str) -> str:
    """Lemmatize a token using NLTK or heuristics."""
    if not token:
        return token
    
    low = token.lower()
    if low in _IRREGULAR_LEMMAS:
        return _IRREGULAR_LEMMAS[low]
    
    le = _get_nltk_lemmatizer()
    if le is not None:
        try:
            # Try noun first, then verb
            n = le.lemmatize(low, pos='n')
            if n != low:
                return n
            v = le.lemmatize(low, pos='v')
            if v != low:
                return v
        except Exception:
            pass
    
    return _heuristic_lemmatize(token)

def _load_compound_map() -> Dict[str, List[str]]:
    """Load explicit compound word mappings from JSON."""
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
    """Split compound words using EXPLICIT dictionary only.
    
    Disabled heuristic splitting to prevent fragment generation.
    
    Args:
        token: Token to potentially split
        known_words: Set of known words (NOT USED in this version)
    
    Returns:
        List containing either [token] or [part1, part2] if explicit match found
    """
    if len(token) < 6:
        return [token]
    
    t = token.lower()
    cmap = _load_compound_map()
    
    if cmap:
        # Direct match
        if t in cmap:
            return cmap[t]
        # Try removing punctuation
        t_no_punc = re.sub(r"[_\-\s]+", "", t)
        if t_no_punc in cmap:
            return cmap[t_no_punc]
    
    # NO HEURISTIC FALLBACK - prevents fragment generation
    return [token]

def _load_multiword_phrases() -> Set[str]:
    """Load multi-word phrases from JSON."""
    global _MULTIWORD_SET
    if _MULTIWORD_SET is not None:
        return _MULTIWORD_SET
    
    try:
        with open(MULTIWORD_JSON, 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
            s = {str(p).lower().strip(): True for p in raw if p}
            result = set(s.keys())
    except Exception:
        result = set()
    
    _MULTIWORD_SET = result
    return _MULTIWORD_SET

def _apply_multiword_phrases(meaning: str) -> str:
    """Replace multi-word phrases with underscore-joined tokens."""
    if not meaning:
        return meaning
    
    phrases = _load_multiword_phrases()
    if not phrases:
        return meaning
    
    for ph in sorted(phrases, key=lambda x: len(x), reverse=True):
        try:
            pat = re.compile(r"\b" + re.escape(ph) + r"\b", flags=re.IGNORECASE)
            if pat.search(meaning):
                replacement = ph.replace(' ', '_')
                meaning = pat.sub(replacement, meaning)
        except re.error:
            continue
    
    return meaning

def tokenize(
    meaning: str,
    stopwords: Optional[Set[str]] = None,
    split_compounds: bool = False,
    known_words: Optional[Set[str]] = None,
    pos_filter: bool = True,
    dict_validate: bool = True,
    dictionary_path: Optional[str] = None,
    min_length: int = 3
) -> List[str]:
    """Enhanced tokenization with POS filtering and dictionary validation.
    
    Pipeline:
    1. Extract tokens from text
    2. Normalize (lowercase, lemmatize)
    3. Optionally split compounds (explicit dictionary only)
    4. POS filter (keep nouns, verbs, adjectives)
    5. Dictionary validate (ensure real English words)
    6. Filter stopwords and morpheme fragments
    7. Apply minimum length requirement
    
    Args:
        meaning: Text to tokenize
        stopwords: Words to exclude (defaults to DEFAULT_STOPWORDS)
        split_compounds: Whether to split compound words
        known_words: Set of known words for compound splitting
        pos_filter: Whether to apply POS filtering (requires NLTK)
        dict_validate: Whether to validate against English dictionary
        dictionary_path: Optional path to custom word list
        min_length: Minimum token length (default 3)
    
    Returns:
        List of validated, filtered tokens
    """
    if not meaning:
        return []
    
    stopwords = stopwords or DEFAULT_STOPWORDS
    
    # Step 1: Extract tokens
    meaning = re.sub(r"\([^)]*\)", " ", meaning)  # Remove parentheticals
    meaning = _apply_multiword_phrases(meaning)
    tokens = WORD_RE.findall(meaning)
    
    # Step 2: Normalize
    normalized = []
    for t in tokens:
        t = t.lower()
        t = re.sub(r"^[^a-zA-Z_]+|[^a-zA-Z_]+$", "", t)
        if not t:
            continue
        if len(t) < min_length:  # Early length filter
            continue
        t = _lemmatize_token(t)
        normalized.append(t)
    
    # Step 3: Optionally split compounds
    if split_compounds and known_words:
        result = []
        for tok in normalized:
            sub_tokens = _split_compound_token(tok, known_words)
            result.extend(sub_tokens)
        normalized = result
    
    # Step 4: POS filtering (keep nouns, verbs, adjectives)
    if pos_filter:
        normalized = _pos_filter_tokens(normalized)
    
    # Step 5: Dictionary validation
    if dict_validate:
        dictionary = _load_english_dictionary(dictionary_path)
        normalized = [t for t in normalized if _is_valid_english_word(t, dictionary)]
    
    # Step 6: Filter stopwords and morpheme fragments
    filtered = []
    for t in normalized:
        if t in stopwords:
            continue
        if t in MORPHEME_BLACKLIST:
            continue
        if len(t) < min_length:  # Final length check after lemmatization
            continue
        filtered.append(t)
    
    return filtered

def split_tokens(
    tokens: List[str],
    known_words: Set[str],
    pos_filter: bool = True,
    dict_validate: bool = True,
    dictionary_path: Optional[str] = None,
    min_length: int = 3
) -> List[str]:
    """Split and validate already-tokenized words.
    
    This applies compound splitting and validation to pre-tokenized text.
    
    Args:
        tokens: List of tokens to process
        known_words: Set of known words for compound splitting
        pos_filter: Whether to apply POS filtering
        dict_validate: Whether to validate against dictionary
        dictionary_path: Optional custom dictionary path
        min_length: Minimum token length
    
    Returns:
        List of split and validated tokens
    """
    # Split compounds
    result = []
    for tok in tokens:
        sub_tokens = _split_compound_token(tok, known_words)
        result.extend(sub_tokens)
    
    # Apply POS filtering
    if pos_filter:
        result = _pos_filter_tokens(result)
    
    # Dictionary validation
    if dict_validate:
        dictionary = _load_english_dictionary(dictionary_path)
        result = [t for t in result if _is_valid_english_word(t, dictionary)]
    
    # Filter by length and morphemes
    filtered = []
    for t in result:
        if t in MORPHEME_BLACKLIST:
            continue
        if len(t) < min_length:
            continue
        filtered.append(t)
    
    return filtered
