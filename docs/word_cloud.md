Here’s a polished **README.md** version of the documentation—clean, structured, and ready to drop directly into your repository.

---

# **Word Cloud Generation Module**
### *Semantic word‑cloud weights for kanji and radicals*

This module generates **English semantic word‑cloud weight dictionaries** for individual **kanji** or **radicals**, using enriched lexical data from `word_cache.json`. It supports:

- Zipf‑weighted frequency scoring  
- English meaning tokenization with lemmatization  
- Multi‑word phrase detection  
- Compound splitting  
- Optional source‑tracking (Japanese words & readings)  
- Optional PNG word‑cloud image generation (via `wordcloud`)

---

## **1. Overview**

The module exposes two primary public functions:

| Function | Description |
|---------|-------------|
| `word_cloud_for_kanji()` | Generates a weighted English word cloud for a single kanji. |
| `word_cloud_for_radical()` | Aggregates word clouds for all kanji belonging to a radical. |

Both functions return:

- `{ token: weight }`  
- or `{ token: { weight, ja: [...] } }` when `include_sources=True`.

A CLI interface is also included for generating text output and optional PNG images.

---

## **2. Data Requirements**

The script expects the following JSON files:

| File | Purpose |
|------|---------|
| `data/word_cache.json` | Core dataset: kanji → words, meanings, frequency ranks, readings. |
| `data/radical_data.json` | Radical → list of kanji, plus metadata. |
| `data/compound_words.json` | Optional explicit compound → parts mapping. |
| `data/multiword_phrases.json` | Optional list of multi‑word English phrases. |

### **word_cache.json format (required)**

```json
{
  "我": {
    "count": 42,
    "words": [
      {
        "word": "我慢",
        "meanings": ["patience", "endurance"],
        "frequency": 123,
        "readings": [
          {"kana": "がまん", "ipa": "ɡamaɴ"}
        ]
      }
    ]
  }
}
```

**Important:**  
`readings` **must** be a list of dicts. Old formats trigger a descriptive error.

---

## **3. Weighting Model**

### **Zipf weighting**

\[
\text{weight} = \frac{1}{\text{rank}^{s}}
\]

- `rank` = frequency rank (1 = most common)  
- `s` = Zipf exponent (default `1.0`)  

Words with `frequency = null` are ignored.

### **Normalization**

All token weights are normalized so the sum equals **1.0**.

---

## **4. Meaning Tokenization Pipeline**

Each English meaning string undergoes:

1. Removal of parenthetical content  
2. Multi‑word phrase replacement  
   - e.g., `"bumper crop"` → `"bumper_crop"`
3. Token extraction via regex  
4. Lowercasing + punctuation stripping  
5. Stopword removal  
6. Lemmatization  
   - Uses NLTK WordNet if available  
   - Falls back to a custom heuristic  
7. Compound splitting  
   - Uses explicit `compound_words.json` when available  
   - Otherwise heuristic splitting using known tokens  

---

## **5. Public API**

### **`word_cloud_for_kanji(kanji, ...)`**

```python
word_cloud_for_kanji(
    kanji: str,
    word_cache_path: str = WORD_CACHE,
    stopwords: Optional[Set[str]] = None,
    zipf_exponent: float = 1.0,
    include_sources: bool = False,
) -> Dict[str, object]
```

**Returns:**

- `{ token: weight }`  
- or `{ token: { "weight": w, "ja": [sources...] } }`

Sources may include:

- Japanese word forms  
- Kana readings  
- IPA readings  

---

### **`word_cloud_for_radical(radical_key, ...)`**

```python
word_cloud_for_radical(
    radical_key: str,
    radical_json_path: str = RADICAL_JSON,
    word_cache_path: str = WORD_CACHE,
    stopwords: Optional[Set[str]] = None,
    zipf_exponent: float = 1.0,
    include_sources: bool = False,
) -> Dict[str, object]
```

**Features:**

- Accepts radical **number** or **character**  
- Aggregates per‑kanji clouds  
- Performs global compound splitting using all meanings in the dataset  

---

## **6. Internal Components**

### **Tokenization & Lemmatization**
- `_tokenize_meaning()`  
- `_lemmatize_token()`  
- `_heuristic_lemmatize()`  
- `_apply_multiword_phrases()`

### **Compound Handling**
- `_load_compound_map()`  
- `_split_compound_token()`

### **Weighting**
- `_rank_to_weight()`  
- `_normalize_weights()`

### **Image Generation**
- `_generate_and_save_wordcloud()`  
- `_generate_image_file_path()`

---

## **7. CLI Usage**

Run the script directly:

```bash
python word_cloud.py --kanji 我 --top 40
python word_cloud.py --radical 85 --include-sources
```

### **Arguments**

| Flag | Description |
|------|-------------|
| `--kanji <char>` | Generate cloud for a single kanji. |
| `--radical <key>` | Radical number or radical character. |
| `--top N` | Show top N tokens (`all` or `-1` for all). |
| `--zipf-exponent X` | Adjust Zipf weighting. |
| `--include-sources` | Include Japanese source words/readings. |
| `--image-out [FILE]` | Write PNG to file (requires `wordcloud`). |
| `--image-out-dir [DIR]` | Write PNG into directory. |
| `--image-width/height` | Image dimensions. |
| `--bg-color` | Background color. |
| `--ensure-nltk` | Download WordNet resources and exit. |

### **Example Output (include_sources)**

```
patience    0.142857    我慢,がまん
endure      0.095000    我慢
```

---

## **8. Error Handling**

### **Old-format entries**
If a word entry has non‑list `readings`, the script raises:

- A detailed error showing the offending entry  
- A clear explanation of the expected format  

### **Missing data**
- Unknown kanji → `{}`  
- Unknown radical → `{}`  

---

## **9. Extensibility Notes**

The module is designed for:

- Adding richer lemmatization (spaCy, Stanza)  
- Expanding stopword lists  
- Adding POS‑aware weighting  
- Integrating with phoneme‑confusion models  
- Exporting results to CSV/JSON for visualization  
