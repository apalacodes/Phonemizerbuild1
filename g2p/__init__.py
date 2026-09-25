"""Nepali G2P public API.

Pipeline: normalize -> exceptions (S0) -> suffix split -> segment stem
-> schwa keep mask (S1-S11) -> map.
Suffixes are postposition-like and keep their inherent vowels (बाट -> b a ʈ ʌ).
Phase 3: all schwa rules; post-rules (phase 4) not applied yet.
"""

from . import schwa
from .mapping import word_phonemes
from .normalize import normalize, tokenize
from .segment import segment
from .suffix import split_suffixes

__all__ = ["analyze_word", "phonemize", "phonemize_word"]


def analyze_word(word: str):
    """(stem aksharas, suffixes, [(keep, rule ID)] per stem akshara, phonemes)."""
    word = normalize(word)
    lexical = schwa.lookup_exception(word)
    if lexical is not None:
        aks = segment(word)
        return aks, [], [(True, "S0")] * len(aks), lexical
    stem, suffixes = split_suffixes(word)
    aks = segment(stem)
    lexical = schwa.lookup_exception(stem)
    if lexical is not None:
        decisions, out = [(True, "S0")] * len(aks), lexical
    else:
        decisions = schwa.decide_with_rules(aks, word=word)
        out = word_phonemes(aks, [keep for keep, _ in decisions])
    for suffix in suffixes:
        out += word_phonemes(segment(suffix))
    return aks, suffixes, decisions, out


def phonemize_word(word: str) -> list[str]:
    return analyze_word(word)[3]


def phonemize(text: str) -> str:
    """Space-separated phonemes, words separated by ' | '."""
    return " | ".join(" ".join(phonemize_word(w)) for w in tokenize(text))
