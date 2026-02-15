# Quick Start Guide

## Installation

```bash
# Install dependencies
pip install nltk

# Optional: for word cloud images
pip install wordcloud pillow numpy

# Download NLTK resources
python scripts/word_cloud_v3.py --ensure-nltk
```

## Basic Usage

```bash
# Test on radical 口 (mouth)
python scripts/word_cloud_v3.py --radical 口 --top 20

# With Japanese source words
python scripts/word_cloud_v3.py --radical 口 --top 20 --include-sources

# Save to file
python scripts/word_cloud_v3.py --radical 口 --top 40 --out results/mouth.txt

# Generate image
python scripts/word_cloud_v3.py --radical 口 --top 40 --image-out results/mouth.png
```

## Command Line Options Summary

### Required (pick one)
- `--kanji 漢` - Single kanji
- `--radical 1` or `--radical 口` - Radical by number or character  
- `--element key` - KanjiVG element

### Common Options
- `--top N` - Show top N words (default 40, use "all" for everything)
- `--include-sources` - Show Japanese source words
- `--out FILE.txt` - Save results to text file
- `--image-out FILE.png` - Generate word cloud image

### Weighting Control
- `--zipf-exponent 1.0` - Adjust Japanese word frequency weighting (default 1.0)
- `--no-tfidf` - Disable TF-IDF, use Zipf only
- `--no-synonyms` - Disable synonym grouping
- `--max-synonyms 2` - Allow 2 representatives per synonym group (default 1)

### Tokenization Control
- `--no-pos-filter` - Keep all word types (not just nouns/verbs/adjectives)
- `--no-dict-validate` - Skip English dictionary validation
- `--dictionary wordlist.txt` - Use custom word list
- `--min-length 4` - Minimum token length (default 3)

## Expected Output Format

### Default (with synonym grouping)
```
# word cloud top 20 for radical 口
# token    weight    [synset_cluster]    (sources)
mouth     0.025431  [mouth,oral_cavity,maw]         口,くち,こう,...
speak     0.018234  [speak,talk,utter,say,tell]     言う,話す,述べる,...
eat       0.015678  [eat,consume,ingest,devour]     食べる,喰う,頂く,...
voice     0.012456  [voice,vocalization]            声,音声,...
taste     0.011234  [taste,flavor,savor]            味,味わう,...
```

### Without synonym grouping
```
# word cloud top 20 for radical 口
# token    weight    (sources)
mouth     0.025431  口,くち,こう,...
speak     0.018234  言う,話す,述べる,...
oral      0.016789  口腔,口の,...
talk      0.015234  話す,話,談話,...
```

## Verifying It Works

### Test 1: No Fragments
```bash
python scripts/word_cloud_v3.py --radical 口 --top 40 | grep -E "(ion|ese|ness|ical)$"
```
**Expected**: Should find nothing (no fragments)

### Test 2: No Generic Words
```bash
python scripts/word_cloud_v3.py --radical 口 --top 40 | grep -E "^(one|make|take|get)\s"
```
**Expected**: Should find nothing (generic words filtered)

### Test 3: Real English Words
```bash
python scripts/word_cloud_v3.py --radical 口 --top 40
```
**Expected**: All tokens should be recognizable English words related to "mouth" semantic field

## Troubleshooting

### Error: "Could not load NLTK words corpus"
```bash
python -c "import nltk; nltk.download('words')"
```

### Error: "POS tagger unavailable"
```bash
python -c "import nltk; nltk.download('averaged_perceptron_tagger')"
```

### Error: "Could not load WordNet"
```bash
python -c "import nltk; nltk.download('wordnet'); nltk.download('omw-1.4')"
```

### Still seeing "ion", "ese", "ness" fragments
Make sure you're NOT using these flags:
- ❌ `--no-pos-filter`
- ❌ `--no-dict-validate`

### Too few results
Try lowering minimum length:
```bash
python scripts/word_cloud_v3.py --radical 口 --min-length 2
```

## Testing Different Radicals

```bash
# Water radical (水)
python scripts/word_cloud_v3.py --radical 氵 --top 30

# Tree radical (木)  
python scripts/word_cloud_v3.py --radical 木 --top 30

# Fire radical (火)
python scripts/word_cloud_v3.py --radical 火 --top 30

# Person radical (人)
python scripts/word_cloud_v3.py --radical 亻 --top 30
```

## File Locations

After running, check:
- Text outputs: Location specified in `--out` or `--out-dir`
- Images: Location specified in `--image-out` or `--image-out-dir`
- NLTK data: `~/.nltk_data/` (or project `.nltk_ready` sentinel)

## Next Steps

1. **Test on your favorite kanji/radical** to see results
2. **Compare with original output** to verify improvements
3. **Adjust parameters** if needed (see IMPLEMENTATION_GUIDE.md)
4. **Report any issues** - particularly if you still see fragments or generic words

## Performance Notes

- First run: Slower (downloads NLTK data)
- Subsequent runs: Faster (cached resources)
- Large radicals (100+ kanji): May take 10-30 seconds
- POS tagging adds ~2-3 seconds per run

## Getting Help

See `IMPLEMENTATION_GUIDE.md` for:
- Detailed architecture explanation
- Advanced configuration
- Troubleshooting guide
- Research background
