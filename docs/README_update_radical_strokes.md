What this does
----------------

- Script: `scripts/update_radical_strokes.py` — fetches stroke counts for the 214 Kangxi radicals from Wikipedia and updates `data/radical_data.json`.
- By default the script performs a dry run; use `--apply` to change the file. It will create a timestamped backup before writing.

Sources you can use
-------------------

1. Wikipedia (programmatic access)
   - Page: https://en.wikipedia.org/wiki/Kangxi_radicals
   - The script scrapes the main Kangxi radicals table (the one labeled "Table" on the page) to get radical numbers and stroke counts.
   - Pros: straightforward, includes radical number and stroke counts in one table.
   - Con: scraping public pages should be polite and include a User-Agent (the script already sets one).

2. Unicode / Unihan (recommended for character-level RS data)
   - Download: https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip
   - Files of interest inside the zip:
     - `Unihan_DictionaryLikeData.txt` (contains per-character properties like `kRSKangXi` and `kTotalStrokes`)
     - `RSIndex.txt` (radical-stroke index maps radicals to code points)
   - Use-case: If you need per-character radical+residual-stroke info or to cross-check radical assignments for kanji, Unihan is authoritative and machine-friendly.

3. Additional projects
   - `kanjivg` for radical glyphs and variants: https://github.com/kanjivg/kanjivg
   - `cjkradlib` (PyPI) for decomposition/IDS based data: https://pypi.org/project/cjkradlib/

How the script works
---------------------

1. Fetches the Kangxi radicals table from Wikipedia (using a safe User-Agent header).
2. Parses each row and extracts: radical number and stroke count (as integer).
3. Loads `data/radical_data.json`, and for each radical key (string of the number) replaces `stroke_count` with the newly fetched integer.
4. If `--apply` is used, it creates a timestamped backup in `data/` and writes the updated JSON.

Running locally
---------------

1. Install dependencies (if needed):

    pip install requests beautifulsoup4

2. Dry run (shows proposed updates):

    python scripts/update_radical_strokes.py

3. Apply updates (creates backup and writes file):

    python scripts/update_radical_strokes.py --apply

Notes & next steps
------------------

- If you prefer not to scrape Wikipedia, you can generate the same mapping by processing `Unihan.zip` and/or a trusted CSV with radical stroke counts.
- If you want the script to also populate derived data (e.g., per-kanji total strokes using Unihan's `kTotalStrokes`), I can extend it to download and use `Unihan_DictionaryLikeData.txt` as a next step.
