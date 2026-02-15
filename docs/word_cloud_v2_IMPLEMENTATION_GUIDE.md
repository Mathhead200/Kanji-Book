# Word Cloud V3: Implementation Guide

## Overview

We've completely rebuilt the tokenization and word cloud generation system with aggressive semantic quality improvements. The new system uses:

1. **Enhanced Tokenization** (tokenizer_v2.py)
   - POS filtering (nouns, verbs, adjectives only)
   - Dictionary validation against NLTK words corpus
   - Morpheme blacklist (filters suffix/prefix fragments)
   - Disabled heuristic compound splitting

2. **Dual Weighting System** (word_cloud_v3.py)
   - Zipf weighting for Japanese word frequency
   - TF-IDF weighting for English token rarity
   - Combined: `weight = zipf(jp_word) × tfidf(en_token)`

3. **Synonym Grouping**
   - WordNet synset-based clustering
   - Configurable representative selection
   - Full cluster reporting in output

---

## Architecture

### Tokenization Pipeline (tokenizer_v2.py)

```
Input Text
    ↓
1. Extract tokens (regex, multi-word phrases)
    ↓
2. Normalize (lowercase, lemmatize)
    ↓
3. Split compounds (explicit dictionary ONLY)
    ↓
4. POS filter (keep NN*, VB*, JJ*)  ← NEW
    ↓
5. Dictionary validate (NLTK words) ← NEW
    ↓
6. Filter stopwords + morphemes     ← ENHANCED
    ↓
7. Apply minimum length
    ↓
Output: Clean semantic tokens
```

### Word Cloud Pipeline (word_cloud_v3.py)

```
Japanese Words (with frequency ranks)
    ↓
1. Tokenize English meanings → tokens
    ↓
2. Apply Zipf weight to each token
    ↓
3. Aggregate across kanji/radical
    ↓
4. Calculate IDF scores across corpus ← NEW
    ↓
5. Apply TF-IDF: weight × IDF        ← NEW
    ↓
6. Group by WordNet synsets          ← NEW
    ↓
7. Select representatives            ← NEW
    ↓
Output: Clean, semantic word cloud
```

---

## Key Improvements

### Problem 1: Fragment Tokens ("ion", "ese", "ness")

**Root Cause**: Aggressive lemmatization + heuristic compound splitting created nonsense fragments.

**Solutions Applied**:
- ✅ Morpheme blacklist filters 40+ common suffixes
- ✅ Disabled heuristic compound splitting (explicit dictionary only)
- ✅ Dictionary validation ensures tokens are real English words
- ✅ POS filtering removes non-content words

**Result**: "nation" stays as "nation", not split into "nat" + "ion"

---

### Problem 2: Generic Words ("one", "make", "person")

**Root Cause**: Very common but semantically weak words flood results.

**Solutions Applied**:
- ✅ Expanded stopwords (30+ generic terms)
- ✅ TF-IDF downweights tokens appearing across many kanji
- ✅ POS filtering removes function words

**Result**: "one" (appears in 1000 kanji) gets massive IDF penalty vs "cricket" (appears in 2 kanji)

---

### Problem 3: Synonym Redundancy

**Root Cause**: "plant", "vegetation", "flora" all appear separately.

**Solutions Applied**:
- ✅ WordNet synset grouping
- ✅ Configurable representative selection (default: 1 per synset)
- ✅ Full cluster reporting preserves detail

**Result**: "plant" shown in cloud, full cluster ["plant", "vegetation", "flora"] in detailed output

---

## Usage

### Basic Usage

```bash
# Generate word cloud for radical 口 (mouth)
python scripts/word_cloud_v3.py --radical 口 --top 40

# With all enhancements enabled (default)
python scripts/word_cloud_v3.py --radical 口 --top 40 --include-sources

# Save to file
python scripts/word_cloud_v3.py --radical 口 --top 40 --out results.txt
```

### Advanced Options

#### Disable TF-IDF (Zipf only)
```bash
python scripts/word_cloud_v3.py --radical 口 --no-tfidf
```

#### Disable Synonym Grouping
```bash
python scripts/word_cloud_v3.py --radical 口 --no-synonyms
```

#### Allow Multiple Representatives Per Synset
```bash
# Show top 2 words from each synonym group
python scripts/word_cloud_v3.py --radical 口 --max-synonyms 2
```

#### Custom English Dictionary
```bash
# Use a curated 10k word list instead of NLTK's 235k
python scripts/word_cloud_v3.py --radical 口 --dictionary common_words.txt
```

#### Disable POS Filtering
```bash
# Keep all word types (nouns, verbs, adjectives, adverbs, etc.)
python scripts/word_cloud_v3.py --radical 口 --no-pos-filter
```

#### Adjust Minimum Token Length
```bash
# Require tokens to be at least 4 characters
python scripts/word_cloud_v3.py --radical 口 --min-length 4
```

---

## Output Format

### Without Synonym Grouping

```
# word cloud top 40 for radical 口
# token    weight    (sources)
mouth     0.025431  口,くち,こう,...
speak     0.018234  言う,話す,述べる,...
eat       0.015678  食べる,喰う,...
```

### With Synonym Grouping (Default)

```
# word cloud top 40 for radical 口
# token    weight    [synset_cluster]    (sources)
mouth     0.025431  [mouth,oral_cavity,maw]  口,くち,こう,...
speak     0.018234  [speak,talk,utter,say]   言う,話す,述べる,...
eat       0.015678  [eat,consume,ingest]     食べる,喰う,...
```

**Cluster Field**: All synonyms grouped together, representative shown first

---

## Dual Weighting Explained

### Zipf Component (Japanese Word Frequency)

```python
zipf_weight = 1 / (japanese_word_rank ** exponent)
```

- Common Japanese words (rank 1-100): High weight
- Rare Japanese words (rank 10,000+): Low weight
- **Purpose**: Concepts from common words are more important

### TF-IDF Component (English Token Rarity)

```python
tf = token_frequency_in_this_kanji
idf = log(total_kanji / kanji_containing_this_token)
tfidf = tf × idf
```

- Token in 1 kanji: High IDF → boosted
- Token in 1000 kanji: Low IDF → suppressed
- **Purpose**: Distinctive concepts are more meaningful

### Combined

```python
final_weight = zipf_weight × tfidf_weight
```

**Example**:
- "mouth" in 口: High Zipf (common word) × Low IDF (appears everywhere) = **Medium**
- "cricket" in 蟋: Medium Zipf × High IDF (very specific) = **High**
- "one" everywhere: High Zipf × Near-zero IDF = **Very Low**

---

## Tokenizer Configuration

### Enhanced Stopwords

Added 30+ semantically weak but common words:
```python
'one', 'two', 'three', 'self', 'person', 'thing', 'way', 'time',
'make', 'take', 'get', 'go', 'come', 'use', 'give', 'put',
...
```

### Morpheme Blacklist

Filters 40+ suffix/prefix fragments:
```python
# Noun suffixes
'ion', 'tion', 'ation', 'sion', 'ment', 'ness', 'ity'

# Adjective suffixes
'ese', 'ish', 'an', 'ian', 'ous', 'ious', 'ful', 'less', 'ical', 'ic'

# Verb suffixes
'ize', 'ise', 'ate', 'fy'

# Lemmatization artifacts
'ing', 'ed', 'er', 'est'
```

### POS Tags Kept

Using NLTK POS tagger:
- **NN\***: Nouns (all types)
- **VB\***: Verbs (all forms)
- **JJ\***: Adjectives

**Filtered out**:
- Determiners, prepositions, conjunctions
- Pronouns, particles, modals
- Adverbs, interjections

---

## Dependencies

### Required
```bash
pip install nltk
```

### Optional (for images)
```bash
pip install wordcloud pillow numpy
```

### NLTK Data
First run will auto-download:
- wordnet (lemmatization)
- omw-1.4 (multilingual wordnet)
- averaged_perceptron_tagger (POS tagging)
- words (235k English word corpus)

Or manually:
```bash
python scripts/word_cloud_v3.py --ensure-nltk
```

---

## Comparison: V2 vs V3

### Before (V2)
```
口 (mouth) top results:
one       0.010303
ion       0.006388
ese       0.004771
up        0.004357
make      0.003968
ical      0.003502
out       0.003425
ness      0.003250
```

**Problems**:
- Fragments: ion, ese, ical, ness
- Generic: one, make, up, out
- No semantic coherence

### After (V3, Expected)
```
口 (mouth) top results:
mouth     0.025431  [mouth,oral_cavity]
speak     0.018234  [speak,talk,utter]
eat       0.015678  [eat,consume,ingest]
voice     0.012456  [voice,vocalization]
taste     0.011234  [taste,flavor,savor]
tooth     0.009876  [tooth,dentition]
```

**Improvements**:
- Real words only
- Semantic coherence
- Meaningful concepts
- Clean synonym handling

---

## Testing Recommendations

### Step 1: Test Tokenization Alone

Create a test script:
```python
from tokenizer_v2 import tokenize

test_meanings = [
    "nation",         # Should NOT split to "nat" + "ion"
    "Japanese",       # Should NOT create "ese" fragment
    "one's mouth",    # Should filter "one"
    "beautiful",      # Should keep (adjective)
    "happiness",      # Should filter "ness" fragment
    "quickly running", # Should keep "run" (verb), filter "quickly" (adverb)
]

for meaning in test_meanings:
    tokens = tokenize(meaning, pos_filter=True, dict_validate=True)
    print(f"{meaning:20} → {tokens}")
```

**Expected**:
```
nation               → ['nation']
Japanese             → ['japanese']
one's mouth          → ['mouth']
beautiful            → ['beautiful']
happiness            → ['happiness']  # if in dictionary, else filtered
quickly running      → ['run']
```

### Step 2: Test on 口 Radical

```bash
python scripts/word_cloud_v3.py --radical 口 --top 20
```

**Look for**:
- ✅ No fragments (ion, ese, ness, ical)
- ✅ No generic words (one, make, take)
- ✅ Semantic concepts (mouth, speak, eat, voice)
- ✅ Clean clusters if synonyms enabled

### Step 3: Compare Modes

```bash
# Zipf only (no TF-IDF)
python scripts/word_cloud_v3.py --radical 口 --no-tfidf --out zipf_only.txt

# TF-IDF enabled (default)
python scripts/word_cloud_v3.py --radical 口 --out tfidf.txt

# Compare results
diff zipf_only.txt tfidf.txt
```

**Expect**: Generic words higher in zipf_only, specific concepts higher in tfidf

### Step 4: Test Synonym Grouping

```bash
# No grouping
python scripts/word_cloud_v3.py --radical 口 --no-synonyms --out no_syn.txt

# With grouping (default)
python scripts/word_cloud_v3.py --radical 口 --out with_syn.txt

# Compare
diff no_syn.txt with_syn.txt
```

**Expect**: With grouping shows fewer total words, each with cluster info

---

## Troubleshooting

### "POS tagger unavailable"
```bash
python -c "import nltk; nltk.download('averaged_perceptron_tagger')"
```

### "Could not load NLTK words corpus"
```bash
python -c "import nltk; nltk.download('words')"
```

### "Could not load WordNet"
```bash
python -c "import nltk; nltk.download('wordnet'); nltk.download('omw-1.4')"
```

### Still seeing fragments
- Check if `--no-pos-filter` is enabled (disable it)
- Check if `--no-dict-validate` is enabled (disable it)
- Verify NLTK resources loaded: `python scripts/word_cloud_v3.py --ensure-nltk`

### Too few results
- Lower `--min-length` (try 2 instead of 3)
- Disable POS filter temporarily: `--no-pos-filter`
- Check if custom dictionary is too restrictive

---

## File Structure

```
your_project/
├── scripts/
│   ├── tokenizer_v2.py         ← Enhanced tokenizer
│   └── word_cloud_v3.py        ← New word cloud generator
├── data/
│   ├── word_cache.json         ← Japanese words + meanings
│   ├── radical_data.json       ← Radical → kanji mappings
│   ├── element_stats.json      ← KanjiVG elements
│   ├── compound_words.json     ← Explicit compound dictionary
│   └── multiword_phrases.json  ← Multi-word phrase patterns
└── .nltk_ready                 ← Sentinel (auto-created)
```

---

## Next Steps

1. **Test thoroughly** on several radicals/kanji
2. **Iterate on stopwords** if generic words still appear
3. **Tune TF-IDF** if weighting seems off (can adjust with parameters)
4. **Expand compound dictionary** if needed compounds aren't splitting
5. **Create curated word list** (10k most common English words) for stricter filtering

---

## Research Citations

This implementation draws on established NLP practices:

1. **TF-IDF Weighting**: Salton & McGill (1983). *Introduction to Modern Information Retrieval*.

2. **POS Filtering for Word Clouds**: Standard practice in corpus linguistics and text mining.

3. **WordNet for Semantic Grouping**: Miller (1995). "WordNet: a lexical database for English."

4. **Stopword Lists**: van Rijsbergen (1979). *Information Retrieval*.

For kanji learning specifically, this aligns with:
- Mnemonic-based learning (Heisig, *Remembering the Kanji*)
- Concrete→Abstract progression (WaniKani methodology)
- Semantic field organization (Kanjidamage approach)

---

## Summary

**Version 3 provides**:
- ✅ No morpheme fragments
- ✅ No generic/weak words
- ✅ Real English words only
- ✅ Semantic concepts emphasized
- ✅ Synonym redundancy reduced
- ✅ Dual weighting (Zipf × TF-IDF)
- ✅ Full cluster reporting
- ✅ Highly configurable

**Perfect for**: Educational kanji learning tools where semantic clarity and meaningful associations are crucial.
