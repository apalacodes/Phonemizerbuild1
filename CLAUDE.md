# deephoneme — Nepali G2P (Phonemizer)

A rule-based Nepali grapheme-to-phoneme converter. The spoken output is the **hybrid**: espeak-ng's
prosody (stress, vowel length) with our G2P's segments and schwa decisions. Accuracy on Nepali schwa
(inherent vowel /ʌ/) deletion is the main goal. espeak-ng and Wiktionary are references, not truth;
the owner's ear decides. Listening uses **Kokoro-82M** (Hindi voices), which reads IPA directly.

Next step: verify pronunciations against audio with forced alignment (Montreal Forced Aligner on
OpenSLR-43): words the aligner fits worst are candidate transcription errors.

## Project layout

```
data/
  phonemes.tsv          # grapheme \t phoneme \t type (consonant/vowel/matra/sign)
  pronouns.txt adverbs.txt postpositions.txt verb_endings.txt suffixes.txt loanwords.txt
                        # word lists for the schwa rules (linguist-editable)
  exceptions.tsv        # word \t phonemes  (full override, rule S0; owner decisions land here)
  ipa_map.tsv           # our phoneme -> espeak-style IPA symbol (what the voice reads)
  hybrid_keep_espeak.tsv# (espeak segment, our phoneme) pairs where espeak's sound is kept (क्ष ʂ)
  review_decisions.tsv  # owner's Review-tab decisions (ours / wiktionary / custom / list name)
  rule_review.tsv       # owner's verdicts from the finished W5 check (right/wrong/custom)
  lexicon.tsv           # 54,640 Wiktionary words + forms: phonemes, hybrid, wiktionary, split
  benchmark.tsv         # THE BENCHMARK: trusted words (owner-decided or ours == Wiktionary)
g2p/
  __init__.py           # phonemize(text), phonemize_word(word), analyze_word(word)
  __main__.py           # CLI `deephoneme`: text, stdin stream, --explain, --serve PORT, --log-new
  paths.py              # DATA_DIR: bundled g2p/data/ in a wheel, else repo data/
  alignment.py          # MFA TextGrids: suspects, word clips from the recordings (Audio check tab)
  variants.py           # ours + rival schwa pronunciations for forced alignment (rivals are NOT corrections)
  compare.py            # espeak-ng -> our inventory, diff_kind, edit distance, PER scoring (stdlib only)
  newwords.py           # opt-in review queue: words not in the lexicon -> new_words.tsv (never exceptions)
  normalize.py segment.py mapping.py suffix.py schwa.py postrules.py
  reference.py          # Wiktionary converters, review helpers (re-exports compare's espeak helpers)
tts/
  ipa_map.py            # our phonemes -> IPA symbols (data/ipa_map.tsv)
  hybrid.py             # align espeak's IPA with our phonemes, keep espeak's stress/length
  synth.py              # text -> (display, voice symbols) for modes ours/espeak/hybrid/wiktionary; CLI
  kokoro_voice.py       # Kokoro-82M ONNX voice (onnxruntime), write_wav
bench/
  wiktionary.py         # download kaikki dump + {{ne-IPA}} args; espeak vs ours vs Wiktionary
  build_lexicon.py      # -> data/lexicon.tsv, bench/out/lexicon_review.tsv
  build_benchmark.py    # -> data/benchmark.tsv (frozen: existing rows are kept)
  evaluate.py           # score espeak and our rules on data/benchmark.tsv -> bench/results.md
  sangraha_words.py     # word counts from AI4Bharat Sangraha synthetic/npi_Deva -> ref/sangraha_words.tsv
  build_words.py        # Wiktionary + Sangraha + corpus words, our phonemes -> out/all_words.tsv, out/nepali_all.dict
  mfa_prepare.py        # metadata.csv + datasets/openslr43 -> out/mfa/corpus (a folder per speaker) + nepali.dict
  mfa_report.py         # MFA TextGrids -> out/mfa/suspects.tsv (with speaker counts), rule_agreement.tsv
  accept_rivals.py      # auto-accept strong rivals (>= 70% of >= 3 tokens, >= 2 speakers) -> exceptions (basis audio)
  ref/                  # kaikki-nepali.jsonl, sangraha_words.tsv (gitignored), ne_ipa_args.tsv (owner-edited)
  out/                  # generated reports (gitignored)
release/                # export.py -> ../deephoneme: clean standalone repo (package + speech/, data, lexicon.dict, test.py, app.py, README)
                        # export_apalas.py -> ../apalas_phonemizer: phonemizer + voice + one app (compare with
                        # espeak-ng, benchmark vs ground_truth.tsv or an uploaded file); templates in release/apalas/
models/kokoro/          # GITIGNORED: kokoro-v1.0.onnx, voices-v1.0.bin, config.json
datasets/               # GITIGNORED speech corpora: openslr43/ (Google Nepali TTS, multi-speaker, CC BY-SA 4.0)
app.py                  # Streamlit: listen, review words, browse Wiktionary, IPA lab, Benchmark, Audio check
check_phoneme.py        # Streamlit: sentence breakdown + audio per word; espeak vs ours benchmark (PER)
tests/                  # pytest; one test per rule
```

## Environment: uv ONLY

This project uses **uv** for everything. Never use pip, venv, virtualenv, poetry, or conda.

- Add deps: `uv add editdistance` · dev deps: `uv add --dev pytest`
- Run code: `uv run python -m g2p ...` · `uv run bench/evaluate.py`
- Run tests: `uv run pytest`
- Sync env: `uv sync`
- Dependencies live in `pyproject.toml` + `uv.lock`; never create requirements.txt.

## Bundling (the deliverable)

The phonemizer is named **deephoneme**: wheel `deephoneme`, command `deephoneme`, `import deephoneme` (a thin
facade; the code stays in `g2p`). Standard library only, no deps.
`uv build` -> `dist/deephoneme-<ver>-py3-none-any.whl`; the wheel carries a copy of the run-time data
(phonemes.tsv, exceptions.tsv, the six word lists) in `g2p/data/` (pyproject force-include; g2p/paths.py).
Rebuild the wheel after any owner decision, or it ships the old exceptions.
Clean standalone repo for others: `uv run release/export.py` (rewrites ../deephoneme, keeps its .git; lexicon = Sangraha >= 50x
+ Wiktionary + corpus + benchmark + exceptions; `--min-count 5` gives ~3.1M words / 155 MB, too big for GitHub). Bump `version` for a release.
Use: `uv add ./deephoneme-*.whl` (or pip), then `deephoneme "text"`, pipe lines through `deephoneme`,
`deephoneme --serve 8000` (HTTP JSON), or `from deephoneme import phonemize, phonemize_word`. App/voice/benchmark deps are the `app` dependency group.

## Conventions

- Python 3.12 (pinned), standard library first. Deps: `editdistance`, `onnxruntime` + `numpy` (voice), `streamlit` (app), `pytest` (dev).
- All word lists live in `data/` as plain UTF-8 text so a linguist can edit them. No word lists hard-coded in Python.
- Output format: phonemes as a list; string form is space-separated, words separated by ` | `.
- Every rule in `schwa.py` has a docstring naming the rule ID below and at least one test.
- Do not tune rules by looking up benchmark or held-out words. Fix errors by improving a rule or adding to `exceptions.tsv` / a word list.
- The shell exports ROS Foxy on PYTHONPATH; pyproject sets `--disable-plugin-autoload` for pytest because of it.

## Phoneme inventory (the output contract — use only these symbols)

Vowels: `i e a ʌ o u`; nasalized: `ĩ ẽ ã ʌ̃ ũ` (õ allowed as free variant); diphthongs `ʌi ʌu` (for ऐ औ), nasalized `ʌĩ ʌũ` (ऐं औं).

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
| ल | l | व | b / w (see POST-2) | श ष स | s |
| ह | ɦ | ज्ञ | g j | क्ष | k tsʰ |

Independent vowels / matras: अ ʌ · आ ा a · इ ि ई ी i · उ ु ऊ ू u · ए े e · ऐ ै ʌi · ओ ो o · औ ौ ʌu · ऋ ृ r i.
Signs: ् halanta (no vowel) · ँ nasalize preceding vowel · ं see POST-1 · ः visarga → ɦ (rare, loanwords).

Note: Nepali च-series are alveolar affricates (ts dz), NOT Hindi tʃ dʒ. Long/short i/u are not distinguished.

## Schwa rules (schwa.py)

Apply to every consonant akshara that has no matra and no halanta. First matching rule wins.
Run suffix splitting first; "final" means final in the stem when a case suffix was removed.

| ID | Condition | Decision |
|---|---|---|
| S0 | Word (or stem) in `exceptions.tsv` | use lexicon entry |
| S1 | Next unit is a halanta-consonant (conjunct follows), or ं / ँ follows | KEEP |
| S2 | First akshara of the word | KEEP |
| S3 | Not final (Nepali rarely deletes medially; medial syncope W5 was rejected by ear, 13/68) | KEEP |
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
- POST-2: व → b word-initially and after ं (वर्षा, संवाद); w elsewhere (rule W1: मानव, अदुवा). Owner decision 2026-09-28.
- POST-3: ँ → add combining tilde to the preceding vowel.

## Required tests (tests/test_rules.py) — word → expected phonemes

```
कमल      k ʌ m ʌ l          S11
समय      s ʌ m ʌ j          S0 (owner, audio check; S8 alone would give s ʌ m ʌ j ʌ)
कस्तो     k ʌ s t̪ o          S1
झन्      dzʱ ʌ n            halanta
गुरुङ     g u r u ŋ          S4
रङ       r ʌ ŋ              S4
माघ      m a gʱ             S11
कारण     k a r ʌ n          S11
साथ      s a t̪ʰ             S11
देश      d̪ e s              S11
मानव     m a n ʌ w          S11, POST-2
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

`tests/test_review.py::test_owner_decided_words_keep_their_pronunciation` guards every word the owner
decided by ear (exceptions, review_decisions.tsv, rule_review.tsv): a change that alters any of them fails.

## Benchmark (data/benchmark.tsv)

Columns: `word  phonemes  hybrid  basis  espeak_agrees  wiktionary`.
- `phonemes` is the reference pronunciation in our inventory; `hybrid` is exactly what the voice is given.
- `basis`: **owner** = decided by ear (exceptions, review_decisions, rule_review; owner's phonemes win);
  **audio** = forced alignment on the owner's recordings chose it and the owner accepted it in bulk;
  **agree** = our G2P gave one of Wiktionary's pronunciations when the word was added.
- Frozen: `build_benchmark.py` keeps existing rows and only adds words (`--fresh` rebuilds). For our
  rules `evaluate.py` is therefore a regression check (should stay 100%); for espeak or any new
  system it is a real benchmark.
- Held-out split: words with editor-supplied `{{ne-IPA|...}}` in `bench/ref/ne_ipa_args.tsv` are
  `test` in lexicon.tsv; never tune rules on them.

After a review session: `uv run bench/build_lexicon.py && uv run bench/build_benchmark.py && uv run bench/evaluate.py`.

## Forced alignment (MFA)

Corpora: the owner's `metadata.csv` (wav,text,speaker; 3,736 utterances, speaker asmita), audio in
`/root/work/TTS/datawork/wavs` (24 kHz mono); and OpenSLR SLR43 in `datasets/openslr43/`
(line_index.tsv: file id<TAB>text; speaker = first two parts of the id, nep_0258). `mfa_prepare.py`
uses both (`--no-slr43` for the owner's only). MFA 3.4 lives OUTSIDE the repo in a micromamba env:

```
uv run bench/mfa_prepare.py
export MAMBA_ROOT_PREFIX=~/mfa/root MFA_ROOT_DIR=~/mfa/work
cd bench/out/mfa && ~/mfa/bin/micromamba run -n mfa mfa train corpus nepali.dict nepali_acoustic.zip \
    --output_directory aligned --clean -j 4          # several speakers: no --single_speaker
uv run bench/mfa_report.py
uv run bench/accept_rivals.py --dry-run            # then without --dry-run; then rebuild (below)
```

Words whose pronunciation came from an earlier alignment (decision `audio`) get the pure-rule form as
their rival (`rival_rules`), so every run re-tests them; `mfa_report.py` lists them as rule `audio-retest`.

The dictionary gives each word our pronunciation plus rival schwa forms; a word whose tokens pick a
rival is a suspect for the owner's ear (suspects.tsv), not an automatic correction.

Fixing suspects: app tab **Audio check** plays the word cut from the recordings (g2p/alignment.py),
then ours / rival / custom through Kokoro. "Rival" and "mine" go to `exceptions.tsv` (S0) and
`review_decisions.tsv`; "ours" is recorded as confirmed. Then rebuild the dictionaries:
`uv run bench/mfa_prepare.py && uv run bench/build_words.py` (and the lexicon/benchmark commands above).
Bulk: the owner accepted all rivals that won >= 50% of a word's tokens (2026-09-29, 1,323 words, one
speaker). Since then `uv run bench/accept_rivals.py` is strict by default: rival >= 70% of >= 3 tokens
from >= 2 speakers (owner decision 2026-09-30). It writes decision `audio` + its own section in
exceptions.tsv (replacing an older entry of the word), may overturn an earlier `audio` decision when
the rules' form wins, and never touches words decided by ear or protected words/stems (required
tests, W5 verdicts). Weaker suspects stay in the Audio check tab. Benchmark basis `audio` marks them.

New words: `DEEPHONEME_NEW_WORDS=<file>` (or CLI `--log-new`) appends words the lexicon lacks to a
review queue; nothing reaches exceptions.tsv without evidence (ear or alignment).

## Speech (tts/)

- Modes (`tts.synth.phonemes_for(text, g2p)` -> (display string, voice symbols)):
  `hybrid` (default, the main system), `ours`, `espeak`, `wiktionary` (reference; ours where missing, marked *).
- A kept stem-final schwa is voiced as the medium `ˌə` (DEFAULT_SCHWA). One-syllable words keep theirs as is.
- Kokoro vocab lacks ʱ and ̪; `c ɟ` (espeak's labels for च ज) are sent as `ʦ ʣ`.
- CLI: `uv run tts/synth.py "नेपाल" --g2p hybrid -o out.wav`
- App: `uv run streamlit run app.py`. Keep app.py thin: all logic lives in `g2p/` and `tts/`.

## History

Phases 1-4 (normalize/segment/mapping, schwa rules, word lists, post-rules) are done.
The Piper voice (espeak-trained) was dropped for Kokoro. Experimental rules W2-W5 were tried against
Wiktionary and by ear and rejected; only W1 (व -> w, now POST-2) was adopted.
