"""Build the full word list with pronunciations: Wiktionary + Sangraha + the speech corpus transcripts.

Sources:
  wiktionary  data/lexicon.tsv (headwords and inflected forms)
  sangraha    bench/ref/sangraha_words.tsv (uv run bench/sangraha_words.py), with corpus counts
  corpus      metadata.csv transcripts (the words MFA aligns)
Pronunciation: our G2P (same as data/lexicon.tsv's phonemes column for Wiktionary words).

Output:
  bench/out/all_words.tsv   word  phonemes  sources  sangraha_count  corpus_count
  bench/out/nepali_all.dict word  phonemes   (MFA / lexicon-lookup format)

uv run bench/build_words.py [--min-count 5] [--workers 4]
"""

import argparse
import collections
import csv
import logging
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bench.mfa_prepare import transcript_words  # noqa: E402
from g2p import phonemize_word  # noqa: E402

OUT = ROOT / "bench" / "out"
SANGRAHA = ROOT / "bench" / "ref" / "sangraha_words.tsv"


def _pronounce(words: list[str]) -> list[str]:
    logging.disable(logging.WARNING)
    return [" ".join(phonemize_word(w)) for w in words]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--min-count", type=int, default=5, help="minimum Sangraha count")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--metadata", type=Path, default=ROOT / "metadata.csv")
    args = ap.parse_args()

    sources: dict[str, set[str]] = collections.defaultdict(set)
    sangraha: dict[str, int] = {}
    corpus: collections.Counter[str] = collections.Counter()
    with open(ROOT / "data" / "lexicon.tsv", encoding="utf-8") as f:
        next(f)
        for line in f:
            sources[line.split("\t", 1)[0]].add("wiktionary")
    if SANGRAHA.exists():
        with open(SANGRAHA, encoding="utf-8") as f:
            next(f)
            for line in f:
                w, c = line.rstrip("\n").split("\t")
                if int(c) >= args.min_count:
                    sangraha[w] = int(c)
                    sources[w].add("sangraha")
    else:
        print(f"{SANGRAHA.relative_to(ROOT)} missing: run `uv run bench/sangraha_words.py`")
    with open(args.metadata, encoding="utf-8") as f:
        for _, text, _ in csv.reader(f):
            corpus.update(transcript_words(text))
    for w in corpus:
        sources[w].add("corpus")

    words = sorted(sources)
    chunks = [words[i:i + 20000] for i in range(0, len(words), 20000)]
    with ProcessPoolExecutor(args.workers) as pool:
        phonemes = [p for chunk in pool.map(_pronounce, chunks) for p in chunk]

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "all_words.tsv", "w", encoding="utf-8") as ft, \
         open(OUT / "nepali_all.dict", "w", encoding="utf-8") as fd:
        ft.write("word\tphonemes\tsources\tsangraha_count\tcorpus_count\n")
        for w, ph in zip(words, phonemes):
            if not ph:
                continue
            src = ",".join(s for s in ("wiktionary", "sangraha", "corpus") if s in sources[w])
            ft.write(f"{w}\t{ph}\t{src}\t{sangraha.get(w, 0)}\t{corpus[w]}\n")
            fd.write(f"{w}\t{ph}\n")
    by_src = collections.Counter(",".join(sorted(s)) for s in sources.values())
    print(f"{len(words)} words -> bench/out/all_words.tsv, bench/out/nepali_all.dict")
    for src, n in by_src.most_common():
        print(f"  {n:>9}  {src}")


if __name__ == "__main__":
    main()
