import json

with open("data/element_stats.json", "r", encoding="utf-8") as f:
    stats = json.load(f)

detected = []

for elem, info in stats.items():
    if info.get("is_kangxi_radical_char"):
        detected.append((elem, info.get("kangxi_radical_ids", [])))

# Sort by radical number
detected_sorted = sorted(
    detected,
    key=lambda x: int(x[1][0]) if x[1] else 999
)

for elem, ids in detected_sorted:
    print(f"{elem}  →  radical IDs: {ids}")

print("\nTotal detected:", len(detected_sorted))
