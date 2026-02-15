#!/usr/bin/env python3
# debug_full_trace.py
import os
import json
import copy
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter
from calculate_kanjivg_spanning_elements import load_element_stats, load_element_order

# Paths (adjust if needed)
ELEMENT_STATS_PATH = "data/element_stats.json"
KANJIVG_DIR = "data-sources/kanjivg"

KVG_NS = "http://kanjivg.tagaini.net"
KVG_ELEMENT_ATTR = f"{{{KVG_NS}}}element"

# --- Minimal Node class (same shape as in the main script) ---
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
    def to_dict(self):
        return {"element": self.element, "is_path": self.is_path,
                "children": [c.to_dict() for c in self.children]}

# --- Helpers to build dict-tree from ElementTree (for canonicalization) ---
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

def normalize_tree(node):
    if node is None:
        return None
    elem = node.get("element")
    is_path = bool(node.get("is_path", False))
    children_norm = tuple(sorted((normalize_tree(c) for c in node.get("children", [])),
                                 key=lambda x: json.dumps(x, ensure_ascii=False)))
    return (elem, is_path, children_norm)

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

# --- Removal algorithm used in main script (two-phase detach then collapse) ---
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
            stack.append((c, d+1))
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
    if root is None:
        return None, False, []
    matches = find_nodes_with_element(root, target)
    if not matches:
        return root, False, []
    matches_sorted = sorted(matches, key=lambda x: x[1], reverse=True)
    removed_nodes = []
    affected_parents = set()
    removed_any = False
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
    for parent in list(affected_parents):
        if parent.parent is None and parent is not root:
            continue
        if not parent.children:
            collapsed = collapse_upward_if_empty(parent)
            if collapsed:
                removed_any = True
    root, pruned_any = prune_empty_wrappers(root)
    if pruned_any:
        removed_any = True
    if root is not None and not root.children:
        removed_any = True
        removed_nodes.append(root)
        root = None
    return root, removed_any, removed_nodes

# -------------------------
# Main debug flow
# -------------------------
def main():
    print("Loading element stats…")
    element_stats = load_element_stats(ELEMENT_STATS_PATH)

    print("Collecting trees from SVGs for canonicalization…")
    element_trees = defaultdict(list)
    svg_cache = {}
    total_svg_refs = sum(len(s.get("source_files", [])) for s in element_stats.values())
    # iterate all source files referenced in element_stats
    for kanji, stats in element_stats.items():
        for svg_file in stats.get("source_files", []):
            svg_path = os.path.join(KANJIVG_DIR, svg_file)
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
            stack = [full_tree]
            while stack:
                node = stack.pop()
                element_trees[node.get("element")].append((svg_file, copy.deepcopy(node)))
                for c in node["children"]:
                    stack.append(c)

    print("Choosing canonical trees (frequency + simplicity)…")
    canonical = {}
    for elem, trees in element_trees.items():
        normalized = [normalize_tree(t) for _, t in trees]
        freq = Counter(normalized)
        if len(freq) == 0:
            continue
        if len(freq) == 1:
            canonical[elem] = next(iter(freq))
            continue
        max_count = max(freq.values())
        candidates = [form for form, cnt in freq.items() if cnt == max_count]
        if len(candidates) == 1:
            canonical[elem] = candidates[0]
        else:
            # pick simplest by height,size
            def to_tree(n):
                if n is None:
                    return None
                elem, is_path, children = n
                return {"element": elem, "is_path": is_path, "children": [to_tree(c) for c in children]}
            def height_size(form):
                t = to_tree(form)
                def hs(node):
                    if node is None:
                        return -1, 0
                    if node["is_path"] or not node["children"]:
                        return 0, 1
                    ch = [hs(c) for c in node["children"]]
                    return 1 + max(h for h,s in ch), 1 + sum(s for h,s in ch)
                return hs(t)
            canonical[elem] = min(candidates, key=height_size)

    # --- Check 1: print canonical for specific kanji ---
    inspect = ["串", "品", "新", "再"]
    print("\nCHECK 1: canonical normalized forms")
    for k in inspect:
        print("KANJI:", k)
        norm = canonical.get(k)
        if norm is None:
            print("  canonical: MISSING")
        else:
            print("  canonical:", json.dumps(norm, ensure_ascii=False))
    # --- Check 2: denormalize and print Node tree for those kanji ---
    print("\nCHECK 2: denormalize canonical -> Node and parent check")
    def node_to_dict(n):
        if n is None:
            return None
        return {"element": n.element, "is_path": n.is_path, "children": [node_to_dict(c) for c in n.children]}
    for k in inspect:
        print(f"--- {k} ---")
        norm = canonical.get(k)
        if norm is None:
            print(" canonical missing")
            continue
        node = denormalize_to_node(norm)
        print(" denorm:", node_to_dict(node))
        # parent pointer check
        def assert_parents(root):
            if root is None:
                return "root None"
            stack = [root]
            while stack:
                cur = stack.pop()
                for c in cur.children:
                    if c.parent is not cur:
                        return f"Parent pointer broken at child {c.element}"
                    stack.append(c)
            return "parents OK"
        print(" parent check:", assert_parents(node))
    # --- Check 3: run removal for element "口" on denormalized "串" ---
    print("\nCHECK 3: run removal for element '口' on denormalized '串'")
    if "串" in canonical:
        node = denormalize_to_node(canonical["串"])
        print(" before:", node_to_dict(node))
        new_root, removed_any, removed_nodes = remove_all_matches_then_collapse(node, "口", debug=True)
        print(" removed_any:", removed_any)
        print(" removed_nodes elements:", [n.element for n in removed_nodes])
        print(" after:", None if new_root is None else node_to_dict(new_root))
    else:
        print(" canonical for 串 missing; cannot run check 3")
    # --- Check 4: ensure no Node roots are shared among kanji ---
    print("\nCHECK 4: detect shared root objects among denormalized kanji")
    kanji_norm_map = {k: v for k,v in canonical.items() if k in element_stats and element_stats[k].get("is_kanji")}
    kanji_trees = {k: denormalize_to_node(v) for k,v in kanji_norm_map.items()}
    seen = {}
    duplicates = []
    for k, root in kanji_trees.items():
        rid = id(root)
        if rid in seen:
            duplicates.append((k, seen[rid]))
        else:
            seen[rid] = k
    print(" duplicates:", duplicates)
    # --- Check 5: trace first few elements and debug only for 串 and 品 ---
    print("\nCHECK 5: trace first 30 elements, debug for 串 and 品")
    element_order = load_element_order(ELEMENT_STATS_PATH.replace("element_stats.json", "element_freq.csv")) if False else load_element_order("data/element_freq.csv")
    trace_kanji = {"串", "品"}
    # build local working map for a subset (only those in canonical)
    working_map = {k: denormalize_to_node(v) for k,v in kanji_norm_map.items() if k in trace_kanji}
    for i, elem in enumerate(element_order[:30], start=1):
        print(f"\n=== element {i}: {elem} ===")
        for k in list(working_map.keys()):
            node = working_map[k]
            new_root, removed, removed_nodes = remove_all_matches_then_collapse(node, elem, debug=True)
            working_map[k] = new_root
            if removed:
                print(f"  {k}: removed {[n.element for n in removed_nodes]} -> root now {None if new_root is None else node_to_dict(new_root)}")
    print("\nDone checks.")

if __name__ == "__main__":
    main()
