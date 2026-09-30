# /// script
# requires-python = ">=3.12"
# dependencies = ["pyarrow"]
# ///
"""Count every Nepali word in AI4Bharat Sangraha (synthetic/npi_Deva, ~15.7 GB, 64 parquet shards).

Each shard is downloaded to bench/out/sangraha/, counted, and deleted, so disk use stays at a few
shards. Per-shard counts are kept (counts_NNNN.tsv), so an interrupted run resumes where it stopped.
Words are runs of Devanagari letters (digits and danda split them), normalized with g2p.normalize.

Output: bench/ref/sangraha_words.tsv   word  count   (words seen at least --min-count times)

uv run bench/sangraha_words.py [--workers 4] [--min-count 2]
"""

import argparse
import collections
import re
import sys
import urllib.request
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from g2p.normalize import normalize  # noqa: E402

BASE = "https://huggingface.co/datasets/ai4bharat/sangraha/resolve/main/synthetic/npi_Deva/"
SHARDS = [f"wiki_npi_Deva_{i:04d}_of_0063.parquet" for i in range(64)]
WORK = ROOT / "bench" / "out" / "sangraha"
OUT = ROOT / "bench" / "ref" / "sangraha_words.tsv"

# Devanagari block minus danda (0964-0965) and digits (0966-096F); ZWNJ/ZWJ stay inside words.
RAW_WORD = re.compile(r"[ऀ-ॣ॰-ॿ‌‍]+")
WORD = re.compile(r"^[ऄ-हॲ-ॿ][ऀ-ॣॱ-ॿ]*$")  # starts with a letter; no abbreviation sign ॰


def count_shard(name: str) -> str:
    done = WORK / f"counts_{name[14:18]}.tsv"
    if done.exists():
        return f"{name}: cached"
    path = WORK / name
    urllib.request.urlretrieve(BASE + name, path)
    counts: collections.Counter[str] = collections.Counter()
    pf = pq.ParquetFile(path)
    for batch in pf.iter_batches(batch_size=2000, columns=["text"]):
        for text in batch.column(0).to_pylist():
            if text:
                counts.update(RAW_WORD.findall(text))
    tmp = done.with_suffix(".part")
    with open(tmp, "w", encoding="utf-8") as f:
        for w, c in counts.items():
            f.write(f"{w}\t{c}\n")
    tmp.rename(done)
    path.unlink()
    return f"{name}: {len(counts)} raw types"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--min-count", type=int, default=2)
    args = ap.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(args.workers) as pool:
        for i, msg in enumerate(pool.map(count_shard, SHARDS), 1):
            print(f"[{i}/{len(SHARDS)}] {msg}", flush=True)

    total: collections.Counter[str] = collections.Counter()
    for tsv in sorted(WORK.glob("counts_*.tsv")):
        with open(tsv, encoding="utf-8") as f:
            for line in f:
                w, c = line.rstrip("\n").split("\t")
                total[normalize(w)] += int(c)
    kept = sorted(((w, c) for w, c in total.items() if c >= args.min_count and WORD.match(w)),
                  key=lambda wc: (-wc[1], wc[0]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("word\tcount\n")
        for w, c in kept:
            f.write(f"{w}\t{c}\n")
    print(f"{len(total)} types, {len(kept)} with count >= {args.min_count} -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
