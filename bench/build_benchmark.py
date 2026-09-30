"""Build data/benchmark.tsv: the words whose pronunciation we trust (the benchmark).

A word is included when
  owner    the owner decided it by ear: data/exceptions.tsv, data/review_decisions.tsv or
           data/rule_review.tsv (the owner's phonemes win), or
  audio    forced alignment on the owner's recordings preferred this form and the owner accepted it
           in bulk (review_decisions.tsv decision 'audio', bench/accept_rivals.py), or
  agree    our G2P gives exactly one of Wiktionary's pronunciations (two independent sources).

The file is frozen: rebuilding keeps every existing row as it is (only a new owner decision
replaces one) and only adds new words. So after a rule change, bench/evaluate.py shows which
trusted words the change broke instead of silently re-deriving them.

Columns: word  phonemes  hybrid  basis  espeak_agrees  wiktionary
  phonemes  our inventory (CLAUDE.md), the reference pronunciation
  hybrid    exactly what the voice is given: espeak's stress/length + these phonemes (tts/hybrid.py)

uv run bench/build_benchmark.py            # after review sessions
uv run bench/build_benchmark.py --fresh    # rebuild from scratch (drops frozen rows)
"""

import argparse
import collections
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from g2p import phonemize_word  # noqa: E402
from g2p.reference import (  # noqa: E402
    espeak_ipa, espeak_to_ours, load_decisions, load_rule_verdicts, load_wiktionary, wikt_to_ours,
)
from g2p.schwa import load_exceptions  # noqa: E402
from tts.synth import hybrid_for_phonemes  # noqa: E402

BENCHMARK = ROOT / "data" / "benchmark.tsv"
HEADER = "word\tphonemes\thybrid\tbasis\tespeak_agrees\twiktionary"

logging.getLogger("g2p.suffix").setLevel(logging.WARNING)


def owner_words() -> dict[str, tuple[list[str], str]]:
    """word -> (phonemes, basis) the owner decided (later sources override earlier ones).
    basis is 'audio' for bulk-accepted alignment evidence, 'owner' for everything decided by ear."""
    out = {w: (list(p), "owner") for w, p in load_exceptions().items()}
    for w, (decision, phonemes) in load_decisions().items():
        out[w] = (phonemes.split(), "audio" if decision == "audio" else "owner")
    for (_rule, w), (_verdict, phonemes) in load_rule_verdicts().items():
        out[w] = (phonemes.split(), "owner")
    return out


def load_benchmark() -> dict[str, tuple[list[str], str]]:
    """word -> (phonemes, basis) from data/benchmark.tsv."""
    if not BENCHMARK.exists():
        return {}
    out = {}
    for line in BENCHMARK.read_text(encoding="utf-8").splitlines()[1:]:
        word, phonemes, _hybrid, basis, *_ = line.split("\t")
        out[word] = (phonemes.split(), basis)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fresh", action="store_true", help="ignore the existing file")
    args = parser.parse_args()

    wikt = load_wiktionary()
    rows = {} if args.fresh else load_benchmark()
    kept = len(rows)
    for w, decided in owner_words().items():
        rows[w] = decided
    for w, variants in wikt.items():
        if w in rows:
            continue
        ours = phonemize_word(w)
        if ours in [wikt_to_ours(v) for v in variants]:
            rows[w] = (ours, "agree")

    words = sorted(rows)
    with ThreadPoolExecutor(max_workers=16) as pool:
        espeak = dict(zip(words, pool.map(lambda w: espeak_to_ours(espeak_ipa(w)), words)))

    counts = collections.Counter()
    with open(BENCHMARK, "w", encoding="utf-8") as f:
        f.write(HEADER + "\n")
        for w in words:
            phonemes, basis = rows[w]
            hybrid = "".join(hybrid_for_phonemes(w, phonemes)).rstrip(".")
            e = "yes" if espeak[w] == phonemes else "no"
            counts[basis, e] += 1
            f.write(f"{w}\t{' '.join(phonemes)}\t{hybrid}\t{basis}\t{e}\t{' / '.join(wikt.get(w, ()))}\n")

    print(f"wrote {BENCHMARK.relative_to(ROOT)}: {len(words)} words ({len(words) - kept:+d} vs before)")
    for basis in ("owner", "audio", "agree"):
        yes, no = counts[basis, "yes"], counts[basis, "no"]
        print(f"  {basis:6} {yes + no:5}  (espeak also agrees: {yes})")


if __name__ == "__main__":
    main()
