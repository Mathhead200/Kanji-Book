1. Update docs/word_cloud.md documentation
2. Build script to add stroke_count information to the element_stats.json file by extracting the number of SVG <path> tags in each element's root.
	Since elements may have different sub-tree structures in different KanjiVG SVG files, se can store a set of different unique stroke_counts and a min, max, and avg stroke count as well.
