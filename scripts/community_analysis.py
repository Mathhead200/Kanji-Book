import json
import numpy as np
import networkx as nx
from sklearn.cluster import SpectralClustering

KANJI_PAIR_MATRIX = "data/radical_cooccurrence_matrix.csv"
RADICAL_PATH = "data/radical_data.json"
MAX_CLUSTERS = 9

# ------------------------------------------------------------
# Load radical metadata
# ------------------------------------------------------------
with open(RADICAL_PATH, "r", encoding="utf-8") as f:
    radical_info = json.load(f)

# ------------------------------------------------------------
# Read header row from CSV to get radical numbers in correct order
# ------------------------------------------------------------
with open(KANJI_PAIR_MATRIX, "r", encoding="utf-8") as f:
    header = f.readline().strip().split(",")[1:]  # skip first empty cell

radical_numbers = [int(h.split(".")[0]) for h in header]
radical_chars = {int(k): radical_info[k]["radical_char"] for k in radical_info}

# ------------------------------------------------------------
# Load pairwise matrix (UTF‑8 safe)
# ------------------------------------------------------------
with open(KANJI_PAIR_MATRIX, "r", encoding="utf-8") as f:
    pair_matrix = np.loadtxt(
        f,
        delimiter=",",
        skiprows=1,
        usecols=range(1, len(radical_numbers) + 1)
    )

N = len(radical_numbers)

# ------------------------------------------------------------
# Build graph
# ------------------------------------------------------------
G = nx.Graph()

for i, r1 in enumerate(radical_numbers):
    for j, r2 in enumerate(radical_numbers):
        if i < j:
            w = pair_matrix[i, j]
            if w > 0:
                G.add_edge(r1, r2, weight=w)

# ------------------------------------------------------------
# Community score (normalized)
# ------------------------------------------------------------
def community_score(labels, matrix):
    within = 0
    between = 0

    for i in range(N):
        for j in range(i + 1, N):
            w = matrix[i, j]
            if labels[i] == labels[j]:
                within += w
            else:
                between += w

    total = within + between
    if total == 0:
        return 0.0

    # +1 = perfect community, -1 = perfect anti-community
    return (within - between) / total

# ------------------------------------------------------------
# Try k = 2..MAX_CLUSTERS
# ------------------------------------------------------------
results = []

for k in range(2, MAX_CLUSTERS + 1):
    clustering = SpectralClustering(
        n_clusters=k,
        affinity="precomputed",
        assign_labels="kmeans",
        random_state=0
    ).fit(pair_matrix)  # <-- use original matrix (not inverted)

    labels = clustering.labels_
    score = community_score(labels, pair_matrix)

    clusters = {}
    for idx, label in enumerate(labels):
        clusters.setdefault(label, []).append(radical_numbers[idx])

    results.append((k, score, clusters))

# ------------------------------------------------------------
# Print results
# ------------------------------------------------------------
for k, score, clusters in results:
    print(f"\n=== {k} communities ===")
    print(f"Score: {score:.3f}")
    for label, group in clusters.items():
        chars = " ".join(radical_chars[r] for r in group)
        print(f"  Cluster {label}: {group}   {chars}")
