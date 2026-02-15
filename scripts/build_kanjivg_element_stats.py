#!/usr/bin/env python3
import os
import glob
import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from tqdm import tqdm
from CJK_TO_KANGXI import CJK_TO_KANGXI

KANJIVG_DIR = "data-sources/kanjivg/*.svg"
KANJI_DATA_PATH = "data/kanji_data.json"
RADICAL_DATA_PATH = "data/radical_data.json"
OUTPUT_JSON = "data/element_stats.json"

SVG_NS = "http://www.w3.org/2000/svg"
KVG_NS = "http://kanjivg.tagaini.net"
KVG_ELEMENT_ATTR = f"{{{KVG_NS}}}element"
KVG_POSITION_ATTR = f"{{{KVG_NS}}}position"

def load_kanji_data(path):
	with open(path, "r", encoding="utf-8") as f:
		return json.load(f)

def load_radical_data(path):
    with open(path, "r", encoding="utf-8") as f:
        radical_data = json.load(f)

    radical_chars = set()          # canonical Kangxi radicals
    radical_kanji_map = defaultdict(set)

    for rid, info in radical_data.items():
        kangxi = info.get("radical_char")  # e.g. "⼾"
        if kangxi:
            radical_chars.add(kangxi)
            radical_kanji_map[kangxi].add(rid)

        # Also map all kanji listed under this radical
        for k in info.get("kanji", []):
            radical_kanji_map[k].add(rid)

    return radical_data, radical_chars, radical_kanji_map

def find_root_group(svg_root):
	# First <g> with kvg:element is treated as the kanji root
	for g in svg_root.iter(f"{{{SVG_NS}}}g"):
		if g.get(KVG_ELEMENT_ATTR) is not None:
			return g
	return None

def count_strokes_in_subtree(group):
	"""Count all <path> elements in a group's subtree"""
	stroke_count = 0
	for elem in group.iter(f"{{{SVG_NS}}}path"):
		stroke_count += 1
	return stroke_count

def collect_element_stats():
	kanji_data = load_kanji_data(KANJI_DATA_PATH)
	radical_data, radical_chars, radical_kanji_map = load_radical_data(RADICAL_DATA_PATH)

	element_stats = {}
	# For counting in how many distinct kanji each element appears
	element_kanji_set = defaultdict(set)

	svg_files = sorted(glob.glob(KANJIVG_DIR))
	print(f"Found {len(svg_files)} SVG files")

	for svg_path in tqdm(svg_files, desc="Processing KanjiVG SVGs"):
		try:
			tree = ET.parse(svg_path)
		except ET.ParseError as e:
			print(f"Parse error in {svg_path}: {e}")
			continue

		root = tree.getroot()
		root_group = find_root_group(root)
		if root_group is None:
			continue

		kanji_literal = root_group.get(KVG_ELEMENT_ATTR)
		if not kanji_literal:
			continue

		# Per-file set of elements to later count distinct kanji per element
		elements_in_this_kanji = set()

		def traverse(group, depth):
			elem_name = group.get(KVG_ELEMENT_ATTR)

			# If this group has no element, just recurse into children
			if elem_name is None:
				max_child_height = 0
				for child in group:
					if child.tag == f"{{{SVG_NS}}}g":
						h = traverse(child, depth)
						max_child_height = max(max_child_height, h)
				return max_child_height

			# Initialize stats record if needed
			if elem_name not in element_stats:
				element_stats[elem_name] = {
					"element": elem_name,
					"total_occurrences": 0,
					"kanji_count": 0,
					"depths": set(),
					"as_root": False,
					"as_child": False,
					"leaf_occurrences": 0,
					"internal_occurrences": 0,
					"child_element_count_min": None,
					"child_element_count_max": None,
					"max_depth_seen": 0,
					"is_kanji": False,
					"is_kangxi_radical_char": False,
					"kangxi_radical_ids": set(),
					"source_files": set(),
					"heights": set(),
					"stroke_counts": set(),
					"positions": defaultdict(int),
				}

			stats = element_stats[elem_name]
			stats["total_occurrences"] += 1
			stats["depths"].add(depth)
			stats["max_depth_seen"] = max(stats["max_depth_seen"], depth)
			stats["source_files"].add(os.path.basename(svg_path))

			if group is root_group and elem_name == kanji_literal:
				stats["as_root"] = True
			else:
				stats["as_child"] = True

			# Count strokes in this element's subtree
			stroke_count = count_strokes_in_subtree(group)
			stats["stroke_counts"].add(stroke_count)

			# Track position if present
			position = group.get(KVG_POSITION_ATTR)
			if position:
				stats["positions"][position] += 1

			# Collect child element groups
			child_elements = [
				child for child in group
				if child.tag == f"{{{SVG_NS}}}g" and child.get(KVG_ELEMENT_ATTR) is not None
			]

			child_count = len(child_elements)
			if child_count == 0:
				stats["leaf_occurrences"] += 1
			else:
				stats["internal_occurrences"] += 1

			if stats["child_element_count_min"] is None:
				stats["child_element_count_min"] = child_count
				stats["child_element_count_max"] = child_count
			else:
				stats["child_element_count_min"] = min(stats["child_element_count_min"], child_count)
				stats["child_element_count_max"] = max(stats["child_element_count_max"], child_count)

			elements_in_this_kanji.add(elem_name)

			# Compute subtree height
			if not child_elements:
				height = 0
			else:
				child_heights = [traverse(child, depth + 1) for child in child_elements]
				height = 1 + max(child_heights)

			stats["heights"].add(height)
			return height

		traverse(root_group, depth=0)

		# Update per-element kanji set
		for elem in elements_in_this_kanji:
			element_kanji_set[elem].add(kanji_literal)

	# Finalize stats: convert sets, add kanji/radical info
	kanji_literals = set(kanji_data.keys())

	for elem_name, stats in element_stats.items():
		stats["kanji_list"] = sorted(
			k for k in element_kanji_set.get(elem_name, set())
			if k in kanji_literals
		)
		stats["kanji_count"] = len(stats["kanji_list"])

		# Depths as sorted list
		stats["depths"] = sorted(stats["depths"])

		# Leaf/internal patterns
		stats["always_leaf"] = stats["internal_occurrences"] == 0
		stats["never_leaf"] = stats["leaf_occurrences"] == 0

		# "Level" characterization (rough, but useful)
		# e.g. appears at depths {0,1,2,...}
		stats["min_depth"] = min(stats["depths"]) if stats["depths"] else None
		stats["max_depth"] = max(stats["depths"]) if stats["depths"] else None

		# Known kanji?
		stats["is_kanji"] = elem_name in kanji_literals

		# Kangxi radical info
		canonical = CJK_TO_KANGXI.get(elem_name, elem_name)  # Convert SVG element to canonical Kangxi radical if possible
		stats["is_kangxi_radical_char"] = canonical in radical_chars
		stats["kangxi_radical_ids"] = sorted(radical_kanji_map.get(canonical, set()))

		stats["min_height"] = min(stats["heights"]) if stats["heights"] else None
		stats["max_height"] = max(stats["heights"]) if stats["heights"] else None
		stats["avg_height"] = sum(stats["heights"]) / len(stats["heights"]) if stats["heights"] else None

		# Stroke count statistics
		stats["stroke_counts"] = sorted(stats["stroke_counts"])
		stats["min_stroke_count"] = min(stats["stroke_counts"]) if stats["stroke_counts"] else None
		stats["max_stroke_count"] = max(stats["stroke_counts"]) if stats["stroke_counts"] else None
		stats["avg_stroke_count"] = sum(stats["stroke_counts"]) / len(stats["stroke_counts"]) if stats["stroke_counts"] else None

		# Position statistics
		stats["positions"] = dict(sorted(stats["positions"].items(), key=lambda x: -x[1]))  # Convert defaultdict to regular dict, sorted by count in descending order
		if stats["positions"]:
			max_count = max(stats["positions"].values())
			stats["most_common_positions"] = sorted([pos for pos, count in stats["positions"].items() if count == max_count])
		else:
			stats["most_common_positions"] = []

	# Convert sets to lists for JSON
	for stats in element_stats.values():
		stats["kangxi_radical_ids"] = sorted(stats["kangxi_radical_ids"])
		stats["source_files"] = sorted(stats["source_files"])
		stats["heights"] = sorted(stats["heights"])

	return element_stats

def main():
	element_stats = collect_element_stats()

	# Write full stats to JSON
	os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
	with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
		json.dump(element_stats, f, ensure_ascii=False, indent=2)

	# Quick console summary: top 20 most common elements by kanji_count
	top = sorted(
		element_stats.values(),
		key=lambda s: (-s["kanji_count"], s["element"])
	)[:20]

	print("\nTop 20 elements by number of kanji they appear in:")
	for s in top:
		print(
			f"{s['element']}: in {s['kanji_count']} kanji, "
			# f"total_occurrences={s['total_occurrences']}, "
			# f"kanji_count={s['kanji_count']}, "
			# f"always_leaf={s['always_leaf']}, "
			f"is_kanji={s['is_kanji']}, "
			f"is_kangxi_radical_char={s['is_kangxi_radical_char']}, "
			f"max_height={s['max_height']}, "
			f"max_stroke_counts={s['max_stroke_count']}\n"
			# f"most_common_positions={s['most_common_positions']}"
			f"\tpositions={s['positions']}"
		)

if __name__ == "__main__":
	main()
