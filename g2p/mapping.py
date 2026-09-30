"""Grapheme -> phoneme mapping driven by data/phonemes.tsv, with post-rules POST-1..3.

schwa.py supplies the keep mask for inherent vowels (None keeps every one).
"""

import functools
import logging

from . import postrules
from .normalize import normalize
from .paths import DATA_DIR
from .segment import Akshara, segment

log = logging.getLogger(__name__)

PHONEMES_TSV = DATA_DIR / "phonemes.tsv"
SCHWA = "ʌ"


@functools.cache
def load_table() -> dict[str, list[str]]:
    """grapheme -> list of phonemes, from data/phonemes.tsv (header row skipped)."""
    table = {}
    with open(PHONEMES_TSV, encoding="utf-8") as f:
        next(f)
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            grapheme, phonemes, _type = line.split("\t")
            table[grapheme] = phonemes.split()
    return table


def _consonant_phonemes(consonants: tuple[str, ...], w_from: int | None = None) -> list[str]:
    """Consonant cluster -> phonemes. व at cluster index >= w_from becomes w (POST-2)."""
    table = load_table()
    out, i = [], 0
    while i < len(consonants):
        pair = "\u094d".join(consonants[i:i + 2]) if i + 1 < len(consonants) else None
        if pair in table:  # ज्ञ, क्ष
            out += table[pair]
            i += 2
            continue
        if w_from is not None and i >= w_from and consonants[i] == "व":
            out.append("w")
        elif consonants[i] in table:
            out += table[consonants[i]]
        else:
            log.warning("mapping: no phoneme for %r", consonants[i])
        i += 1
    return out


def akshara_phonemes(
    ak: Akshara, keep_schwa: bool = True, next_ak: Akshara | None = None, w_from: int | None = None,
) -> list[str]:
    """Phonemes for one akshara. The inherent vowel is emitted only if keep_schwa.

    `next_ak` lets ं assimilate to a following stop (POST-1); `w_from` is for POST-2.
    """
    table = load_table()
    out = _consonant_phonemes(ak.consonants, w_from)
    if ak.vowel is not None:
        out += table[ak.vowel]
    elif ak.inherent and keep_schwa:
        out.append(SCHWA)
    postrules.apply_signs(ak, next_ak, out, table["ः"])
    return out


def word_phonemes(aksharas: list[Akshara], keep: list[bool] | None = None) -> list[str]:
    """Phonemes for a segmented word. keep[i] decides akshara i's inherent vowel (None = keep all)."""
    if keep is None:
        keep = [True] * len(aksharas)
    out: list[str] = []
    for i, (ak, k) in enumerate(zip(aksharas, keep, strict=True)):
        next_ak = aksharas[i + 1] if i + 1 < len(aksharas) else None
        w_from = None
        if "व" in ak.consonants:
            w_from = next((j for j in range(len(ak.consonants)) if postrules.va_is_w(aksharas, i, j)), None)
        out += akshara_phonemes(ak, keep_schwa=k, next_ak=next_ak, w_from=w_from)
    return out


def raw_phonemes(word: str) -> list[str]:
    """normalize -> segment -> map, with every inherent vowel kept."""
    return word_phonemes(segment(normalize(word)))
