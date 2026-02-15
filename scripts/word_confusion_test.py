import csv
import math
from typing import Dict, List, Tuple

# ---------------------------------------------------------
# 1. Load phoneme confusion matrix
# ---------------------------------------------------------

def load_confusion_matrix(path: str):
    dist = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    phonemes = rows[0][1:]

    for r in rows[1:]:
        p = r[0]
        for q, val in zip(phonemes, r[1:]):
            try:
                dist[(p, q)] = float(val)
            except ValueError:
                dist[(p, q)] = 999.0

    return phonemes, dist


# ---------------------------------------------------------
# 2. Phoneme distance lookup
# ---------------------------------------------------------

def phoneme_distance(p: str, q: str, dist_matrix: Dict[Tuple[str, str], float]) -> float:
    return dist_matrix.get((p, q), 999.0)


# ---------------------------------------------------------
# 3. IPA tokenization (dot-separated)
# ---------------------------------------------------------

def tokenize_ipa(ipa: str, phoneme_set: List[str]) -> List[str]:
    return ipa.split(".")


# ---------------------------------------------------------
# 4. Word confusion distance (directional)
# ---------------------------------------------------------

# Strong penalties for deletion/insertion
MIN_DEL = 5.0
MIN_INS = 5.0

def word_distance(
    ipa_src: str,
    ipa_tgt: str,
    phonemes: List[str],
    dist_matrix: Dict[Tuple[str, str], float],
    alpha: float = 1.0,
    beta: float = 1.0,
) -> float:

    src = tokenize_ipa(ipa_src, phonemes)
    tgt = tokenize_ipa(ipa_tgt, phonemes)
    n, m = len(src), len(tgt)

    # Compute deletion/insertion costs with floors
    def del_cost(p: str) -> float:
        raw = min(phoneme_distance(p, q, dist_matrix) for q in phonemes)
        return max(MIN_DEL, raw)

    def ins_cost(q: str) -> float:
        raw = min(phoneme_distance(p, q, dist_matrix) for p in phonemes)
        return max(MIN_INS, raw)

    # DP matrix
    D = [[0.0] * (m + 1) for _ in range(n + 1)]

    # Base cases
    for i in range(1, n + 1):
        D[i][0] = D[i - 1][0] + alpha * del_cost(src[i - 1])
    for j in range(1, m + 1):
        D[0][j] = D[0][j - 1] + beta * ins_cost(tgt[j - 1])

    # Recurrence
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            sub = phoneme_distance(src[i - 1], tgt[j - 1], dist_matrix)
            D[i][j] = min(
                D[i - 1][j - 1] + sub,            # substitution
                D[i - 1][j] + alpha * del_cost(src[i - 1]),  # deletion
                D[i][j - 1] + beta * ins_cost(tgt[j - 1])    # insertion
            )

    return D[n][m] / max(1, max(n, m))


# ---------------------------------------------------------
# 5. Load lexicons
# ---------------------------------------------------------

def load_lexicon(path: str) -> List[Tuple[str, str]]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            word = row["word"].strip()
            ipa = row["ipa"].strip()
            if word and ipa:
                out.append((word, ipa))
    return out


# ---------------------------------------------------------
# 6. Compute nearest English neighbors
# ---------------------------------------------------------

def nearest_neighbors(
    ja_lex: List[Tuple[str, str]],
    en_lex: List[Tuple[str, str]],
    phonemes: List[str],
    dist_matrix: Dict[Tuple[str, str], float],
    k: int = 5,
):
    results = []
    for ja_word, ja_ipa in ja_lex:
        scores = []
        for en_word, en_ipa in en_lex:
            d = word_distance(ja_ipa, en_ipa, phonemes, dist_matrix)
            scores.append((en_word, en_ipa, d))
        scores.sort(key=lambda x: x[2])
        results.append({
            "ja_word": ja_word,
            "ja_ipa": ja_ipa,
            "neighbors": scores[:k],
        })
    return results


# ---------------------------------------------------------
# 7. Write output CSV (globally sorted)
# ---------------------------------------------------------

def write_neighbors_csv(results, out_path: str):
    rows = []
    for r in results:
        ja_word = r["ja_word"]
        ja_ipa = r["ja_ipa"]
        for rank, (en_word, en_ipa, dist) in enumerate(r["neighbors"], start=1):
            rows.append([ja_word, ja_ipa, rank, en_word, en_ipa, dist])

    rows.sort(key=lambda x: x[5])

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ja_word", "ja_ipa", "rank", "en_word", "en_ipa", "distance"])
        writer.writerows(rows)


# ---------------------------------------------------------
# 8. Main
# ---------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--en_lex", required=True)
    parser.add_argument("--ja_lex", required=True)
    parser.add_argument("--out", default="ja_to_en_neighbors.csv")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    phonemes, dist_matrix = load_confusion_matrix(args.matrix)
    en_lex = load_lexicon(args.en_lex)
    ja_lex = load_lexicon(args.ja_lex)

    results = nearest_neighbors(ja_lex, en_lex, phonemes, dist_matrix, k=args.k)
    write_neighbors_csv(results, args.out)

    print(f"Wrote {args.out}")
