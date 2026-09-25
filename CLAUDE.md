# Nepali G2P (Phonemizer)

A rule-based Nepali grapheme-to-phoneme converter, with espeak-ng as the baseline.
Later phases add a lexicon and a neural fallback. Accuracy on Nepali schwa (inherent vowel /ʌ/) deletion is the main goal.
Listening tests use the owner's **Piper Nepali voice** (models/) as the speaker; espeak-ng is kept only as a baseline.

## Project layout

```
nepali-g2p/
  data/
    phonemes.tsv        # grapheme \t phoneme \t type (consonant/vowel/matra/sign)
    pronouns.txt        # one word per line; final schwa DELETED
    adverbs.txt         # final schwa KEPT
    postpositions.txt   # final schwa KEPT
    verb_endings.txt    # suffix patterns marking verb forms; final schwa KEPT
    suffixes.txt        # case/plural suffixes: को मा ले लाई हरू बाट सँग देखि सम्म ...
    loanwords.txt       # non-Sanskrit loans; final-conjunct schwa DELETED
    exceptions.tsv      # word \t phonemes  (full override, checked first)
    gold/test.tsv       # word \t category \t phonemes   (NEVER use for rule tuning by lookup)
  g2p/
    __init__.py         # public API: phonemize(text) -> str, phonemize_word(word) -> list[str]
    normalize.py        # NFC, strip ZWJ/ZWNJ, nukta unification, digits/punctuation
    segment.py          # word -> list of aksharas (consonant cluster + vowel/matra/halanta/nasal)
    mapping.py          # grapheme -> phoneme using data/phonemes.tsv
    suffix.py           # split word into stem + suffixes using data/suffixes.txt
    schwa.py            # keep/delete decision for every inherent vowel
    postrules.py        # nasal assimilation, व handling, ज्ञ, etc.
  bench/
    run_espeak.py       # espeak-ng -v ne -q --ipa on gold words -> bench/out/espeak.tsv
    evaluate.py         # WER, PER, schwa accuracy, per-category table
  tts/
    piper_voice.py      # load ONNX voice, phonemes -> ids -> wav (onnxruntime, no piper CLI)
    symbol_map.py       # our phoneme inventory -> the voice's phoneme_id_map symbols
    synth.py            # CLI: text -> wav with --g2p {ours,espeak}
  data/piper_map.tsv    # our_phoneme \t piper_symbols   (editable mapping table)
  models/               # GITIGNORED. Owner's files, never modify or commit:
    ne_NP-google-medium.onnx        # inference model (used by tts/)
    ne_NP-google-medium.onnx.json   # config: phoneme_id_map, sample_rate, inference scales
    best.ckpt                       # training checkpoint (for later fine-tuning only)
    piper_train_p007.yaml           # training config (for later fine-tuning only)
  bench/listen/         # A/B listening test output (wavs + index.html)
  tests/                # pytest; one test per rule, using the examples below
```

## Environment: uv ONLY

This project uses **uv** for everything. Never use pip, venv, virtualenv, poetry, or conda.

- Add deps: `uv add editdistance` · dev deps: `uv add --dev pytest`
- Run code: `uv run python -m g2p ...` · `uv run bench/evaluate.py`
- Run tests: `uv run pytest`
- Sync env: `uv sync`
- Dependencies live in `pyproject.toml` + `uv.lock`; never create requirements.txt.

## Conventions

- Python 3.10+, standard library first. Allowed deps: `pytest`, `editdistance` (or implement Levenshtein).
- All word lists live in `data/` as plain UTF-8 text so a linguist can edit them. No word lists hard-coded in Python.
- Output format: phonemes as a list; string form is space-separated, words separated by ` | `.
- Every rule in `schwa.py` has a docstring naming the rule ID below and at least one test.
- Do not tune rules by looking up gold words. Fix errors by improving a rule or adding to `exceptions.tsv` / a word list.

## Phoneme inventory (the output contract — use only these symbols)

Vowels: `i e a ʌ o u`; nasalized: `ĩ ẽ ã ʌ̃ ũ` (õ allowed as free variant); diphthongs `ʌi ʌu` (for ऐ औ).

| Grapheme | Phoneme | Grapheme | Phoneme | Grapheme | Phoneme |
|---|---|---|---|---|---|
| क | k | ख | kʰ | ग | g |
| घ | gʱ | ङ | ŋ | च | ts |
| छ | tsʰ | ज | dz | झ | dzʱ |
| ञ | n | ट | ʈ | ठ | ʈʰ |
| ड | ɖ | ढ | ɖʱ | ण | n |
| त | t̪ | थ | t̪ʰ | द | d̪ |
| ध | d̪ʱ | न | n | प | p |
| फ | pʰ | ब | b | भ | bʱ |
| म | m | य | j | र | r |
| ल | l | व | b (see POST-2) | श ष स | s |
| ह | ɦ | ज्ञ | g j | क्ष | k tsʰ |

Independent vowels / matras: अ ʌ · आ ा a · इ ि ई ी i · उ ु ऊ ू u · ए े e · ऐ ै ʌi · ओ ो o · औ ौ ʌu · ऋ ृ r i.
Signs: ् halanta (no vowel) · ँ nasalize preceding vowel · ं see POST-1 · ः visarga → ɦ (rare, loanwords).

Note: Nepali च-series are alveolar affricates (ts dz), NOT Hindi tʃ dʒ. Long/short i/u are not distinguished.

## Schwa rules (schwa.py)

Apply to every consonant akshara that has no matra and no halanta. First matching rule wins.
Run suffix splitting first; "final" means final in the stem when a case suffix was removed.

| ID | Condition | Decision |
|---|---|---|
| S0 | Word in `exceptions.tsv` | use lexicon entry |
| S1 | Next unit is a halanta-consonant (conjunct follows), or ं / ँ follows | KEEP |
| S2 | First akshara of the word | KEEP |
| S3 | Not final (Nepali rarely deletes medially) | KEEP |
| S4 | Final letter is ङ | DELETE |
| S5 | Word in `pronouns.txt` | DELETE |
| S6 | Word in `adverbs.txt` or `postpositions.txt` | KEEP |
| S7 | Word matches a pattern in `verb_endings.txt` | KEEP |
| S8 | Final letter is छ, य or ह | KEEP |
| S9 | Final akshara is a conjunct and word in `loanwords.txt` (or the word is मञ्च) | DELETE |
| S10 | Final akshara is a conjunct | KEEP |
| S11 | Otherwise (incl. घ ण थ फ व श ष) | DELETE |

## Post-rules (postrules.py)

- POST-1: ं before a stop → homorganic nasal (velar ŋ, palatal/alveolar n, retroflex n, dental n, labial m); elsewhere → nasalize the preceding vowel.
- POST-2: व → b by default; w only via exceptions for now.
- POST-3: ँ → add combining tilde to the preceding vowel.

## Required tests (tests/test_rules.py) — word → expected phonemes

```
कमल      k ʌ m ʌ l          S11
समय      s ʌ m ʌ j ʌ        S2, S8
कस्तो     k ʌ s t̪ o          S1
झन्      dzʱ ʌ n            halanta
गुरुङ     g u r u ŋ          S4
रङ       r ʌ ŋ              S4
माघ      m a gʱ             S11
कारण     k a r ʌ n          S11
साथ      s a t̪ʰ             S11
देश      d̪ e s              S11
मानव     m a n ʌ b          S11, POST-2
अन्त      ʌ n t̪ ʌ            S10
सम्बन्ध    s ʌ m b ʌ n d̪ʱ ʌ     S10
हुन्छ      ɦ u n tsʰ ʌ         S7/S8/S10
भएर      bʱ ʌ e r ʌ         S7
रहन      r ʌ ɦ ʌ n ʌ        S7 (infinitive)
छन्      tsʰ ʌ n            halanta
यस       j ʌ s              S5
जुन      dz u n             S5
अब       ʌ b ʌ              S6
आज       a dz ʌ             S6
सुख      s u kʰ ʌ           S0
दुख      d̪ u kʰ ʌ           S0
पार्क      p a r k            S9
मार्च      m a r ts           S9
मञ्च      m ʌ n ts           S9
घरमा     gʱ ʌ r m a         suffix split + S11
नेपालको   n e p a l k o      suffix split + S11
संगीत     s ʌ ŋ g i t̪         POST-1, S11
महँगो     m ʌ ɦ ʌ̃ g o         S1, POST-3
छ        tsʰ ʌ              S2
म        m ʌ                S2
ज्ञान      g j a n            mapping, S11
```

If a test and a rule disagree, stop and report it rather than editing the expected output.

## Benchmark (bench/)

- `run_espeak.py`: call `espeak-ng -v ne -q --ipa` per word; map its IPA to our inventory
  (tʃ→ts, dʒ→dz, ə→ʌ, strip stress marks and length marks) before scoring.
- `evaluate.py` reports, for each system (espeak, rules):
  - WER (word exact match), PER (Levenshtein over phoneme lists / reference length)
  - Schwa accuracy + precision/recall of DELETE decisions (align on inherent-vowel positions)
  - Per-category word accuracy (category column of gold/test.tsv)
  - Words/second
- Write results to `bench/results.md` as a table, appending a dated row per run. Write errors to `bench/out/errors_<system>.tsv`.

## TTS speaker: Piper voice (tts/)

The voice was trained on **espeak-ng phonemes**, so it only knows the symbols in `phoneme_id_map`
inside `models/ne_NP-google-medium.onnx.json`. Our phonemes must be translated into those symbols before synthesis.

- Deps: `uv add onnxruntime numpy` (write WAV with stdlib `wave`). Do not install the piper CLI or piper-tts.
- `piper_voice.py`:
  - Read the .onnx.json: `phoneme_id_map`, `audio.sample_rate`, `inference` (noise_scale, length_scale, noise_w), `num_speakers`.
  - Inspect the ONNX session's input names before hardcoding them; Piper models normally take
    `input` (int64 [1,N]), `input_lengths` (int64 [N]), `scales` (float32 [noise, length, noise_w]), and `sid` only if multi-speaker.
  - Piper id sequence: BOS `^`, then each symbol followed by pad `_`, then EOS `$` — verify against the config.
  - Phonemes are split into single codepoints for lookup (e.g. `tsʰ` → `t`,`s`,`ʰ`). Unknown codepoints: log a warning and drop, never crash.
- `symbol_map.py` + `data/piper_map.tsv`: map our inventory to symbols espeak-ng used for the same sound
  (e.g. our `ts` → espeak's `tʃ`/`ts` — whichever the map and espeak's Nepali output actually use; our `ʌ` → espeak's `ʌ`/`ə`).
  Symbols in the voice mean "what espeak labelled this sound", not strict IPA.
- `synth.py`: `uv run tts/synth.py "नेपाल" --g2p ours -o out.wav` and `--g2p espeak` (espeak-ng -v ne -q --ipa=3 → same voice).
- The first task for tts/ is a report: dump `phoneme_id_map`, list which of our phonemes have a direct match, which need mapping, and which are missing.

### Interface required by app.py (do not change these signatures)

- `tts.synth.phonemes_for(text: str, g2p: str) -> tuple[str, list[str]]`
  `g2p` is `"ours"` or `"espeak"`. Returns (human-readable phoneme string, list of Piper symbols ready for the voice).
- `tts.piper_voice.PiperVoice.load(onnx_path: Path) -> PiperVoice` (config = same path + `.json`)
- `PiperVoice.synthesize(symbols: list[str], length_scale=None, noise_scale=None, noise_w=None) -> tuple[np.ndarray, int]`
  returns (float32 mono audio in [-1, 1], sample_rate). `None` means use the config's defaults.
- `PiperVoice.last_missing: set[str]` — symbols dropped in the last call because they are not in `phoneme_id_map`.

## Streamlit frontend (app.py)

`uv add streamlit` · run with `uv run streamlit run app.py`. Already written; it imports `g2p` and `tts`
and shows backend status in the sidebar, so it works (partially) before every phase is done.
Keep app.py thin: all logic lives in `g2p/` and `tts/`.

## Listening benchmark (bench/listen.py)

For each gold word and sentence, write three files to `bench/listen/`:
`<id>_piper_ours.wav`, `<id>_piper_espeak.wav`, `<id>_espeak_raw.wav` (espeak-ng's own voice),
plus `index.html` with the text, both phoneme strings, three audio players, and a column to note which sounds correct.
Group rows by gold category so schwa cases can be heard together.

## Build phases

1. normalize, segment, mapping, phonemes.tsv, and tests for them.
2. schwa.py with S1–S4, S8, S10, S11 (orthographic only) + suffix.py.
3. Word lists (starter entries) and S0, S5–S7, S9. All tests in "Required tests" pass.
4. postrules.py.
5. bench scripts; baseline results for espeak vs rules.
6. Error loop: read errors_rules.tsv, propose rule or list fixes grouped by category, confirm before bulk edits.
7. tts/: symbol report → piper_map.tsv → piper_voice.py → synth.py (both --g2p modes) → bench/listen.py.
8. Later (ask first): fine-tune `best.ckpt` on the training audio re-phonemized with our G2P, using `piper_train_p007.yaml`.
