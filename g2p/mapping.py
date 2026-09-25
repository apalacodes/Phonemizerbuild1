"""Grapheme -> phoneme mapping driven by data/phonemes.tsv.

Phase 1 output keeps every inherent vowel; schwa.py supplies a keep mask later.
"""

import functools
import logging
from pathlib import Path

from .normalize import normalize
from .segment import Akshara, segment

log = logging.getLogger(__name__)

PHONEMES_TSV = Path(__file__).resolve().parent.parent / "data" / "phonemes.tsv"
SCHWA = "ʌ"
NASAL = "̃"  # combining tilde
VOWEL_PHONEMES = {"i", "e", "a", "ʌ", "o", "u", "ʌi", "ʌu"}


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


def _consonant_phonemes(consonants: tuple[str, ...]) -> list[str]:
    table = load_table()
    out, i = [], 0
    while i < len(consonants):
        pair = "्".join(consonants[i:i + 2]) if i + 1 < len(consonants) else None
        if pair in table:  # ज्ञ, क्ष
            out += table[pair]
            i += 2
            continue
        if consonants[i] in table:
            out += table[consonants[i]]
        else:
            log.warning("mapping: no phoneme for %r", consonants[i])
        i += 1
    return out


def _nasalize_last_vowel(phonemes: list[str]) -> None:
    for j in range(len(phonemes) - 1, -1, -1):
        if phonemes[j] in VOWEL_PHONEMES:
            phonemes[j] += NASAL
            return
    log.warning("mapping: nasal sign with no vowel to nasalize in %r", phonemes)


def akshara_phonemes(ak: Akshara, keep_schwa: bool = True) -> list[str]:
    """Phonemes for one akshara. The inherent vowel is emitted only if keep_schwa."""
    table = load_table()
    out = _consonant_phonemes(ak.consonants)
    if ak.vowel is not None:
        out += table[ak.vowel]
    elif ak.inherent and keep_schwa:
        out.append(SCHWA)
    for sign in ak.signs:
        if sign == "ँ":  # POST-3
            _nasalize_last_vowel(out)
        elif sign == "ं":  # POST-1 "elsewhere" case; homorganic nasal comes in phase 4
            _nasalize_last_vowel(out)
        else:
            out += table[sign]
    return out


def word_phonemes(aksharas: list[Akshara], keep: list[bool] | None = None) -> list[str]:
    """Phonemes for a segmented word. keep[i] decides akshara i's inherent vowel (None = keep all)."""
    if keep is None:
        keep = [True] * len(aksharas)
    out: list[str] = []
    for ak, k in zip(aksharas, keep, strict=True):
        out += akshara_phonemes(ak, keep_schwa=k)
    return out


def raw_phonemes(word: str) -> list[str]:
    """normalize -> segment -> map, with every inherent vowel kept."""
    return word_phonemes(segment(normalize(word)))
