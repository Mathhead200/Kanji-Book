# 2242KANJIFREQUENCYLISTVER.1.1 - MAIN.csv
Contains the frequencies of each kanji measured under different metrics;
sorted by AVG FREQ.

# name_cache.json
Contains all the Japanese names accociated with a particular kanji.
Scraped from https://japanese-names.info/kanji/{kanji}/. See scripts/name_scraper.py.

# kanji_data.json
JSON containing a full list of Japanese kanji and meta data about those words including
their primary radical and readings.
kanji_data_with_freq.json is kanji_data.json merged with "2242KANJIFREQUENCYLISTVER.1.1 - MAIN.csv"
kanji_data_with_names.json is kanji_data_with_freq.json merged with name_cache.json

# radical_data.json
JSON containing each Kangxi radical and its mapping to all kanji that use it as
a primary radical for look-up.

# word_cache.json
JSON mapping kanji to words which incorperate that kanji and meta data about those words,
including their frequncy of literary usage, and approximated IPA pronounciations.
Downloaded from API, "https://kanjiapi.dev/v1/words/{kanji}". See scripts/script4.py.

# english_ipa_cache.json
JSON mapping English words to their IPA reduced IPA pronounciations for cross-reference
with he word cache.

# phoneme_confusion_matrix.csv
A table storing the relative "distance" between two phonemes relative to native US English
speakers. Phonemes that coul be confused when spoken are given low scores, and phonemes
which are unlikely to be confused are given higher scores.

# compound_words.json
Contains a list of English compound words and their sub-words for use by scripts/word_cloud.py

# multiword_phrases.json
Contains a list of phrases that should not be split by scripts/word_cloud.py, but
instead should be treated as single words or ideas.
