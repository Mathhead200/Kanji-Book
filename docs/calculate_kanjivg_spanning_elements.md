### Overview

A deterministic structural coverage planner that builds a greedy element coverage plan from KanjiVG SVGs. It selects canonical tree shapes for elements, prefers full-root kanji SVGs when available, and simulates removing element `<g>` groups from kanji trees to compute which element first “consumes” each kanji. The program writes a ragged CSV describing the order in which elements cover kanji.

**Key features**
- Canonicalization that prefers the full SVG root for kanji.
- Two-phase removal algorithm: detach matching `<g>` nodes deepest-first, then collapse empty parents.
- Final cleanup pass to prune empty wrapper groups.
- Two run modes: **full** (all kanji) and **joyo** (restricted to a provided Joyo CSV).
- Optional per-kanji debug and optional verbose diagnostics.

---

### Installation and Requirements

**Requirements**
- Python 3.8+
- Standard library modules: `json`, `csv`, `argparse`, `xml.etree.ElementTree`, `collections`, `copy`
- Third-party: `tqdm` (progress bars)

**Files expected in repository**
- `data/element_stats.json` — element metadata and source SVG references
- `data/element_freq.csv` — element frequency order
- `data-sources/kanjivg/` — KanjiVG SVG files referenced by `element_stats.json`
- `calculate_kanjivg_spanning_elements.py` — helper functions (or renamed helper module)
- `element_coverage_plan.py` — main program (CLI)

**Install**
```bash
python -m pip install tqdm
```

---

### Usage and CLI Options

**Command line**
```bash
python element_coverage_plan.py --mode full
python element_coverage_plan.py --mode joyo --joyo-file "data/2242KANJIFREQUENCYLISTVER.1.1 - MAIN.csv"
```

**Options**
- `--mode` `full|joyo` — run mode; default `full`.
- `--joyo-file` — CSV file listing Joyo kanji (one kanji per row, first column). Used when `--mode joyo`.
- `--output` — output CSV path (default `data/element_coverage_plan.csv`).
- `--debug-kanji` — list of kanji to enable per-kanji debug prints.
- `--verbose` — print tree conflict diagnostics during canonical selection.

**Mode comparison**

| Mode | Purpose | Input filter | Performance |
|---|---:|---|---:|
| **full** | Cover all kanji referenced in `element_stats` | None | Processes entire dataset (largest runtime) |
| **joyo** | Restrict coverage to Joyo kanji list | Requires `--joyo-file` CSV | Faster; parses only SVGs for filtered kanji |

---

### Internals and Algorithm

**Canonical selection**
- Collects every subtree observed across all SVGs and normalizes them.
- If an element is a kanji and a full-root SVG exists for that kanji, the program prefers the normalized full-root form as canonical.
- Fallback: choose the most common normalized form; if tied, choose the most complex (largest height then size).

**Tree representation**
- Canonical trees are normalized tuples `(element, is_path, children_norm)`.
- Canonical normalized forms are denormalized into `Node` objects with `element`, `is_path`, `children`, and `parent` pointers.

**Removal algorithm (per element)**
1. **Collect matches**: find all `<g>` nodes whose `element` equals the processed element.
2. **Detach matches**: remove all matches deepest-first without collapsing parents.
3. **Collapse parents**: for each parent of a detached node, if it has no children, collapse upward recursively (detach empty parents).
4. **Final cleanup**: prune any remaining empty wrapper `<g>` nodes (non-path groups with zero children).
5. **Root consumption**: if the kanji root is removed, mark the kanji as consumed for the current element and record it in the CSV row.

**Output**
- A ragged CSV where each row corresponds to an element that pruned at least one kanji.
- Columns include: `order`, `element`, `is_kanji`, `is_kangxi_radical`, `pruned_kanji_count`, `new_kanji_count`, `cumulative_covered`, `remaining_kanji`, followed by `kanji_1`, `kanji_2`, ...

---

### Debugging and Diagnostics

**Flags**
- `--debug-kanji` prints per-kanji removal traces (removed nodes and new root) for the listed kanji.
- `--verbose` prints tree conflict diagnostics during canonical selection (only when requested).

**Common checks**
- If a kanji collapses earlier than expected:
  - Run with `--debug-kanji <kanji>` to see which nodes were removed and when.
  - Use `--verbose` to see canonicalization diagnostics and confirm the canonical form used for that kanji.
- If you see import errors referencing `calculate_kanjivg_spanning_elements`, ensure the helper module is not shadowing the main script name. Rename the helper module (e.g., `kanjivg_utils.py`) and update imports.

**Suggested quick debug commands**
```bash
# Verbose canonical diagnostics
python element_coverage_plan.py --mode full --verbose

# Debug specific kanji
python element_coverage_plan.py --mode joyo --joyo-file "data/2242KANJIFREQUENCYLISTVER.1.1 - MAIN.csv" --debug-kanji 串 品
```

---

### Examples and Notes

**Run full coverage**
```bash
python element_coverage_plan.py --mode full --output data/element_coverage_plan_full.csv
```

**Run Joyo coverage**
```bash
python element_coverage_plan.py --mode joyo --joyo-file "data/2242KANJIFREQUENCYLISTVER.1.1 - MAIN.csv" --output data/element_coverage_plan_joyo.csv
```

**Interpreting the CSV**
- Each row corresponds to an element that pruned at least one kanji.
- `pruned_kanji_count` counts kanji whose trees changed when that element was processed.
- `new_kanji_count` counts kanji that became fully consumed at that element (first time they are covered).
- `cumulative_covered` is the running total of consumed kanji.

**Extensibility**
- Canonical selection strategy and tie-breakers are centralized in `choose_canonical_trees` and can be adjusted (for example, prefer simplest instead of most complex).
- The `remove_all_matches_then_collapse` function encapsulates the removal logic and is a single place to modify collapse rules.
