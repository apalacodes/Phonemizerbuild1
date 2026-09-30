"""Build the vocabulary + pronunciation lexicon from Wiktionary words, pronounced by our hybrid G2P.

Words: every Nepali headword in the kaikki.org Wiktionary dump plus every inflected form listed
in its declension/conjugation tables (single Devanagari words only).
Pronunciation: our G2P (segments, schwa) and the hybrid string (espeak stress/length + our
segments) that the voice is given. Wiktionary's IPA is kept as a reference column only.

Split: headwords with hand-edited Wiktionary IPA are the held-out test set; their inflected
forms are test too, so nothing about them leaks into training. Everything else is train.

Output:
  data/lexicon.tsv               word  source  lemma  split  phonemes  hybrid  wiktionary  agrees
  bench/out/lexicon_review.tsv   train headwords where our phonemes disagree with Wiktionary

uv run bench/build_lexicon.py
"""

import collections
import json
import logging
import re
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from g2p.reference import (  # noqa: E402
    KAIKKI, espeak_ipa, heldout_words, load_wiktionary, wikt_to_ours,
)
from tts.synth import DEFAULT_SCHWA, _ours_word  # noqa: E402
from tts.hybrid import fix_word  # noqa: E402

LEXICON = ROOT / "data" / "lexicon.tsv"
REVIEW = ROOT / "bench" / "out" / "lexicon_review.tsv"
DEVANAGARI = re.compile(r"^[ऀ-ॿ]+$")
SKIP_POS = {"character", "suffix", "prefix", "infix"}

logging.getLogger("g2p.suffix").setLevel(logging.WARNING)


def collect_words() -> dict[str, tuple[str, str]]:
    """word -> (source, lemma). source is 'headword' or 'form'; a headword wins over a form."""
    words: dict[str, tuple[str, str]] = {}
    forms: dict[str, str] = {}
    with open(KAIKKI, encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            lemma = unicodedata.normalize("NFC", e["word"])
            if not DEVANAGARI.match(lemma) or e.get("pos") in SKIP_POS:
                continue
            words[lemma] = ("headword", lemma)
            for form in e.get("forms", []):
                w = unicodedata.normalize("NFC", form.get("form", ""))
                if DEVANAGARI.match(w):
                    forms.setdefault(w, lemma)
    for w, lemma in forms.items():
        words.setdefault(w, ("form", lemma))
    return words


def main() -> None:
    if not KAIKKI.exists():
        sys.exit("Wiktionary dump missing: run `uv run bench/wiktionary.py` first")
    t0 = time.time()
    words = collect_words()
    wikt = load_wiktionary()
    heldout = heldout_words()
    order = sorted(words)
    print(f"{len(order)} words ({sum(s == 'headword' for s, _ in words.values())} headwords); "
          f"running espeak-ng…")
    with ThreadPoolExecutor(max_workers=16) as pool:
        espeak = dict(zip(order, pool.map(espeak_ipa, order)))

    rows, review = [], []
    counts = collections.Counter()
    for w in order:
        source, lemma = words[w]
        split = "test" if lemma in heldout or w in heldout else "train"
        phonemes, final_schwa = _ours_word(w)
        hybrid = fix_word(espeak[w], phonemes, final_schwa, DEFAULT_SCHWA)
        variants = wikt.get(w, ())
        if variants:
            refs = [wikt_to_ours(v) for v in variants]
            agrees = "yes" if phonemes in refs else "no"
            if agrees == "no" and split == "train" and source == "headword":
                review.append((w, " ".join(phonemes), " / ".join(" ".join(r) for r in refs), " / ".join(variants)))
        else:
            agrees = ""
        counts[split, agrees or "-"] += 1
        rows.append((w, source, lemma, split, " ".join(phonemes), hybrid, " / ".join(variants), agrees))

    with open(LEXICON, "w", encoding="utf-8") as f:
        f.write("word\tsource\tlemma\tsplit\tphonemes\thybrid\twiktionary\tagrees\n")
        for r in rows:
            f.write("\t".join(r) + "\n")
    REVIEW.parent.mkdir(parents=True, exist_ok=True)
    with open(REVIEW, "w", encoding="utf-8") as f:
        f.write("word\tours\twiktionary_phonemes\twiktionary_ipa\n")
        for r in review:
            f.write("\t".join(r) + "\n")

    print(f"wrote {LEXICON.relative_to(ROOT)}: {len(rows)} rows in {time.time() - t0:.0f}s")
    for split in ("train", "test"):
        n = sum(v for (s, _), v in counts.items() if s == split)
        yes, no = counts[split, "yes"], counts[split, "no"]
        print(f"  {split:5} {n:6} words; with Wiktionary IPA: {yes + no} (agree {yes}, disagree {no})")
    print(f"wrote {REVIEW.relative_to(ROOT)}: {len(review)} train headwords to review")


if __name__ == "__main__":
    main()
