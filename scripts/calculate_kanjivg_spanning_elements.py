#!/usr/bin/env python3
"""
element_coverage_plan.py

Deterministic structural coverage planner with improved canonical selection
and two run modes:

  --full    : build coverage over the full kanji set referenced in element_stats
  --joyo    : restrict coverage to the kanji listed in a provided Joyo CSV

Add --verbose to print tree conflict diagnostics.
"""
import os
import sys
import json
import csv
import argparse
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter
from tqdm import tqdm
from copy import deepcopy

ELEMENT_STATS_PATH = "data/element_stats.json"
ELEMENT_FREQ_PATH = "data/element_freq.csv"
KANJIVG_DIR = "data-sources/kanjivg"
OUTPUT_CSV_PATH = "data/element_coverage_plan.csv"

KVG_NS = "http://kanjivg.tagaini.net"
KVG_ELEMENT_ATTR = f"{{{KVG_NS}}}element"

# Debug toggle for specific kanji (empty by default)
DEBUG_KANJI = set()


# ------------------------------------------------------------
# 1. Load element_stats.json
# ------------------------------------------------------------
def load_element_stats(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------
# 3. Load element frequency order
# ------------------------------------------------------------
def load_element_order(path):
    order = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            order.append(row["element"])
    return order


# ---------------------------------------------------------------------
# Node model with parent pointers
# ---------------------------------------------------------------------
class Node:
    __slots__ = ("element", "is_path", "children", "parent")

    def __init__(self, element=None, is_path=False):
        self.element = element
        self.is_path = bool(is_path)
        self.children = []
        self.parent = None

    def add_child(self, child):
        child.parent = self
        self.children.append(child)

    def detach_from_parent(self):
        if self.parent is None:
            return
        try:
            self.parent.children.remove(self)
        except ValueError:
            pass
        self.parent = None

    def has_children(self):
        return len(self.children) > 0

    def to_dict(self):
        return {
            "element": self.element,
            "is_path": self.is_path,
            "children": [c.to_dict() for c in self.children]
        }


# ---------------------------------------------------------------------
# Normalization utilities
# ---------------------------------------------------------------------
def normalize_tree(node):
    if node is None:
        return None
    elem = node.get("element")
    is_path = bool(node.get("is_path", False))
    children_norm = tuple(
        sorted(
            (normalize_tree(c) for c in node.get("children", [])),
            key=lambda x: json.dumps(x, ensure_ascii=False)
        )
    )
    return (elem, is_path, children_norm)


def compute_height_and_size(node):
    """Return (height, size) of a dict-like tree node."""
    if node is None:
        return -1, 0
    if node.get("is_path", False) or not node.get("children"):
        return 0, 1
    child_vals = [compute_height_and_size(c) for c in node["children"]]
    heights = [h for h, s in child_vals]
    sizes = [s for h, s in child_vals]
    return 1 + max(heights), 1 + sum(sizes)


def denormalize_to_node(norm):
    if norm is None:
        return None
    elem, is_path, children = norm
    n = Node(element=elem, is_path=is_path)
    for c in children:
        child_node = denormalize_to_node(c)
        if child_node is not None:
            n.add_child(child_node)
    return n


# ---------------------------------------------------------------------
# SVG parsing -> dict tree (for canonicalization)
# ---------------------------------------------------------------------
def find_root_group(svg_root):
    for g in svg_root.iter():
        if g.tag.endswith("g") and g.get(KVG_ELEMENT_ATTR) is not None:
            return g
    return None


def build_dict_tree(et_node):
    tag = et_node.tag.split("}")[-1]
    if tag == "path":
        return {"element": None, "is_path": True, "children": []}
    elem = et_node.get(KVG_ELEMENT_ATTR)
    children = []
    for child in et_node:
        child_tag = child.tag.split("}")[-1]
        if child_tag in ("g", "path"):
            children.append(build_dict_tree(child))
    return {"element": elem, "is_path": False, "children": children}


def build_node_tree_from_et(et_node):
    tag = et_node.tag.split("}")[-1]
    if tag == "path":
        return Node(element=None, is_path=True)
    elem = et_node.get(KVG_ELEMENT_ATTR)
    n = Node(element=elem, is_path=False)
    for child in et_node:
        child_tag = child.tag.split("}")[-1]
        if child_tag in ("g", "path"):
            child_node = build_node_tree_from_et(child)
            n.add_child(child_node)
    return n


# ---------------------------------------------------------------------
# Load all trees and full-root trees (optionally restricted to a kanji set)
# ---------------------------------------------------------------------
def load_all_trees(element_stats, kanji_filter=None):
    """
    Returns:
      element_trees: dict element -> list of (svg_file, dict_tree_subtree)
      full_tree_by_kanji: dict kanji -> list of (svg_file, dict_tree_full_root)

    If kanji_filter is provided (set of kanji), only SVGs whose root element
    is in that set are recorded for full_tree_by_kanji and only subtrees from
    those SVGs are added to element_trees. This reduces parsing when running
    in restricted modes.
    """
    element_trees = defaultdict(list)
    full_tree_by_kanji = defaultdict(list)
    svg_cache = {}

    total_svg_refs = sum(len(stats.get("source_files", [])) for stats in element_stats.values())

    with tqdm(total=total_svg_refs, desc="Parsing SVG files", unit="svg") as pbar:
        for kanji, stats in element_stats.items():
            for svg_file in stats.get("source_files", []):
                svg_path = os.path.join(KANJIVG_DIR, svg_file)
                pbar.update(1)

                if not os.path.exists(svg_path):
                    continue

                if svg_path not in svg_cache:
                    try:
                        tree = ET.parse(svg_path)
                        svg_cache[svg_path] = tree.getroot()
                    except ET.ParseError:
                        continue

                root = svg_cache[svg_path]
                root_group = find_root_group(root)
                if root_group is None:
                    continue

                full_tree = build_dict_tree(root_group)

                # Record full root tree for the kanji element of this SVG
                root_elem = root_group.get(KVG_ELEMENT_ATTR)
                if root_elem:
                    # If a filter is provided, only record full-root trees for kanji in the filter
                    if kanji_filter is None or root_elem in kanji_filter:
                        full_tree_by_kanji[root_elem].append((svg_file, deepcopy(full_tree)))

                # Walk and record every subtree. If a filter is provided, only record
                # subtrees for SVGs whose root element is in the filter (to keep behavior consistent).
                if kanji_filter is None or (root_group.get(KVG_ELEMENT_ATTR) in kanji_filter):
                    stack = [full_tree]
                    while stack:
                        node = stack.pop()
                        element_trees[node.get("element")].append((svg_file, deepcopy(node)))
                        for c in node["children"]:
                            stack.append(c)

    return element_trees, full_tree_by_kanji


# ---------------------------------------------------------------------
# Choose canonical trees with preference for full-root kanji SVGs
# ---------------------------------------------------------------------
def choose_canonical_trees(element_trees, full_tree_by_kanji, element_stats, verbose=False):
    canonical = {}
    diagnostics = {}

    for elem, trees in tqdm(element_trees.items(), desc="Selecting canonical trees", unit="elem"):
        # Normalize observed trees
        normalized = [(src, normalize_tree(t)) for src, t in trees]
        observed_norms = [norm for src, norm in normalized]

        # If this element is a kanji and we have full-root trees for it,
        # prefer a normalized form that equals one of those full-root forms.
        if element_stats.get(elem, {}).get("is_kanji", False):
            own_full_norms = []
            for svg_file, full_tree in full_tree_by_kanji.get(elem, []):
                own_full_norms.append(normalize_tree(full_tree))
            # If any full-root normalized form is present among observed norms, pick it
            for full_norm in own_full_norms:
                if full_norm in observed_norms:
                    canonical[elem] = full_norm
                    break
            if elem in canonical:
                continue

        # Frequency-based selection
        freq = Counter(observed_norms)

        # If only one form exists → choose it
        if len(freq) == 1:
            canonical_form = next(iter(freq))
            canonical[elem] = canonical_form
            continue

        # Diagnostics for conflicts
        diagnostics[elem] = {
            "forms": {},
            "message": f"Element {elem} has {len(freq)} conflicting tree representations."
        }
        for src, norm in normalized:
            diagnostics[elem]["forms"].setdefault(json.dumps(norm, ensure_ascii=False), []).append(src)

        # Choose canonical form:
        # 1) Most common
        max_count = max(freq.values())
        candidates = [form for form, count in freq.items() if count == max_count]

        if len(candidates) == 1:
            canonical_form = candidates[0]
        else:
            # 2) Tie → pick most complex (largest height, then largest size)
            def complexity(form):
                # Convert normalized form back to dict-like tree for compute_height_and_size
                def to_tree(n):
                    if n is None:
                        return None
                    elem, is_path, children = n
                    return {"element": elem, "is_path": is_path, "children": [to_tree(c) for c in children]}
                tree = to_tree(form)
                h, s = compute_height_and_size(tree)
                # We want largest height then largest size
                return (h, s)
            canonical_form = max(candidates, key=complexity)

        canonical[elem] = canonical_form

    # Print diagnostics only if verbose requested
    if verbose and diagnostics:
        print("\n=== TREE CONFLICT DIAGNOSTICS ===")
        for elem, info in diagnostics.items():
            print(info["message"])
            for form, sources in info["forms"].items():
                print(f"  Form: {form}")
                print(f"    Sources: {sources}")
        print("=== END DIAGNOSTICS ===\n")

    return canonical


# ---------------------------------------------------------------------
# Removal algorithm: two-phase detach then collapse, with final cleanup
# ---------------------------------------------------------------------
def find_nodes_with_element(root, target):
    if root is None:
        return []
    out = []
    stack = [(root, 0)]
    while stack:
        cur, d = stack.pop()
        if cur.element == target:
            out.append((cur, d))
        for c in cur.children:
            stack.append((c, d + 1))
    return out


def collapse_upward_if_empty(node):
    removed_any = False
    cur = node
    while cur is not None and cur.parent is not None:
        parent = cur.parent
        if parent.children:
            break
        parent.detach_from_parent()
        removed_any = True
        cur = parent
    return removed_any


def prune_empty_wrappers(root):
    if root is None:
        return None, False
    removed_any = False
    while True:
        to_remove = []
        stack = [root]
        while stack:
            n = stack.pop()
            if n.is_path:
                continue
            for c in n.children:
                stack.append(c)
            if not n.children and n is not root:
                to_remove.append(n)
        if not to_remove:
            break
        removed_any = True
        for n in to_remove:
            n.detach_from_parent()
    if root is not None and not root.children:
        return None, True
    return root, removed_any


def remove_all_matches_then_collapse(root, target, debug=False):
    """
    1) Find all nodes with element == target.
    2) Detach all matches (deepest-first), record affected parents.
    3) For each affected parent, if it has no children, collapse upward recursively.
    4) Final cleanup pass to prune empty wrapper groups.
    5) Return (new_root_or_None, removed_any_bool, removed_nodes_list).
    """
    if root is None:
        return None, False, []

    matches = find_nodes_with_element(root, target)
    if not matches:
        return root, False, []

    matches_sorted = sorted(matches, key=lambda x: x[1], reverse=True)
    removed_nodes = []
    affected_parents = set()
    removed_any = False

    # Detach all matches deepest-first
    for node, depth in matches_sorted:
        if root is None:
            break
        if node is root:
            removed_nodes.append(node)
            removed_any = True
            root = None
            break
        if node.parent is None:
            continue
        parent = node.parent
        node.detach_from_parent()
        removed_nodes.append(node)
        removed_any = True
        affected_parents.add(parent)

    # Collapse upward from each affected parent if empty
    for parent in list(affected_parents):
        if parent.parent is None and parent is not root:
            continue
        if not parent.children:
            collapsed = collapse_upward_if_empty(parent)
            if collapsed:
                removed_any = True

    # Final cleanup pass
    root, pruned_any = prune_empty_wrappers(root)
    if pruned_any:
        removed_any = True

    # Final root-empty check
    if root is not None and not root.children:
        removed_any = True
        removed_nodes.append(root)
        root = None

    if debug and removed_nodes:
        return root, removed_any, removed_nodes

    return root, removed_any, removed_nodes


# ---------------------------------------------------------------------
# Structural greedy coverage loop
# ---------------------------------------------------------------------
def structural_coverage(element_stats, canonical_trees, element_order, kanji_filter=None):
    # Build kanji -> normalized mapping for kanji only, with fallback to first SVG full root
    kanji_norm_map = {}
    for k, s in element_stats.items():
        if not s.get("is_kanji", False):
            continue
        # If a kanji_filter is provided, skip kanji not in the filter
        if kanji_filter is not None and k not in kanji_filter:
            continue
        if k in canonical_trees:
            kanji_norm_map[k] = canonical_trees[k]
        else:
            # fallback: try to build from the first source SVG for this kanji
            built = None
            for src in s.get("source_files", []):
                svg_path = os.path.join(KANJIVG_DIR, src)
                if not os.path.exists(svg_path):
                    continue
                try:
                    tree = ET.parse(svg_path)
                    root = tree.getroot()
                    root_group = find_root_group(root)
                    if root_group is None:
                        continue
                    dict_tree = build_dict_tree(root_group)
                    built = normalize_tree(dict_tree)
                    break
                except ET.ParseError:
                    continue
            if built is not None:
                kanji_norm_map[k] = built

    # Convert normalized forms into fresh Node trees
    kanji_trees = {k: denormalize_to_node(t) for k, t in kanji_norm_map.items()}

    remaining = set(kanji_trees.keys())
    covered = set()
    plan = []
    order_num = 1

    for elem in tqdm(element_order, desc="Running structural coverage", unit="elem"):
        new_kanji = []
        pruned_kanji_count = 0

        for k in list(remaining):
            tree = kanji_trees.get(k)
            debug_flag = k in DEBUG_KANJI
            new_tree, removed, removed_nodes = remove_all_matches_then_collapse(tree, elem, debug=debug_flag)
            kanji_trees[k] = new_tree

            if removed:
                pruned_kanji_count += 1
                if new_tree is None:
                    new_kanji.append(k)
                    remaining.remove(k)
                    covered.add(k)

                if debug_flag:
                    removed_elems = [n.element for n in removed_nodes]
                    print(f"\nDEBUG: element {elem} pruned from kanji {k}")
                    print(f"  removed nodes: {removed_elems}")
                    print(f"  new root: {None if new_tree is None else new_tree.to_dict()}")

        if pruned_kanji_count == 0:
            continue

        row = {
            "order": order_num,
            "element": elem,
            "is_kanji": bool(element_stats.get(elem, {}).get("is_kanji", False)),
            "is_kangxi_radical": bool(element_stats.get(elem, {}).get("is_kangxi_radical_char", False)),
            "pruned_kanji_count": pruned_kanji_count,
            "new_kanji_count": len(new_kanji),
            "cumulative_covered": len(covered),
            "remaining_kanji": len(remaining),
            "new_kanji": new_kanji,
        }
        plan.append(row)
        order_num += 1

        if not remaining:
            break

    return plan


# ---------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------
def write_ragged_csv(plan, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    max_len = max((len(r["new_kanji"]) for r in plan), default=0)

    fieldnames = [
        "order",
        "element",
        "is_kanji",
        "is_kangxi_radical",
        "pruned_kanji_count",
        "new_kanji_count",
        "cumulative_covered",
        "remaining_kanji",
    ] + [f"kanji_{i+1}" for i in range(max_len)]

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=",", extrasaction="ignore")
        writer.writeheader()
        for row in plan:
            flat = {k: row.get(k, "") for k in fieldnames}
            for i in range(max_len):
                key = f"kanji_{i+1}"
                flat[key] = row["new_kanji"][i] if i < len(row["new_kanji"]) else ""
            writer.writerow(flat)


# ---------------------------------------------------------------------
# Utility: load Joyo kanji set from CSV (expects a CSV with kanji in first column)
# ---------------------------------------------------------------------
def load_joyo_set(csv_path):
    joyo = set()
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Joyo CSV not found: {csv_path}")
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            # assume the kanji character is in the first column; strip whitespace
            kanji = row[0].strip()
            if kanji:
                joyo.add(kanji)
    return joyo


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(description="Build element coverage plan (--full or --joyo).")
    parser.add_argument("--mode", choices=("full", "joyo"), default="full",
                        help="Run mode: 'full' uses all kanji; 'joyo' restricts to Joyo list.")
    parser.add_argument("--joyo-file", default="data/2242KANJIFREQUENCYLISTVER.1.1 - MAIN.csv",
                        help="CSV file listing Joyo kanji (one kanji per row, first column).")
    parser.add_argument("--output", default=OUTPUT_CSV_PATH, help="Output CSV path.")
    parser.add_argument("--debug-kanji", nargs="*", default=[], help="List of kanji to enable debug for.")
    parser.add_argument("--verbose", action="store_true", help="Print tree conflict diagnostics.")
    args = parser.parse_args(argv)

    global DEBUG_KANJI
    DEBUG_KANJI = set(args.debug_kanji)

    print("Loading element stats…")
    element_stats = load_element_stats(ELEMENT_STATS_PATH)

    # Determine kanji filter based on mode
    kanji_filter = None
    if args.mode == "joyo":
        print(f"Loading Joyo kanji list from {args.joyo_file} …")
        try:
            joyo_set = load_joyo_set(args.joyo_file)
        except Exception as e:
            print(f"Error loading Joyo file: {e}", file=sys.stderr)
            sys.exit(1)
        # Only keep kanji that appear in element_stats and in the joyo set
        kanji_filter = {k for k in element_stats.keys() if k in joyo_set and element_stats.get(k, {}).get("is_kanji", False)}
        print(f"Joyo mode: restricting to {len(kanji_filter)} kanji from Joyo list.")
    else:
        print("Full mode: using all kanji referenced in element_stats.")

    print("Collecting all tree representations (may be restricted by mode)…")
    all_trees, full_tree_by_kanji = load_all_trees(element_stats, kanji_filter=kanji_filter)

    print("Selecting canonical trees (prefer full-root kanji SVGs)…")
    canonical = choose_canonical_trees(all_trees, full_tree_by_kanji, element_stats, verbose=args.verbose)

    print("Loading element frequency order…")
    element_order = load_element_order(ELEMENT_FREQ_PATH)

    print("Running structural coverage…")
    plan = structural_coverage(element_stats, canonical, element_order, kanji_filter=kanji_filter)

    print(f"Writing output to {args.output}")
    write_ragged_csv(plan, args.output)

    print("Done.")


if __name__ == "__main__":
    main()
