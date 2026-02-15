
Goal:
For a given kanji, determine which English words, if any, sound similar in pronounciation
to some reading of that kanji. We can then incorperate one or more of these "close" words
into that kanji's file. We should also consider English word phrases, e.g. "Don't go" sounds
like "doko" ("where" in Japanese).

Optimizations:
* Eliminate English words that contain (too many) phonemes not found in Japanese, (or maybe all words that do not contain non-Jpaanese phonemes?)
	e.g. some vowels, some consonant clusters
* Maybe eliminate very long English words.
* Eliminate very obscure English words
* BK-tree or vantage point tree ?
* Cache results since Japanese has many repreated phonemes
* In general, dynamic programming could be useful here. Not just caching individual phonemes, but also group distances since the total distance is additive (or somehow cumulative from sub-problems).
