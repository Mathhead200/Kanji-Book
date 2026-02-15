import nltk
from collections.abc import Collection
from wordcloud import STOPWORDS

assert all(word.islower() for word in STOPWORDS)  # DEBUG

_nltk_words_cache: set[str] = None

def download_nltk_resources():
	nltk.download("punkt")
	nltk.download("punkt_tab")
	nltk.download("averaged_perceptron_tagger_eng")
	nltk.download("wordnet")
	nltk.download("words")

def pos_keep(pos: str) -> bool:
	# NN*: noun
	# VB*: verb
	# JJ*: adjective
	# CD: cardinal number
	return any(pos.startswith(pos_prefix) for pos_prefix in ["NN", "VB", "JJ", "CD"])

def get_nltk_words() -> set[str]:
	global _nltk_words_cache
	if _nltk_words_cache is None:
		_nltk_words_cache = set(nltk.corpus.words.words())
	return _nltk_words_cache

def tokenize(s: str, words: Collection[str]=None, case_insensitive=False) -> list[str]:
	if words is None:
		words = get_nltk_words()
	if case_insensitive:
		words = [word.lower() for word in words]
	
	tokens = []
	for token, pos in nltk.pos_tag(nltk.word_tokenize(s)):
		if not pos_keep(pos):
			continue
		if case_insensitive:
			token = token.lower()
		if token in STOPWORDS or token not in words:
			continue
		tokens.append(token)
	return tokens
