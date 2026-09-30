"""Nepali G2P public API.

Pipeline: normalize -> exceptions (S0) -> suffix split -> segment stem
-> schwa keep mask (S1-S11) -> map.
Suffixes are postposition-like and keep their inherent vowels (बाट -> b a ʈ ʌ).
Post-rules (POST-1..3) are applied inside the mapping step.
"""

from typing import NamedTuple

from . import newwords, schwa
from .mapping import word_phonemes
from .normalize import normalize, tokenize
from .segment import Akshara, segment
from .suffix import split_suffixes

__all__ = ["analyze_word", "phonemize", "phonemize_word"]


class WordAnalysis(NamedTuple):
    aksharas: list[Akshara]  # stem aksharas
    suffixes: list[str]
    decisions: list[tuple[bool, str | None]]  # (keep, rule ID) per stem akshara
    phonemes: list[str]
    stem_len: int  # phonemes[:stem_len] belong to the stem


def analyze_word(word: str) -> WordAnalysis:
    word = normalize(word)
    lexical = schwa.lookup_exception(word)
    if lexical is not None:
        aks = segment(word)
        return WordAnalysis(aks, [], [(True, "S0")] * len(aks), lexical, len(lexical))
    stem, suffixes = split_suffixes(word)
    aks = segment(stem)
    lexical = schwa.lookup_exception(stem)
    if lexical is not None:
        decisions, out = [(True, "S0")] * len(aks), list(lexical)
    else:
        decisions = schwa.decide_with_rules(aks, word=word)
        out = word_phonemes(aks, [keep for keep, _ in decisions])
    stem_len = len(out)
    for suffix in suffixes:
        out += word_phonemes(segment(suffix))
    return WordAnalysis(aks, suffixes, decisions, out, stem_len)


def phonemize_word(word: str) -> list[str]:
    a = analyze_word(word)
    if (new_words := newwords.active()) is not None:  # opt-in review queue (g2p/newwords.py)
        new_words.see(normalize(word), a)
    return a.phonemes


def phonemize(text: str) -> str:
    """Space-separated phonemes, words separated by ' | '."""
    return " | ".join(" ".join(phonemize_word(w)) for w in tokenize(text))
