"""Accept automatically the rival pronunciations that forced alignment preferred with strong evidence.

A suspect (bench/out/mfa/suspects.tsv) is accepted when the rival won at least --min-share of the
word's tokens, over at least --min-tokens tokens, from at least --min-speakers different speakers.
The rival then becomes the word's pronunciation:
  data/review_decisions.tsv   decision 'audio' (so alignment evidence stays distinct from decisions by ear)
  data/exceptions.tsv         under its own section header (rule S0); an older entry for the word is replaced
Candidates: undecided words, and words whose earlier 'audio' decision the new run overturned (rival_rules:
the rules' own form won). Never touched: words decided by ear (ours / rival / custom / wiktionary /
W5 verdicts) and protected words (required tests) with their stems. Weaker evidence stays in the app's
Audio check tab for the owner's ear.

Undo: delete the 'audio' rows from review_decisions.tsv and that section of exceptions.tsv.

uv run bench/accept_rivals.py [--min-share 0.7] [--min-tokens 3] [--min-speakers 2] [--dry-run]
The first bulk accept (2026-09-29, one speaker) used --min-share 0.5 --min-tokens 1 --min-speakers 1.
"""

import argparse
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from g2p import phonemize_word, schwa  # noqa: E402
from g2p.alignment import load_suspects  # noqa: E402
from g2p.normalize import normalize  # noqa: E402
from g2p.reference import DECISIONS_TSV, load_decisions, load_rule_verdicts  # noqa: E402
from g2p.suffix import split_suffixes  # noqa: E402

SECTION = "# Audio check: rival chosen by forced alignment, accepted in bulk (bench/accept_rivals.py)"

logging.disable(logging.WARNING)


def protected_words() -> set[str]:
    """Words whose pronunciation must not move: required rule tests and W5 verdicts, plus their stems."""
    required = re.findall(r'^    \("([^"]+)", "', (ROOT / "tests" / "test_rules.py").read_text(encoding="utf-8"), re.M)
    words = set(required) | {w for _, w in load_rule_verdicts()}
    return words | {split_suffixes(normalize(w))[0] for w in words}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--min-share", type=float, default=0.7, help="rival share of the word's tokens")
    ap.add_argument("--min-tokens", type=int, default=3, help="aligned tokens of the word")
    ap.add_argument("--min-speakers", type=int, default=2, help="different speakers who chose the rival")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    decided = load_decisions()
    exceptions = schwa.load_exceptions()
    protected = protected_words()
    accept, skipped, weak = [], [], 0
    for r in load_suspects():
        w = r["word"]
        by_ear = w in decided and decided[w][0] != "audio"
        if by_ear or (w in exceptions and w not in decided):  # decided by ear, or a hand-listed exception
            continue
        strong = (r["rival"] >= args.min_share * r["tokens"] and r["tokens"] >= args.min_tokens
                  and int(r.get("rival_speakers") or 1) >= args.min_speakers)
        if not strong:
            weak += 1
            continue
        (skipped if w in protected else accept).append(r)
    print(f"accepting {len(accept)} rivals (share >= {args.min_share}, tokens >= {args.min_tokens}, "
          f"speakers >= {args.min_speakers}), {sum(r['rival_kind'] == 'rival_rules' for r in accept)} of them "
          f"overturning an earlier audio decision; {weak} weaker suspects left for the Audio check tab; "
          f"skipped as protected: {' '.join(r['word'] for r in skipped) or '-'}")
    if args.dry_run or not accept:
        return

    for r in accept:
        decided[r["word"]] = ("audio", r["rival_phonemes"])
    with open(DECISIONS_TSV, "w", encoding="utf-8") as f:
        f.write("word\tdecision\tphonemes\n")
        for w in sorted(decided):
            f.write(f"{w}\t{decided[w][0]}\t{decided[w][1]}\n")

    path = schwa.DATA_DIR / "exceptions.tsv"
    replaced = {normalize(r["word"]) for r in accept}
    lines = [line for line in path.read_text(encoding="utf-8").splitlines()
             if line.startswith("#") or not line.strip() or normalize(line.split("\t", 1)[0]) not in replaced]
    if SECTION not in lines:
        lines.append(SECTION)
    lines += [f"{r['word']}\t{r['rival_phonemes']}" for r in sorted(accept, key=lambda r: r["word"])]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    schwa.load_exceptions.cache_clear()

    wrong = [r["word"] for r in accept if " ".join(phonemize_word(r["word"])) != r["rival_phonemes"]]
    print(f"wrote {DECISIONS_TSV.relative_to(ROOT)} and {path.relative_to(ROOT)}; "
          f"{len(accept) - len(wrong)} of {len(accept)} now pronounced as accepted" + (f"; check {wrong[:10]}" if wrong else ""))


if __name__ == "__main__":
    main()
