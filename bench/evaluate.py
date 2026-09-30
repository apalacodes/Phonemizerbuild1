"""Score G2P systems against the benchmark (data/benchmark.tsv, built by bench/build_benchmark.py).

Systems: espeak (espeak-ng -v ne, mapped to our inventory) and rules (our G2P).
Reports word accuracy (1 - WER), PER (Levenshtein / reference length), both per basis
(owner = decided by ear, audio = accepted from forced alignment, agree = our G2P and Wiktionary
agreed when the word was added),
errors by kind and words/second. Appends a dated row per system to bench/results.md and writes
bench/out/errors_<system>.tsv.

The benchmark is frozen, so for our rules this is a regression check: every error is a trusted
word that a later change broke. For espeak (or any new system) it is a real benchmark.

uv run bench/evaluate.py
"""

import datetime
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from g2p import phonemize_word  # noqa: E402
from g2p.compare import espeak_ipa, espeak_to_ours, score  # noqa: E402

BENCHMARK = ROOT / "data" / "benchmark.tsv"
OUT = ROOT / "bench" / "out"
RESULTS = ROOT / "bench" / "results.md"

logging.getLogger("g2p.suffix").setLevel(logging.WARNING)

SYSTEMS = {
    "espeak": lambda w: espeak_to_ours(espeak_ipa(w)),
    "rules": phonemize_word,
}


def load_benchmark() -> list[tuple[str, str, list[str]]]:
    """(word, basis, phonemes) rows."""
    rows = []
    for line in BENCHMARK.read_text(encoding="utf-8").splitlines()[1:]:
        word, phonemes, _hybrid, basis, *_ = line.split("\t")
        rows.append((word, basis, phonemes.split()))
    return rows


def main() -> None:
    if not BENCHMARK.exists():
        sys.exit("data/benchmark.tsv missing: run `uv run bench/build_benchmark.py` first")
    bench = load_benchmark()
    OUT.mkdir(parents=True, exist_ok=True)
    today = datetime.date.today().isoformat()
    results = []
    for name, system in SYSTEMS.items():
        r = score(bench, system)
        with open(OUT / f"errors_{name}.tsv", "w", encoding="utf-8") as f:
            f.write("word\tbasis\tsystem\tbenchmark\tkind\n")
            for e in r["errors"]:
                f.write("\t".join(e[:5]) + "\n")
        results.append((name, r["acc"], r["per"], r["wps"], r["per_basis"], r["kinds"]))

    n = len(bench)
    print(f"benchmark: {n} words ({BENCHMARK.relative_to(ROOT)})\n")
    print(f"{'':28}" + "".join(f"{r[0]:>12}" for r in results))
    print(f"{'word accuracy (1 - WER)':28}" + "".join(f"{r[1]:>12.1%}" for r in results))
    print(f"{'PER':28}" + "".join(f"{r[2]:>12.1%}" for r in results))
    print(f"{'words / second':28}" + "".join(f"{r[3]:>12.0f}" for r in results))
    print("\nper basis (word accuracy / PER):")
    for b in ("owner", "audio", "agree"):
        cnt = results[0][4].get(b, [0, 0])[1]
        if cnt:
            print(f"  {b:12} n={cnt:4}  " + "".join(
                f"{r[4][b][0] / cnt:>8.1%} /{r[4][b][2] / r[4][b][3]:>5.1%}" for r in results))
    print("\nerrors by kind:")
    for k in sorted({k for r in results for k in r[5]}):
        print(f"  {k:40}" + "".join(f"{r[5][k]:>8}" for r in results))

    new = not RESULTS.exists()
    with open(RESULTS, "a", encoding="utf-8") as f:
        if new:
            f.write("# Benchmark results (data/benchmark.tsv)\n\n")
            f.write("| date | system | words | word acc | PER | words/s |\n|---|---|---|---|---|---|\n")
        for name, acc, per, wps, _, _ in results:
            f.write(f"| {today} | {name} | {n} | {acc:.1%} | {per:.1%} | {wps:.0f} |\n")
    print(f"\nerrors: {OUT.relative_to(ROOT)}/errors_<system>.tsv · results appended to {RESULTS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
