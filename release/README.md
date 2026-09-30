# deephoneme

Rule-based Nepali grapheme-to-phoneme (G2P) converter. No model, no training, no dependencies (Python 3.12+ standard library).
Pronunciations come from a letter table, schwa-deletion rules, a few word lists, and an exceptions file of
words decided by ear or confirmed by forced alignment on real Nepali speech. The big `lexicon.dict` is the phonemizer's own output for {lexicon_words} words, shipped for
lookup and forced alignment; the phonemizer does not need it at run time.

## To use

```bash
git clone git@github.com:apalacodes/deephoneme.git && cd deephoneme
uv run test.py --quick
uv run --extra app python -m deephoneme.speech.kokoro_voice      # once: download the voice
uv run --extra app streamlit run check_phoneme.py
```

Needs [uv](https://docs.astral.sh/uv/) (it fetches Python 3.12+ itself). For the `hybrid` and `espeak`
voices also install espeak-ng: `sudo apt install espeak-ng`.

## Numbers

| | |
|---|---|
| Lexicon (`lexicon.dict`) | **{lexicon_words}** words |
| Exceptions (rule S0: decided by ear or accepted from audio) | **{exceptions}** words |
| Verified words (benchmark) | **{verified}**: {owner} decided by ear, {audio} accepted from forced alignment on real speech, {agree} where the rules agree with Wiktionary |
| Rule samples (`test.py`) | {rule_samples} |
| Letter table | {table_rows} graphemes |
| Word lists | {word_lists} |

Lexicon sources (a word can have several):

| source | words |
|---|---|
{source_rows}

## Use

Needs Python 3.12+. Easiest with [uv](https://docs.astral.sh/uv/), which fetches the right Python itself
(plain `python`/`python3` may be too old, e.g. 3.8 on Ubuntu 20.04). From this folder:

```bash
uv run test.py --quick                    # self-test
uv run deephoneme "नेपालमा घर छ"           # n e p a l m a | gʱ ʌ r | tsʰ ʌ
uv build                                  # -> dist/deephoneme-{version}-py3-none-any.whl
```

In another project: `uv add /path/to/deephoneme` (this folder) or `uv add ./deephoneme-{version}-py3-none-any.whl`.

```python
from deephoneme import phonemize, phonemize_word
phonemize("नेपालमा घर छ")     # 'n e p a l m a | gʱ ʌ r | tsʰ ʌ'
phonemize_word("समय")         # ['s', 'ʌ', 'm', 'ʌ', 'j']
```

```bash
deephoneme "नेपालमा घर छ"                 # n e p a l m a | gʱ ʌ r | tsʰ ʌ
cat sentences.txt | deephoneme            # one line in, one line out
deephoneme --explain नेपालको              # which rule decided each schwa
deephoneme --serve 8000                   # GET localhost:8000/phonemize?text=...  -> JSON
uv run test.py [--quick]                  # self-test
```

### New words: a review queue (optional)

```bash
uv run deephoneme --log-new "…"                           # CLI: unseen words -> new_words.tsv
export DEEPHONEME_NEW_WORDS=new_words.tsv                 # any program that imports deephoneme
```

Every word that is not in `lexicon.dict` is appended once to `new_words.tsv` (word, phonemes, the
schwa rule per akshara, date). They are **not** added to `exceptions.tsv`: the phonemizer only knows
a word is new, not that it is wrong. Check them by ear (`check_phoneme.py`) or in the next forced
alignment run, and put the ones that need it into `deephoneme/data/exceptions.tsv`.

Output: phonemes separated by spaces, words by ` | `. Look up a word in the lexicon: `grep -P "^समय\t" lexicon.dict`.

## Listen: the tester app (optional)

A Streamlit app to hear the phonemes through the Kokoro-82M voice (Hindi voices, reads IPA directly).
Needs the `app` extra (streamlit, onnxruntime, numpy); the phonemizer itself stays dependency-free.

```bash
uv run --extra app python -m deephoneme.speech.kokoro_voice   # once: download the voice (~350 MB) into models/kokoro/
uv run --extra app streamlit run app.py                         # opens http://localhost:8501
```

- **Speak**: type text, hear it in each mode. **Word**: the rule behind each schwa, the lexicon entry,
  and a box to try other phonemes. **IPA lab**: edit the exact symbols the voice gets.
- Modes: `hybrid` = espeak-ng's stress and vowel length with our sounds and schwa (the main system);
  `ours` = our phonemes only; `espeak` = espeak-ng as-is. `hybrid` and `espeak` need
  `espeak-ng` installed (`sudo apt install espeak-ng`); without it the app offers `ours` only.
- Voice already downloaded elsewhere? `export KOKORO_DIR=/path/to/kokoro` instead of downloading.
- **Check phonemes + benchmark**: `uv run --extra app streamlit run check_phoneme.py`. Paste a long
  sentence: per word our phonemes vs espeak-ng's, the benchmark reference where there is one, audio for
  the sentence and every word. Tab *Benchmark* scores espeak-ng and deephoneme on `benchmark.tsv`
  (word accuracy, PER = phoneme edit distance / reference phonemes, per basis, error kinds).
- Save a file from code: `uv run --extra app python -m deephoneme.speech.synth "नेपाल" -o out.wav`.

## How a word is pronounced

1. **Normalize** (`normalize.py`): NFC, remove zero-width characters and nukta, repair typing habits (ाे → ो, doubled matras).
2. **Exceptions** (rule S0): if the word, or its stem after removing a case suffix, is in `exceptions.tsv`, use that.
3. **Suffix split** (`suffix.py`): case suffixes (मा, को, ले, …) are split off; the stem gets the schwa rules.
4. **Segment** (`segment.py`) into aksharas; **map** (`mapping.py`) letters with the table below.
5. **Schwa rules** (`schwa.py`): every consonant akshara with no matra and no halanta; first matching rule wins.
6. **Post-rules** (`postrules.py`): nasals and व.

| Rule | Condition | Schwa |
|---|---|---|
| S0 | word or stem in `exceptions.tsv` | as listed |
| S1 | a conjunct follows, or ं / ँ follows | keep |
| S2 | first akshara | keep |
| S3 | not final (medial) | keep |
| S4 | final ङ | delete |
| S5 | word in `pronouns.txt` | delete |
| S6 | word in `adverbs.txt` or `postpositions.txt` | keep |
| S7 | word matches `verb_endings.txt` | keep |
| S8 | final छ, य or ह | keep |
| S9 | final conjunct and word in `loanwords.txt` | delete |
| S10 | final conjunct | keep |
| S11 | otherwise | delete |

| Post-rule | |
|---|---|
| POST-1 | ं before a stop → nasal at the stop's place (ŋ n m); elsewhere nasalizes the vowel |
| POST-2 | व → b at the start of a word and after ं; w elsewhere |
| POST-3 | ँ nasalizes the preceding vowel |

## Letter table (`deephoneme/data/phonemes.tsv`)

{table}

Phoneme inventory: vowels `i e a ʌ o u`, nasalized `ĩ ẽ ã ʌ̃ ũ õ`, diphthongs `ʌi ʌu` (nasalized `ʌĩ ʌũ`);
consonants as in the table plus `w`. Long and short i/u are not distinguished; च-series are alveolar `ts dz`.

## Files

```
deephoneme/            the phonemizer (normalize, segment, mapping, suffix, schwa, postrules; CLI in __main__;
                       compare.py: espeak-ng mapping and PER scoring)
deephoneme/speech/     optional voice: hybrid prosody (espeak-ng), IPA map, Kokoro-82M (app extra)
deephoneme/data/
  phonemes.tsv         letter table: grapheme, phoneme, type
  exceptions.tsv       word → phonemes; overrides every rule (S0). Edit this to fix a word.
  pronouns.txt adverbs.txt postpositions.txt verb_endings.txt loanwords.txt   word lists (S5-S9)
  suffixes.txt         case suffixes split before the schwa rules
  ipa_map.tsv hybrid_keep_espeak.tsv   voice only: phoneme -> IPA symbol, sounds kept from espeak
app.py                 tester app (Speak / Word / IPA lab)
check_phoneme.py       sentence checker + espeak-ng vs deephoneme benchmark (PER)
benchmark.tsv          {verified} verified words: word, phonemes, basis (owner / audio / agree)
lexicon.dict           word<TAB>phonemes for every word above (MFA dictionary format)
test.py                self-test
```

To change a pronunciation, add the word to `exceptions.tsv` (or a word list), not to `lexicon.dict`:
the lexicon is generated and `test.py` checks it against the phonemizer.

Built {date} from the development repo (`uv run release/export.py`).
