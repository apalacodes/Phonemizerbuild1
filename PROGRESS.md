# Nepali G2P — progress log

Status as of 2026-09-28. For how to run things, see `CLAUDE.md`.

## Goal

A rule-based Nepali grapheme-to-phoneme (G2P) converter that gets **schwa deletion** right, since this is
where existing tools fail. It should come with a trustworthy pronunciation lexicon and a voice
that speaks our phonemes, so every decision can be checked by ear.

## What was done

### 1. Rule-based G2P (phases 1–4)
- Pipeline: normalize → akshara segmentation → suffix split → schwa rules S0–S11 → mapping with post-rules POST-1..3.
- Word lists in `data/` that a linguist can edit:
  - 42 pronouns
  - 8 adverbs
  - 13 postpositions
  - 13 verb endings
  - 13 suffixes
  - 40 loanwords
- The required test words from `CLAUDE.md` all pass. There are 182 tests in total.

### 2. Compared against references
- **Wiktionary** (kaikki.org dump): 1,762 words have usable IPA.
  - The 279 words whose IPA an editor wrote by hand are held out as a test split.
  - Our G2P matched Wiktionary on **82.2%** of dev words, against **63.7%** for espeak-ng.
  - On the hand-edited held-out words, both systems scored only about **32–34%**. The main error type was medial schwa.
- **espeak-ng** is kept as a baseline and as the source of prosody. It is not treated as the truth.

### 3. Rules tried and decided by ear
| Rule | What it does | Outcome |
|---|---|---|
| W1 | व → w except word-initially and after ं (मानव m a n ʌ w) | **Adopted** (now POST-2) |
| W2 | drop medial ह (कोही k o i) | Rejected |
| W3 | breathy stops lose breathiness after the first sound | Rejected |
| W4 | C + य + schwa → e | Rejected |
| W5 | medial schwa syncope (सरकार s ʌ r k a r) | **Rejected**: right on only 13 of 68 words. It fails on compounds (आइतबार) and on न- negative verbs (नचलेर). |

Rules were never tuned on the held-out words.

### 4. The hybrid pronunciation (main system)
- espeak-ng supplies the prosody (stress, vowel length). Our G2P supplies the segments and schwa decisions.
- The two are aligned per word with Levenshtein distance.
- Exceptions:
  - espeak's ʂ is kept for क्ष (it sounded better).
  - A kept stem-final schwa is voiced as a medium `ˌə`.
- The hybrid string is exactly what the voice receives.

### 5. Voice
- The Piper voice (trained on espeak labels, so it learned espeak's mistakes) was dropped.
- It was replaced by **Kokoro-82M** (Hindi voices, hm_omega by default), which reads IPA directly. The hybrid spoken by Kokoro "sounds much better".
- Limitation: Kokoro's vocabulary has no ʱ (breathy) and no ̪ (dental), so the voice can't make these contrasts.

### 6. Lexicon and manual review
- **`data/lexicon.tsv`**: 54,640 words (Wiktionary headwords plus inflected forms), each with our phonemes, the hybrid string and Wiktionary's IPA.
- The Review tab in `app.py` compares ours, Wiktionary and your own version by ear. Decisions so far:
  - 48 word reviews:
    - 34 keep ours
    - 8 custom
    - 3 use Wiktionary
    - 3 added to the loanword list
  - 68 W5 verdicts:
    - 54 W5 wrong
    - 13 W5 right
    - 1 custom
  - 38 exceptions in `data/exceptions.tsv`.
- A test (`test_owner_decided_words_keep_their_pronunciation`) fails if any change alters a word decided by ear.

### 7. Benchmark — `data/benchmark.tsv` (1,675 words)
| Basis | Words | espeak also agrees |
|---|---|---|
| owner (decided by ear) | 129 | 72 |
| agree (our G2P = Wiktionary) | 1,546 | 1,157 |

- The file is **frozen**: rebuilding only adds words, and only a new owner decision replaces a row.
- Current scores (`uv run bench/evaluate.py`):

  | | Word accuracy | PER |
  |---|---|---|
  | espeak-ng | 73.4% (55.8% on owner words) | 5.9% |
  | our rules | 100% | 0% |

  Our 100% holds by construction, so it is a regression alarm, not an accuracy claim.

### 8. Cleanup
- Removed Piper, the rejected rules W2–W5, the old gold set and stray files.
- The repo now contains `g2p/`, `tts/`, `bench/`, `data/`, `tests/`, `app.py` and `CLAUDE.md`.

## Known open issues
- नगरपालिका is wrongly split as नगरपालि + का (suffix splitter).
- 291 train headwords where our G2P and Wiktionary disagree; about 48 reviewed so far.
- Nasalization cases have not been reviewed yet.
- Missing pause/break word list (espeak's `$pause` words) for sentence rhythm.
- The benchmark has no audio evidence yet. "Correct" means your ear or two text sources agreeing.

## Next steps: verify pronunciations against real audio

Dataset: the owner's OpenSLR Nepali speech corpus (7+ hours of audio with transcripts).
Tool: **Montreal Forced Aligner (MFA)**.

1. **Environment.** MFA is distributed through conda, which conflicts with this project's uv-only
   rule. Run it in its own environment or Docker, outside this repo, and exchange plain files only.
2. **Corpus.** Convert the dataset to MFA's layout: one `.wav` and one `.lab` transcript per
   utterance, grouped by speaker. Normalize transcripts with `g2p.normalize` so the words match the lexicon.
3. **Coverage.** List every transcript word. Look up words already in `lexicon.tsv`, and send the rest
   (out-of-vocabulary, OOV) through our G2P, marking them `oov` for later review.
4. **Dictionary with variants.** Export `word<TAB>phonemes`. For words where schwa is uncertain,
   add both versions (e.g. `घर gʱ ʌ r` and `gʱ ʌ r ʌ`, or the medial-syncope form).
   MFA picks the variant that fits the audio best, which gives direct evidence per word.
5. **Train and align.** No pretrained Nepali MFA model is assumed, so train one on the 7 hours
   (`mfa train`), then align the corpus.
6. **Find suspect words.** Flag words where:
   - MFA chose a different variant than our G2P;
   - a phone sits at the minimum duration, e.g. a schwa that isn't really there;
   - acoustic likelihood is low.
   Rank the suspects by frequency.
7. **Feed back.** Load the suspects into the app's Review tab together with the real audio clip.
   Decisions go to `exceptions.tsv` or become rule and word-list changes, as before.
8. **Benchmark.** Add an **audio** basis to `benchmark.tsv` for words confirmed by alignment.
   Report how often each schwa rule (S1–S11) agrees with the audio.

## Future direction
- **Audio-verified lexicon.** Grow the lexicon from "text sources agree" to "real speakers say it this way".
- **Rules from evidence.** Use the alignment statistics to design narrower rules. For example, a
  medial-syncope rule limited to the patterns where speakers really delete the schwa, instead of W5's broad version.
- **A Nepali voice trained on our phonemes.** Train or fine-tune a TTS voice on the OpenSLR audio
  re-phonemized with the hybrid G2P. It would keep the breathy and dental contrasts that Kokoro drops,
  and it wouldn't learn espeak's mistakes.
- **Neural fallback for unseen words.** Train a small G2P model on the verified lexicon for words
  the rules and lists don't cover, with the rules staying the first choice.
- **Sentence level.** Pause words, number and date reading, and clause-context stress.
