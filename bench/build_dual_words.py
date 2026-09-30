"""Build the dual-words deck: words that the owner's sentence ground truths pronounce two (or more)
ways depending on the sentence, e.g. दिन "day" d̪ i n vs "to give" d̪ i n ʌ.

A word-by-word phonemizer can give only one form, so these words are listed on the side instead of
being fixed in exceptions.tsv. The `note` column is for the owner (meaning of each form) and is kept
when the deck is rebuilt.

Input:  data/ground_truth*sentences.tsv
Output: data/dual_words.tsv   word  ours  form  count  example  ...  note   (one row per form)

uv run bench/build_dual_words.py
"""

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from g2p import phonemize_word  # noqa: E402
from g2p.compare import dual_words, load_sentences  # noqa: E402

DECK = ROOT / "data" / "dual_words.tsv"
HEADER = "word\tform\tcount\tours\texample\tsource\tnote"

logging.disable(logging.WARNING)


def main() -> None:
    notes = {}
    if DECK.exists():
        for line in DECK.read_text(encoding="utf-8").splitlines()[1:]:
            cols = line.split("\t")
            if len(cols) == 7 and cols[6]:
                notes[cols[0], cols[1]] = cols[6]
    rows = []
    for gt in sorted((ROOT / "data").glob("ground_truth*sentences.tsv")):
        _, sentences = load_sentences(gt)
        for word, forms in dual_words(sentences).items():
            ours = " ".join(phonemize_word(word))
            for form, examples in sorted(forms.items(), key=lambda f: -len(f[1])):
                rows.append((word, form, len(examples), ours, examples[0], gt.name, notes.get((word, form), "")))
    total: dict[str, int] = {}
    for r in rows:
        total[r[0]] = total.get(r[0], 0) + r[2]
    rows.sort(key=lambda r: (-total[r[0]], r[0], -r[2]))  # most frequent word first
    with open(DECK, "w", encoding="utf-8") as f:
        f.write(HEADER + "\n")
        for r in rows:
            f.write("\t".join(map(str, r)) + "\n")
    words = sorted(total, key=lambda w: -total[w])
    print(f"{len(words)} dual words ({len(rows)} forms) -> {DECK.relative_to(ROOT)}: {' '.join(words)}")


if __name__ == "__main__":
    main()
