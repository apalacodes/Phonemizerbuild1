"""Read MFA forced-alignment output (bench/out/mfa) for the app's Audio check tab.

suspects.tsv (bench/mfa_report.py) lists words whose recorded tokens picked a rival schwa form
over ours. This module loads it and cuts a word's clip out of the recording via its TextGrid.
"""

import functools
import io
import re
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MFA_DIR = ROOT / "bench" / "out" / "mfa"
SUSPECTS_TSV = MFA_DIR / "suspects.tsv"
SILENCE = {"", "sil", "sp", "spn", "<eps>"}


def read_textgrid(path: Path) -> dict[str, list[tuple[float, float, str]]]:
    """Long-format TextGrid -> {tier name: [(start, end, label)]}."""
    tiers: dict[str, list[tuple[float, float, str]]] = {}
    tier = None
    xmin = 0.0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if m := re.match(r'name = "(.*)"', line):
            tier = tiers.setdefault(m.group(1), [])
        elif m := re.match(r"xmin = ([\d.]+)", line):
            xmin = float(m.group(1))
        elif m := re.match(r"xmax = ([\d.]+)", line):
            xmax = float(m.group(1))
        elif (m := re.match(r'text = "(.*)"', line)) and tier is not None:
            tier.append((xmin, xmax, m.group(1)))
    return tiers


def load_suspects() -> list[dict]:
    """Rows of suspects.tsv, most rival tokens first; [] if MFA has not been run."""
    if not SUSPECTS_TSV.exists():
        return []
    lines = SUSPECTS_TSV.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    rows = [dict(zip(header, line.split("\t"))) for line in lines[1:]]
    for r in rows:
        r["tokens"], r["ours"], r["rival"] = int(r["tokens"]), int(r["ours"]), int(r["rival"])
        r["utts"] = r["utts"].split()
    rows.sort(key=lambda r: (-r["rival"], -r["tokens"], r["word"]))
    return rows


@functools.cache
def utterance_index() -> dict[str, list[str]]:
    """word -> utterance ids whose transcript contains it (bench/out/mfa/corpus/*/*.lab)."""
    index: dict[str, list[str]] = {}
    for lab in sorted((MFA_DIR / "corpus").rglob("*.lab")):
        for w in dict.fromkeys(lab.read_text(encoding="utf-8").split()):
            index.setdefault(w, []).append(lab.stem)
    return index


def word_clips(word: str, utt: str, pad: float = 0.15) -> list[dict]:
    """Every occurrence of `word` in utterance `utt`: {start, end, phones, wav (bytes), context_wav}."""
    tgs = list((MFA_DIR / "aligned").rglob(f"{utt}.TextGrid"))
    wavs = list((MFA_DIR / "corpus").rglob(f"{utt}.wav"))
    if not tgs or not wavs:
        return []
    tiers = read_textgrid(tgs[0])
    phones = [p for p in tiers.get("phones", []) if p[2] not in SILENCE]
    words = tiers.get("words", [])
    out = []
    for i, (start, end, label) in enumerate(words):
        if label != word:
            continue
        # Context: the words either side, so the word is heard as it was spoken.
        ctx_start = next((s for s, _, lab in reversed(words[:i]) if lab not in SILENCE), start)
        ctx_end = next((e for _, e, lab in words[i + 1:] if lab not in SILENCE), end)
        out.append({
            "start": start, "end": end,
            "phones": [(p[2], round(p[1] - p[0], 3)) for p in phones if p[0] >= start - 1e-4 and p[1] <= end + 1e-4],
            "wav": cut_wav(wavs[0], start - pad, end + pad),
            "context_wav": cut_wav(wavs[0], ctx_start - pad, ctx_end + pad),
        })
    return out


def cut_wav(path: Path, start: float, end: float) -> bytes:
    """A [start, end] slice of a PCM wav, as wav bytes."""
    with wave.open(str(path)) as w:
        rate = w.getframerate()
        a = max(0, int(start * rate))
        b = min(w.getnframes(), int(end * rate))
        w.setpos(a)
        frames = w.readframes(b - a)
        params = w.getparams()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as o:
        o.setparams(params)
        o.writeframes(frames)
    return buf.getvalue()
