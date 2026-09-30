"""Export the clean, standalone deephoneme repo: the phonemizer, its data, one lexicon, test.py, README.

  uv run release/export.py [--out ../deephoneme] [--min-count 50]

Lexicon words: Wiktionary (data/lexicon.tsv), the speech corpus (metadata.csv), the benchmark,
every exception and owner decision, the rule samples, and Sangraha words seen >= --min-count times
(bench/ref/sangraha_words.tsv). Pronunciations are computed fresh by the current rules.
The output folder is rebuilt from scratch each time; only its .git is kept.
"""

import argparse
import ast
import csv
import datetime
import logging
import re
import shutil
import sys
import tomllib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from g2p import phonemize_word  # noqa: E402
from g2p.normalize import tokenize  # noqa: E402
from g2p.schwa import load_exceptions  # noqa: E402

MODULES = ["__init__", "__main__", "normalize", "segment", "mapping", "suffix", "schwa", "postrules", "compare", "newwords"]
DATA = ["phonemes.tsv", "exceptions.tsv", "pronouns.txt", "adverbs.txt", "postpositions.txt",
        "verb_endings.txt", "suffixes.txt", "loanwords.txt", "ipa_map.tsv", "hybrid_keep_espeak.tsv"]
SPEECH = ["__init__", "ipa_map", "hybrid", "synth", "kokoro_voice"]
# (file, old, new): tts/ -> deephoneme/speech/. Each must match exactly once, so drift in tts/ fails loudly.
SPEECH_EDITS = [
    ("synth", "--g2p wiktionary  Wiktionary's IPA with espeak's stress/length; ours where it lacks the word (*)\n", ""),
    ("synth", "uv run tts/synth.py", "uv run python -m deephoneme.speech.synth"),
    ("synth", 'if __package__ in (None, ""):  # run as a script: make the repo root importable\n'
              "    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))\n\n", ""),
    ("synth", "from g2p.reference import wiktionary_phonemes\n", ""),
    ("synth", 'G2P_MODES = ("ours", "espeak", "hybrid", "wiktionary")', 'G2P_MODES = ("ours", "espeak", "hybrid")'),
    ("synth", '    if g2p == "wiktionary":\n        return _wiktionary(text, schwa_style)\n', ""),
    ("kokoro_voice", "ROOT = Path(__file__).resolve().parent.parent\n",
     "ROOT = Path(__file__).resolve().parents[2]  # the repo: models/kokoro/ (gitignored)\n"),
    ("__init__", "(ours / espeak / hybrid / wiktionary)", "(ours / espeak / hybrid)"),
    ("kokoro_voice", "Download them with: python -m tts.kokoro_voice", "Download them with: uv run --extra app python -m deephoneme.speech.kokoro_voice"),
]
WORD_LISTS = ["pronouns.txt", "adverbs.txt", "postpositions.txt", "verb_endings.txt", "loanwords.txt", "suffixes.txt"]
WORD = re.compile(r"^[ऀ-ॣॱ-ॿ]+$")
PATHS_PY = '"""The data files ship inside the package."""\n\nfrom pathlib import Path\n\n' \
           'DATA_DIR = Path(__file__).resolve().parent / "data"\n'


def _tsv_words(path: Path, skip_header: bool = True) -> list[str]:
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()[1 if skip_header else 0:]
    return [line.split("\t", 1)[0] for line in lines if line and not line.startswith("#")]


def _count(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#"))


def _pronounce(words: list[str]) -> list[str]:
    logging.disable(logging.WARNING)
    return [" ".join(phonemize_word(w)) for w in words]


def rule_samples() -> list[tuple[str, str, str]]:
    """RULE_SAMPLES from the clean repo's test.py (read, not imported: it imports the exported package)."""
    tree = ast.parse((HERE / "test.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "RULE_SAMPLES")
    return ast.literal_eval(node.value)


def collect(min_count: int) -> dict[str, set[str]]:
    sources: dict[str, set[str]] = {}

    def add(words, src):
        for w in words:
            if WORD.match(w):
                sources.setdefault(w, set()).add(src)

    add(_tsv_words(ROOT / "data" / "lexicon.tsv"), "wiktionary")
    add(_tsv_words(ROOT / "data" / "benchmark.tsv"), "benchmark (verified)")
    add(load_exceptions(), "exceptions")
    add(_tsv_words(ROOT / "data" / "review_decisions.tsv"), "owner decisions")
    add([w for w, _, _ in rule_samples()], "rule samples")
    with open(ROOT / "metadata.csv", encoding="utf-8") as f:
        add((w for _, text, _ in csv.reader(f) for w in tokenize(text.replace("¥", "र्"))), "speech corpus")
    sangraha = ROOT / "bench" / "ref" / "sangraha_words.tsv"
    if sangraha.exists():
        with open(sangraha, encoding="utf-8") as f:
            next(f)
            add((w for w, c in (line.rstrip("\n").split("\t") for line in f) if int(c) >= min_count),
                f"sangraha (seen >= {min_count}x)")
    else:
        print("warning: bench/ref/sangraha_words.tsv missing (uv run bench/sangraha_words.py); skipped")
    return sources


# check_phoneme.py (workshop) -> the clean repo's copy; same rule: each edit must match exactly once.
CHECK_EDITS = [
    ("  uv run streamlit run check_phoneme.py", "  uv run --extra app streamlit run check_phoneme.py"),
    ("our phonemizer on data/benchmark.tsv\n(same numbers as bench/evaluate.py), per basis,",
     "our phonemizer on benchmark.tsv,\nper basis,"),
    ("from g2p import analyze_word", "from deephoneme import analyze_word"),
    ("from g2p.compare import", "from deephoneme.compare import"),
    ("from g2p.normalize import", "from deephoneme.normalize import"),
    ("from tts import synth", "from deephoneme.speech import synth"),
    ("from tts.kokoro_voice import", "from deephoneme.speech.kokoro_voice import"),
    ('Path(__file__).resolve().parent / "data" / "benchmark.tsv"', 'Path(__file__).resolve().parent / "benchmark.tsv"'),
    ("`uv run python -m tts.kokoro_voice`", "`uv run --extra app python -m deephoneme.speech.kokoro_voice`"),
    ("Fix it in app.py (Review / Benchmark tab) or add it to data/exceptions.tsv.",
     "Add it to deephoneme/data/exceptions.tsv (or decide it in the workshop repo and re-export)."),
    ('st.caption(f"data/benchmark.tsv: {', 'st.caption(f"benchmark.tsv: {'),
]


def export_check_app(out: Path) -> None:
    src = (ROOT / "check_phoneme.py").read_text(encoding="utf-8")
    for old, new in CHECK_EDITS:
        if src.count(old) != 1:
            sys.exit(f"export: check_phoneme.py changed; update CHECK_EDITS for {old[:60]!r}")
        src = src.replace(old, new)
    if re.search(r"^\s*(from|import) (g2p|tts|bench)\b", src, re.M):
        sys.exit("export: check_phoneme.py still refers to g2p/tts/bench after rewriting")
    (out / "check_phoneme.py").write_text(src, encoding="utf-8")


def export_benchmark(out: Path) -> int:
    rows = [line.split("\t") for line in (ROOT / "data" / "benchmark.tsv").read_text(encoding="utf-8").splitlines()[1:]]
    with open(out / "benchmark.tsv", "w", encoding="utf-8") as f:
        f.write("word\tphonemes\tbasis\n")
        for r in rows:
            f.write(f"{r[0]}\t{r[1]}\t{r[3]}\n")
    return len(rows)


def export_speech(dest: Path) -> None:
    """Copy tts/ into deephoneme/speech/ with relative imports; the Wiktionary mode (dev repo only) is removed."""
    dest.mkdir()
    code = {m: (ROOT / "tts" / f"{m}.py").read_text(encoding="utf-8") for m in SPEECH}
    for m, old, new in SPEECH_EDITS:
        if code[m].count(old) != 1:
            sys.exit(f"export: tts/{m}.py changed; update SPEECH_EDITS for {old[:60]!r}")
        code[m] = code[m].replace(old, new)
    start = code["synth"].index("def _wiktionary(")
    code["synth"] = code["synth"][:start] + code["synth"][code["synth"].index("def hybrid_for_phonemes("):]
    for m, src in code.items():
        src = src.replace("from tts.", "from .").replace("from g2p.", "from ..").replace("from g2p import", "from .. import")
        if re.search(r"^\s*(from|import) (g2p|tts)\b", src, re.M):
            sys.exit(f"export: tts/{m}.py still refers to g2p/tts after rewriting")
        (dest / f"{m}.py").write_text(src, encoding="utf-8")


def letter_table() -> str:
    rows = [line.split("\t") for line in (ROOT / "data" / "phonemes.tsv").read_text(encoding="utf-8").splitlines()[1:]]
    cells = [f"{g} `{p}`" for g, p, _ in rows]
    width = 8
    out = ["|" + " |" * width, "|" + "---|" * width]
    for i in range(0, len(cells), width):
        chunk = cells[i:i + width] + [""] * (width - len(cells[i:i + width]))
        out.append("| " + " | ".join(chunk) + " |")
    return "\n".join(out)


KEEP = {".git", ".venv", "models"}  # history, the uv environment and the downloaded Kokoro voice survive exports


def clean_out(out: Path) -> Path:
    """Empty the export folder (keeping KEEP); refuse a folder that is not an earlier export.
    The voice is linked in from the workshop (models/kokoro) when the folder has none, so it is
    never downloaded twice."""
    out = out.resolve()
    if out.exists() and any(out.iterdir()) and not (out / "deephoneme").is_dir():
        sys.exit(f"{out} exists and is not a deephoneme export; refusing to overwrite")
    out.mkdir(parents=True, exist_ok=True)
    for p in out.iterdir():
        if p.name not in KEEP:
            shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink()
    voice = out / "models" / "kokoro"
    if not voice.exists() and (ROOT / "models" / "kokoro" / "kokoro-v1.0.onnx").exists():
        voice.parent.mkdir(exist_ok=True)
        voice.symlink_to(ROOT / "models" / "kokoro")
    return out


def write_package(pkg: Path, data: list[str]) -> None:
    """The phonemizer as package `deephoneme` (g2p/ modules with relative imports) plus its data files."""
    (pkg / "data").mkdir(parents=True)
    for m in MODULES:
        src = (ROOT / "g2p" / f"{m}.py").read_text(encoding="utf-8")
        (pkg / f"{m}.py").write_text(src.replace("python -m g2p", "python -m deephoneme"), encoding="utf-8")
    (pkg / "__main__.py").write_text((pkg / "__main__.py").read_text(encoding="utf-8").replace(
        'if __name__ == "__main__":\n    main(sys.argv[1:])', 'if __name__ == "__main__":\n    cli()'), encoding="utf-8")
    (pkg / "paths.py").write_text(PATHS_PY, encoding="utf-8")
    for d in data:
        shutil.copy(ROOT / "data" / d, pkg / "data" / d)


def version() -> str:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def write_lexicon(out: Path, min_count: int, workers: int) -> tuple[int, dict[str, int]]:
    """lexicon.dict (word<TAB>phonemes) for every collected word; returns (words written, words per source)."""
    sources = collect(min_count)
    words = sorted(sources)
    chunks = [words[i:i + 20000] for i in range(0, len(words), 20000)]
    with ProcessPoolExecutor(workers) as pool:
        phonemes = [p for c in pool.map(_pronounce, chunks) for p in c]
    n = 0
    with open(out / "lexicon.dict", "w", encoding="utf-8") as f:
        for w, ph in zip(words, phonemes):
            if ph:
                f.write(f"{w}\t{ph}\n")
                n += 1
    by_src: dict[str, int] = {}
    for s in sources.values():
        for x in s:
            by_src[x] = by_src.get(x, 0) + 1
    return n, by_src


def readme_stats(n: int, by_src: dict[str, int]) -> dict[str, str]:
    """Numbers and tables filled into a README template ({lexicon_words}, {exceptions}, ...)."""
    basis = [line.split("\t")[3] for line in (ROOT / "data" / "benchmark.tsv").read_text(encoding="utf-8").splitlines()[1:]]
    return {
        "version": version(), "lexicon_words": f"{n:,}", "exceptions": f"{_count(ROOT / 'data' / 'exceptions.tsv'):,}",
        "owner": f"{basis.count('owner'):,}", "agree": f"{basis.count('agree'):,}",
        "audio": f"{basis.count('audio'):,}", "verified": f"{len(basis):,}",
        "rule_samples": str(len(rule_samples())),
        "table_rows": str(_count(ROOT / "data" / "phonemes.tsv") - 1),
        "word_lists": ", ".join(f"{w.removesuffix('.txt')} {_count(ROOT / 'data' / w)}" for w in WORD_LISTS),
        "source_rows": "\n".join(f"| {k} | {v:,} |" for k, v in sorted(by_src.items(), key=lambda kv: -kv[1])),
        "table": letter_table(), "date": datetime.date.today().isoformat(),
    }


def fill(template: Path, stats: dict[str, str]) -> str:
    text = template.read_text(encoding="utf-8")
    for k, v in stats.items():
        text = text.replace("{" + k + "}", v)
    return text


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT.parent / "deephoneme")
    ap.add_argument("--min-count", type=int, default=50, help="minimum Sangraha count (5 -> ~3.1M words, 155 MB)")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    out = clean_out(args.out)

    pkg = out / "deephoneme"
    write_package(pkg, DATA)
    export_speech(pkg / "speech")
    shutil.copy(HERE / "app.py", out / "app.py")
    export_check_app(out)
    export_benchmark(out)
    shutil.copy(HERE / "test.py", out / "test.py")
    (out / "pyproject.toml").write_text((HERE / "pyproject.template.toml").read_text(encoding="utf-8")
                                        .replace("{version}", version()), encoding="utf-8")
    (out / ".gitignore").write_text("__pycache__/\n.venv/\ndist/\nmodels/\nuv.lock\nnew_words.tsv\n", encoding="utf-8")

    n, by_src = write_lexicon(out, args.min_count, args.workers)
    stats = readme_stats(n, by_src)
    (out / "README.md").write_text(fill(HERE / "README.md", stats), encoding="utf-8")
    size = (out / "lexicon.dict").stat().st_size / 1e6
    print(f"exported {out}: lexicon {n:,} words ({size:.0f} MB), {stats['exceptions']} exceptions")
    for k, v in sorted(by_src.items(), key=lambda kv: -kv[1]):
        print(f"  {v:>9,}  {k}")


if __name__ == "__main__":
    main()
