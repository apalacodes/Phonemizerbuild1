"""Prepare a Montreal Forced Aligner run: the owner's recordings (metadata.csv + wavs) and, when
downloaded, OpenSLR SLR43 (Google's multi-speaker Nepali TTS data, datasets/openslr43/).

Corpus: one folder per speaker, a symlink to each wav plus a .lab transcript (normalized words).
Dictionary: every transcript word with our pronunciation first and rival schwa pronunciations
after it (g2p/variants.py); MFA picks the one that fits the audio. Words whose pronunciation was
accepted from an earlier alignment (decision 'audio') get the pure-rule form as their rival, so
every run re-tests them; words decided by ear get no rivals.

Output (bench/out/mfa/):
  corpus/<speaker>/<utt>.wav|.lab
  nepali.dict          word  phonemes            (MFA format; ours + rivals)
  variants.tsv         word  kind  phonemes  count  in_lexicon

uv run bench/mfa_prepare.py [--metadata metadata.csv] [--wavs /root/work/TTS/datawork] [--slr43 DIR | --no-slr43]
"""

import argparse
import collections
import csv
import logging
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from g2p.normalize import tokenize  # noqa: E402
from g2p.reference import load_decisions  # noqa: E402
from g2p.variants import schwa_variants  # noqa: E402

OUT = ROOT / "bench" / "out" / "mfa"
WORD = re.compile(r"^[ऀ-ॣॱ-ॿ]+$")
# Leftovers of legacy-font (Preeti) conversion: ¥ was eyelash ra.
FONT_FIXES = str.maketrans({"¥": "र्"})

logging.getLogger("g2p.suffix").setLevel(logging.WARNING)


def transcript_words(text: str) -> list[str]:
    return [w for w in tokenize(text.translate(FONT_FIXES)) if WORD.match(w)]


def owner_utterances(metadata: Path, wav_root: Path):
    """(speaker, wav, text) from the owner's metadata.csv (wav path, text, speaker)."""
    with open(metadata, encoding="utf-8") as f:
        for wav_rel, text, speaker in csv.reader(f):
            yield speaker, wav_root / wav_rel, text


def slr43_utterances(root: Path):
    """(speaker, wav, text) from OpenSLR SLR43: line_index.tsv (file id, text); the file id starts
    with the speaker id (nep_0258_0119737288 -> nep_0258)."""
    wavs = {p.stem: p for p in root.rglob("*.wav")}
    for index in root.rglob("line_index.tsv"):
        for line in index.read_text(encoding="utf-8").splitlines():
            if "\t" not in line:
                continue
            utt, text = line.split("\t", 1)
            utt = utt.strip()
            yield "_".join(utt.split("_")[:2]), wavs.get(utt, root / f"{utt}.wav"), text


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--metadata", type=Path, default=ROOT / "metadata.csv")
    ap.add_argument("--wavs", type=Path, default=Path("/root/work/TTS/datawork"),
                    help="folder that the metadata's wav paths are relative to")
    ap.add_argument("--slr43", type=Path, default=ROOT / "datasets" / "openslr43")
    ap.add_argument("--no-slr43", action="store_true", help="only the owner's recordings")
    args = ap.parse_args()

    sources = [("owner", owner_utterances(args.metadata, args.wavs))]
    if not args.no_slr43 and args.slr43.exists():
        sources.append(("slr43", slr43_utterances(args.slr43)))

    corpus = OUT / "corpus"
    if corpus.exists():
        shutil.rmtree(corpus)
    counts: collections.Counter[str] = collections.Counter()
    missing = collections.Counter()
    per_source = collections.Counter()
    for source, utterances in sources:
        for speaker, wav, text in utterances:
            if not wav.exists():
                missing[source] += 1
                continue
            words = transcript_words(text)
            if not words:
                continue
            counts.update(words)
            per_source[source] += 1
            d = corpus / speaker
            d.mkdir(parents=True, exist_ok=True)
            (d / wav.name).symlink_to(wav.resolve())
            (d / wav.name).with_suffix(".lab").write_text(" ".join(words) + "\n", encoding="utf-8")

    lexicon = set()
    with open(ROOT / "data" / "lexicon.tsv", encoding="utf-8") as f:
        next(f)
        lexicon = {line.split("\t", 1)[0] for line in f}

    retest = frozenset(w for w, (d, _) in load_decisions().items() if d == "audio")
    kinds: collections.Counter[str] = collections.Counter()
    with open(OUT / "nepali.dict", "w", encoding="utf-8") as fd, \
         open(OUT / "variants.tsv", "w", encoding="utf-8") as fv:
        fv.write("word\tkind\tphonemes\tcount\tin_lexicon\n")
        for w in sorted(counts):
            for kind, ph in schwa_variants(w, retest=retest):
                kinds[kind] += 1
                fd.write(f"{w}\t{' '.join(ph)}\n")
                fv.write(f"{w}\t{kind}\t{' '.join(ph)}\t{counts[w]}\t{'yes' if w in lexicon else 'no'}\n")

    utts = sum(1 for _ in corpus.rglob("*.lab"))
    speakers = sum(1 for d in corpus.iterdir() if d.is_dir())
    print(f"{utts} utterances from {speakers} speakers {dict(per_source)} "
          f"(wavs missing: {dict(missing) or 0}), {len(counts)} word types, "
          f"{sum(counts.values())} tokens; {sum(w in lexicon for w in counts)} types in lexicon.tsv")
    print(f"dictionary entries: {dict(kinds)} -> {(OUT / 'nepali.dict').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
