# Apala's phonemizer

A rule-based Nepali grapheme-to-phoneme converter (package `deephoneme`), with one app to compare it
with espeak-ng and to benchmark it against ground-truth pronunciations, and a Kokoro voice to listen.
No neural model: letter table + schwa rules + word lists + {exceptions} exceptions decided by ear or
confirmed by forced alignment on real speech. The phonemizer itself needs no packages.

## Everything in this folder

```
apalas_phonemizer/
├── README.md                  this file
├── pyproject.toml             project file; the phonemizer has no dependencies, the app extra adds
│                              streamlit + onnxruntime + numpy
├── app.py                     the app: 1 · compare with espeak-ng   2 · benchmark against ground truth
├── ground_truth.tsv           {verified} verified words (word, phonemes, basis): the default ground truth
├── ground_truth_sentences.tsv {sentences} sentences with IPA (sentence, sentence_ipa): sentence-level ground truth
├── lexicon.dict               reference dictionary: {lexicon_words} words, word<TAB>phonemes (not used at run time)
├── test.py                    self-test: rule samples, exceptions, ground truth, lexicon
└── deephoneme/                the phonemizer
    ├── __init__.py            phonemize(text), phonemize_word(word), analyze_word(word)
    ├── __main__.py            command line: `deephoneme "text"`, --explain, --serve, --log-new
    ├── normalize.py           Unicode clean-up, typing-habit repairs, tokenizing
    ├── segment.py             word -> aksharas
    ├── suffix.py              split case suffixes (मा, को, ले, …) before the schwa rules
    ├── schwa.py               schwa rules S0-S11 (keep or delete the inherent ʌ)
    ├── mapping.py             letters -> phonemes (data/phonemes.tsv)
    ├── postrules.py           ं ँ व post-rules
    ├── compare.py             espeak-ng -> our phonemes, edit distance, PER scoring
    ├── newwords.py            optional log of words not in lexicon.dict (a review queue)
    ├── paths.py               where the data files are
    ├── data/
    │   ├── phonemes.tsv       letter table ({table_rows} graphemes)
    │   ├── exceptions.tsv     {exceptions} words: word<TAB>phonemes, overrides every rule (S0)
    │   ├── pronouns.txt adverbs.txt postpositions.txt verb_endings.txt loanwords.txt suffixes.txt
    │   │                      word lists used by the rules ({word_lists})
    │   ├── ipa_map.tsv        voice only: our phoneme -> IPA symbol Kokoro reads
    │   └── hybrid_keep_espeak.tsv   voice only: sounds kept from espeak-ng
    └── speech/                voice only: espeak-ng prosody + our sounds ("hybrid"), Kokoro-82M
```

Not in git: `.venv/` (made by uv), `models/kokoro/` (the voice, downloaded once), `new_words.tsv`.

## Requirements

- [uv](https://docs.astral.sh/uv/): `curl -LsSf https://astral.sh/uv/install.sh | sh` (it installs
  Python 3.12+ itself; an older system `python3` does not matter).
- For the app: `sudo apt install espeak-ng` (the comparison and the "hybrid" voice need it) and the
  Kokoro voice files (~350 MB, one command below).

## Run it

```bash
cd apalas_phonemizer
uv run test.py --quick                                         # self-test: expect 4 × ok

uv run deephoneme "नेपालमा घर छ"                                # n e p a l m a | gʱ ʌ r | tsʰ ʌ
uv run deephoneme --explain नेपालको                             # which rule decided each schwa
cat sentences.txt | uv run deephoneme                          # one line in, one line out

uv run --extra app python -m deephoneme.speech.kokoro_voice    # once: download the voice
uv run --extra app streamlit run app.py                        # the app: http://localhost:8501
```

From Python (inside this folder, or after `uv add /path/to/apalas_phonemizer` in another project):

```python
from deephoneme import phonemize, phonemize_word
phonemize("नेपालमा घर छ")        # 'n e p a l m a | gʱ ʌ r | tsʰ ʌ'
phonemize_word("समय")            # ['s', 'ʌ', 'm', 'ʌ', 'j']
```

## The app

**1 · Compare with espeak-ng.** Paste Nepali text. You see, per word, the schwa rules, our phonemes,
espeak-ng's phonemes and the kind of difference, and you hear both through the same Kokoro voice.

**2 · Benchmark against ground truth.** Scores our phonemizer (and espeak-ng) with PER (phoneme edit
distance / ground-truth phonemes) and word accuracy, per basis and per error kind, lists every error
(filter, search, download as TSV) and plays the ground truth next to the system's version.
Ground truth: the bundled `ground_truth.tsv` (words) or `ground_truth_sentences.tsv` (sentences), or
upload your own file in either format (TSV or CSV):

```
word	phonemes	basis                  sentence	sentence_ipa
समय	s ʌ m ʌ j	mine                   घर छ	gʰʌɾ tsʰʌ
कमल	k ʌ m ʌ l	mine
```

Words: `phonemes` space-separated in the symbols of the table below, `basis` optional.
Sentences: IPA words separated by spaces, one per word of the sentence. A word with more than one
accepted pronunciation lists them with `/` (`dzʌnʌta/dzʌnta`): a system is right with either, and the
app flags these words (⚑) as places where the phonemizer produces only one of them. Before scoring the IPA is
converted to our symbols; this changes notation only (ɾ → r, dʰ gʰ bʰ → d̪ʱ gʱ bʱ, plain t d → t̪ d̪,
a plain h after a stop → ʰ, h elsewhere → ɦ). For sentences the app also shows PER per sentence,
each word as ground truth / ours / espeak-ng, and plays the sentence three ways.

## How a word is pronounced

1. normalize the spelling → 2. if the word (or its stem) is in `exceptions.tsv`, use that (S0) →
3. split a case suffix → 4. cut the stem into aksharas → 5. decide each inherent schwa (S1-S11) →
6. map letters to phonemes, apply ं ँ व post-rules → 7. add the suffix back.

| Rule | Condition | Schwa |
|---|---|---|
| S0 | word or stem in `exceptions.tsv` | as listed |
| S1 | a conjunct or ं / ँ follows | keep |
| S2 | first akshara | keep |
| S3 | not final | keep |
| S4 | final ङ | delete |
| S5 | pronoun (`pronouns.txt`) | delete |
| S6 | adverb / postposition | keep |
| S7 | verb ending (`verb_endings.txt`) | keep |
| S8 | final छ, य or ह | keep |
| S9 | final conjunct in a loanword (`loanwords.txt`) | delete |
| S10 | final conjunct | keep |
| S11 | otherwise | delete |

Letter table (`deephoneme/data/phonemes.tsv`):

{table}

Output: phonemes separated by spaces, words by ` | `. Vowels `i e a ʌ o u`, nasalized `ĩ ẽ ã ʌ̃ ũ õ`,
diphthongs `ʌi ʌu` (nasalized `ʌĩ ʌũ`).

## Changing a pronunciation

Add `word<TAB>phonemes` to `deephoneme/data/exceptions.tsv`, or better, decide it in the development
repo (Phonemizer) and regenerate this folder: `uv run release/export_apalas.py` there.
`lexicon.dict` is generated; `test.py` checks that the phonemizer still reproduces it.

Built {date}.
