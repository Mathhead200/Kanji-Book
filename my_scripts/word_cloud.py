import os
import csv
import json
from collections import defaultdict, Counter
from collections.abc import Mapping, Iterable
from math import log
from typing import TypeVar
from tqdm import tqdm
from wordcloud import WordCloud
from tokenizer import tokenize, download_nltk_resources

# Progress Tracking
TQDM_LOAD_JSON_DATA = True
TQDM_GET_TOKENS_FROM_JA_WORD_ENTRY = False
TQDM_CALCULATE_IDF = True
TQDM_NORMALIZE_AND_SORT = False
TQDM_GET_TOKENS_FROM_KANJI = False
TQDM_GET_TOKENS_FROM_ELEMENT = False
TQDM_GET_TOKENS_FROM_RADICAL = False

JSON_PATHS = {
	"radicals": "data/radical_data.json",
	"elements": "data/element_stats.json",
	"kanji": "data/kanji_data.json",
	"ja_words": "data/word_cache.json",
}

DATA = None  # initialize with load_json_data()
_token_list_cache:   dict[str, list[str]]        = {}  #           ja_word -> list[token]
_token_counts_cache: dict[str, Counter[str]]     = {}  #           ja_word -> Counter[token]
_kanji_cache:        dict[str, dict[str, float]] = {}  #             kanji -> (token -> (normalized) total weight)
_radical_cache:      dict[str, dict[str, float]] = {}  #  (Kangxi) radical -> (token -> (normalized) total weight)
_element_cache:      dict[str, dict[str, float]] = {}  # (KangiVG) element -> (token -> (normalized) total weight)
_idf = None

T = TypeVar("T")
def opt_tqdm(elements: Iterable[T], desc=None) -> Iterable[T]:
	if desc is None:
		return elements
	return tqdm(elements, desc=desc)


def load_json_data(tqdm_desc=None) -> None:
	global DATA
	if TQDM_LOAD_JSON_DATA and tqdm_desc is None:  # Progress tracking
		tqdm_desc = "Loading JSON data"
	DATA = {
		key: json.load(open(path, "r", encoding="utf-8"))
		for key, path in opt_tqdm(JSON_PATHS.items(), desc=tqdm_desc)
	}

def get_tokens_from_ja_word_entry(ja_word_entry: dict, tqdm_desc=None) -> tuple[list[str], list[Counter[str]]]:
	ja_word = ja_word_entry["word"]
	if TQDM_GET_TOKENS_FROM_JA_WORD_ENTRY and tqdm_desc is None:  # Progress tracking
		tqdm_desc = f"Tokenizing {ja_word}"
	if ja_word not in _token_list_cache:
		_token_list_cache[ja_word] = []
		for meaning_entry in opt_tqdm(ja_word_entry["meanings"], desc=tqdm_desc):  # each meaning for this Japanese word
			for gloss in meaning_entry["glosses"]:                                 # each English "gloss" for this meaning (gloss: str)
				_token_list_cache[ja_word].extend(tokenize(gloss))  # add each token in gloss
		_token_counts_cache[ja_word] = Counter(_token_list_cache[ja_word])  # stores tally (number of occurances) of each token for the given Japanese word
	return _token_list_cache[ja_word], _token_counts_cache[ja_word]

def get_token_list_from_ja_word_entry(ja_word_entry: dict, tqdm_desc=None) -> list[str]:
	token_list, _ = get_tokens_from_ja_word_entry(ja_word_entry, tqdm_desc=tqdm_desc)
	return token_list

def get_token_counts_from_ja_word_entry(ja_word_entry: dict, tqdm_desc=None) -> Counter[str]:
	_, token_counts = get_tokens_from_ja_word_entry(ja_word_entry, tqdm_desc=tqdm_desc)
	return token_counts

def zipf(ja_word_entry: dict, exponent: float = 1.0) -> float:
	""" Zipf's Law """
	frequency = ja_word_entry["frequency"]
	if frequency is None:
		return 0.0
	return 1.0 / (frequency ** exponent)

def calculate_idf(tqdm_desc=None) -> dict[str, float]:
	""" Inverse document frequency for all terms in Japanese corpus. """
	global _idf
	if _idf is None:
		# Load Japanese corpus
		ja_words: dict[str, dict] = {}  # Japanese words -> word_entry JSON objects
		for kanji_entry in DATA["ja_words"].values():  # all kanji in Japanese word corpus
			for ja_word_entry in kanji_entry["words"]:
				if ja_word_entry["frequency"] is None:
					continue  # skip words that have no provided frequency, assumed very-rare
				ja_word = ja_word_entry["word"]
				ja_words[ja_word] = ja_word_entry  # store only unique Japanese words (duplicates overwrite earlier word_entries)
		
		# Calculate corpus frequecy for each token
		if TQDM_CALCULATE_IDF and tqdm_desc is None:  # Progress tracking
			tqdm_desc = "Calculating all inverse document frequencies"
		frequencies = defaultdict(int)  # will be the number of "documents" (i.e. Japanese words) each (English) token appears in
		for ja_word_entry in opt_tqdm(ja_words.values(), desc=tqdm_desc):
			tokens = set(get_token_list_from_ja_word_entry(ja_word_entry))  # remove duplicate tokens within each single "document" (i.e. Japanese word)
			for token in tokens:
				frequencies[token] += 1
		# # Inverse document frequency for each (English) token, sorted most common to least common
		N = len(ja_words)
		_idf = { token: log(N / frequency) for token, frequency in sorted(frequencies.items(), key=lambda x: -x[1]) }
	return _idf

def tf_idf(en_word: str, ja_word_entry: dict, idf: dict[str, float] = None) -> float:
	""" Term Frequency - Inverse Document Frequency """
	if idf is None:
		idf = calculate_idf()
	tf = get_token_counts_from_ja_word_entry(ja_word_entry)
	return tf[en_word] * idf[en_word]

class Cluster:
	__slots__ = ("weight", "ja_words")
	weight: float               # total weight for this token cluster
	ja_words: dict[str, float]  # Japanese words -> individual weight for this word in this cluster

	def __init__(self):
		self.weight = 0.0
		self.ja_words = {}
	
	def merge(self, other: Cluster) -> None:
		self.weight += other.weight
		for new_word, weight in other.ja_words.items():
			if new_word in self.ja_words:
				self.ja_words[new_word] += weight
			else:
				self.ja_words[new_word] = weight

def normalize_and_sort(tokens: Mapping[str, Cluster], tqdm_desc=None) -> dict[str, Cluster]:
	if len(tokens) == 0:  # to avoid divide-by-zero error in case of empty Mapping
		return {}
	if TQDM_NORMALIZE_AND_SORT and tqdm_desc is None:  # Progress tracking
		tqdm_desc = "Normalizing and sorting token weights"
	W = sum(cluster.weight for cluster in tokens.values())
	tokens = dict(sorted(tokens.items(), key=lambda item: -item[1].weight))  # sort clusters
	for cluster in opt_tqdm(tokens.values(), desc=tqdm_desc):
		cluster.weight /= W
		cluster.ja_words = { ja_word: weight / W for ja_word, weight in sorted(cluster.ja_words.items(), key=lambda item: -item[1]) }
	return tokens

def get_tokens_from_kanji(kanji: str, tqdm_desc=None) -> dict[str, Cluster]:
	if kanji not in _kanji_cache:
		if TQDM_GET_TOKENS_FROM_KANJI and tqdm_desc is None:  # Progress tracking
			tqdm_desc = f"Tokenizing kanji {kanji}"
		tokens = defaultdict(Cluster)  # (English) tokens (str) -> (total weight (float), associated Japanese words (dict))
		for ja_word_entry in opt_tqdm(DATA["ja_words"].get(kanji, {}).get("words", []), desc=tqdm_desc):  # all Japanese words associated with this kanji (if any)
			ja_word = ja_word_entry["word"]
			# The dictionary source had words associated with kanji that did not themselves contain said kanji.
			# We want to skip these words as unimportant.
			if kanji not in ja_word:  # check if str ja_word contains substr/character kanji
				continue
			a = zipf(ja_word_entry)
			if a == 0:
				continue  # skip words that have no provided frequency, assumed very-rare
			for token in set(get_token_list_from_ja_word_entry(ja_word_entry)):
				b = tf_idf(token, ja_word_entry)
				assert b != 0, "TF-IDF should not be 0"
				weight = a * b
				tokens[token].weight += weight
				tokens[token].ja_words[ja_word] = weight
		_kanji_cache[kanji] = normalize_and_sort(tokens)
	return _kanji_cache[kanji]

def get_tokens_from_element(kanjivg_element: str, tqdm_desc=None) -> dict[str, Cluster]:
	if kanjivg_element not in _element_cache:
		if TQDM_GET_TOKENS_FROM_ELEMENT and tqdm_desc is None:  # Progress tracking
			tqdm_desc = f"Tokenizing KanjiVG element {kanjivg_element}"
		tokens = defaultdict(Cluster)
		for kanji in opt_tqdm(DATA["elements"].get(kanjivg_element, {}).get("kanji_list", []), desc=tqdm_desc):  # all kanji containing this (KanjiVG) element (if any)
			for token, cluster in get_tokens_from_kanji(kanji).items():
				tokens[token].merge(cluster)
		_element_cache[kanjivg_element] = normalize_and_sort(tokens)
	return _element_cache[kanjivg_element]

def get_tokens_from_radical(kangxi_radical_id: str, tqdm_desc=None) -> dict[str, Cluster]:
	if kangxi_radical_id not in _radical_cache:
		if TQDM_GET_TOKENS_FROM_RADICAL and tqdm_desc is None:  # Progress tracking
			tqdm_desc = f"Tokenizing Kangxi radical id={kangxi_radical_id}"
		tokens = defaultdict(Cluster)
		for kanji in opt_tqdm(DATA["radicals"].get(kangxi_radical_id, {}).get("kanji", []), desc=tqdm_desc):  # all kanji associated with this Kangxi radical (if any)
			for token, cluster in get_tokens_from_kanji(kanji).items():
				tokens[token].merge(cluster)
		_radical_cache[kangxi_radical_id] = normalize_and_sort(tokens)
	return _radical_cache[kangxi_radical_id]

def save_word_cloud(tokens: dict[str, Cluster], out: str) -> None:
	if len(tokens) == 0:
		return
	wc = WordCloud(width=1920, height=1080, background_color="white")
	wc.generate_from_frequencies({ token: cluster.weight for token, cluster in tokens.items() })
	wc.to_file(out)

def save_freq_report(tokens: dict[str, Cluster], out: str) -> None:
	if len(tokens) == 0:
		return

	with open(out, "w", encoding="utf-8") as file:
		# save summary at the top
		file.write("Summary: {Weight} {token}: {words[0:10]}\n")
		for token in tokens:
			cluster = tokens[token]
			words = list(cluster.ja_words)
			L = len(words)
			MAX = 10
			words = words[0:MAX]
			if L > MAX:
				words.append("...")
			words = ", ".join(words)
			file.write(f"{cluster.weight:.7f} {L:4d} {token:15}: {words}\n")

		file.write(f'\n{"-" * 80}\n\n')

		# full report after
		for i, token in enumerate(tokens):
			cluster = tokens[token]
			L = len(cluster.ja_words)
			file.write(f"TOKEN[{i + 1:2d}]: {cluster.weight:.7f} {L:4d} {token}\n")
			for j, item in enumerate(cluster.ja_words.items()):
				ja_word, weight = item
				file.write(f"\t{token} WORD[{i + 1:2d},{j + 1:4d}]: {weight:.7f} {ja_word}\n")

if __name__ == "__main__":
	COVERAGE_FILE = "data/element_coverage_plan_joyo.csv"
	OUT_DIR = "word_clouds/v4. Joyo plan Kanji and KanjiVG elements, (v2 lexer)"

	# download_nltk_resources()
	load_json_data()

	# generate list of elements from coverage file
	elements = []
	print("Parsing data/element_coverage_plan.csv...")
	with open(COVERAGE_FILE, "r", encoding="utf-8") as file:
		reader = csv.DictReader(file)
		for row in reader:
			elements.append(row["element"])

	# generate word clouds
	radicals = [radical_id for element in elements for radical_id in DATA["elements"][element]["kangxi_radical_ids"] if DATA["elements"][element]["is_kangxi_radical_char"]]
	kanjis = [element for element in elements if DATA["elements"][element]["is_kanji"]]

	for radical_id in tqdm(radicals, desc="Generating word clouds for Kangxi radicals"):
		tokens = get_tokens_from_radical(radical_id)
		radical_char = DATA["radicals"][radical_id]["radical_char"]
		codepoint = hex(ord(radical_char))[2:]  # strip leading "0x..."
		sub_dir = f'{OUT_DIR}/stroke {DATA["radicals"][radical_id]["stroke_count"]}'
		os.makedirs(sub_dir, exist_ok=True)
		save_freq_report(tokens, f"{sub_dir}/radical_{radical_id}_{radical_char}_{codepoint}.txt")
		save_word_cloud( tokens, f"{sub_dir}/radical_{radical_id}_{radical_char}_{codepoint}.png")

	for kanji in tqdm(kanjis, desc="Generating word clouds for kanji"):
		tokens = get_tokens_from_kanji(kanji)
		codepoint = hex(ord(kanji))[2:]  # strip leading "0x..."
		sub_dir = f'{OUT_DIR}/stroke {DATA["kanji"][kanji]["stroke_count"]}'
		os.makedirs(sub_dir, exist_ok=True)
		save_freq_report(tokens, f"{sub_dir}/kanji_{kanji}_{codepoint}.txt")
		save_word_cloud( tokens, f"{sub_dir}/kanji_{kanji}_{codepoint}.png")

	for element in tqdm(elements, desc="Generating word clouds for all elements"):
		tokens = get_tokens_from_element(element)
		codepoint = "_".join( hex(ord(c))[2:] for c in element )  # strip leading "0x..."
		sub_dir = f'{OUT_DIR}/stroke {DATA["elements"][element]["max_stroke_count"]}'
		os.makedirs(sub_dir, exist_ok=True)
		save_freq_report(tokens, f"{sub_dir}/element_{element}_{codepoint}.txt")
		save_word_cloud( tokens, f"{sub_dir}/element_{element}_{codepoint}.png")

	print("Done.")
