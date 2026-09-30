"""Export apalas_phonemizer: just the phonemizer, its voice, one app (compare with espeak-ng, benchmark
against ground truth), the ground truth, the reference lexicon and the self-test.

  uv run release/export_apalas.py [--out ../apalas_phonemizer] [--min-count 50]

Shares its steps with release/export.py (the deephoneme repo). The folder is rebuilt each time; .git is kept.
"""

import argparse
import shutil
from pathlib import Path

from export import (  # release/ is on sys.path when this file runs
    DATA, HERE, ROOT, clean_out, export_benchmark, export_speech, fill, readme_stats, version, write_lexicon,
    write_package,
)

APALAS = HERE / "apalas"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT.parent / "apalas_phonemizer")
    ap.add_argument("--min-count", type=int, default=50, help="minimum Sangraha count for lexicon.dict")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    out = clean_out(args.out)

    pkg = out / "deephoneme"
    write_package(pkg, DATA)
    export_speech(pkg / "speech")
    shutil.copy(APALAS / "app.py", out / "app.py")
    export_benchmark(out)
    (out / "benchmark.tsv").rename(out / "ground_truth.tsv")
    shutil.copy(ROOT / "data" / "ground_truth_sentences.tsv", out / "ground_truth_sentences.tsv")
    test = (HERE / "test.py").read_text(encoding="utf-8")
    for old, new in [('"benchmark.tsv"', '"ground_truth.tsv"'), ("benchmark.tsv", "ground_truth.tsv"),
                     ('_check("benchmark', '_check("ground truth'), ("benchmark: {", "ground truth: {")]:
        test = test.replace(old, new)
    (out / "test.py").write_text(test, encoding="utf-8")
    project = (HERE / "pyproject.template.toml").read_text(encoding="utf-8").replace("{version}", version())
    project = project.replace('name = "deephoneme"', 'name = "apalas-phonemizer"', 1)
    (out / "pyproject.toml").write_text(project, encoding="utf-8")
    (out / ".gitignore").write_text("__pycache__/\n.venv/\ndist/\nmodels/\nuv.lock\nnew_words.tsv\n", encoding="utf-8")

    n, by_src = write_lexicon(out, args.min_count, args.workers)
    stats = readme_stats(n, by_src)
    stats["sentences"] = str(sum(1 for line in (out / "ground_truth_sentences.tsv").read_text(
        encoding="utf-8").splitlines()[1:] if line.strip()))
    (out / "README.md").write_text(fill(APALAS / "README.md", stats), encoding="utf-8")
    print(f"exported {out}: lexicon {n:,} words, {stats['exceptions']} exceptions, "
          f"ground truth {stats['verified']} words")


if __name__ == "__main__":
    main()
