"""Split a normalized word into aksharas.

An akshara is a consonant cluster (C, or C्C्C...) followed by a matra, a halanta,
or nothing (inherent vowel), plus any trailing signs (ँ ं ः). Independent vowels
form their own akshara. A word-final C् is its own halanta akshara: झन् -> झ | न्.
"""

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

HALANTA = "्"
CONSONANTS = set("कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह")
VOWELS = set("अआइईउऊएऐओऔऋ")
MATRAS = set("ािीुूेैोौृ")
SIGNS = set("ँंः")


@dataclass(frozen=True)
class Akshara:
    text: str
    consonants: tuple[str, ...] = ()
    vowel: str | None = None  # matra or independent vowel
    halanta: bool = False
    signs: tuple[str, ...] = ()

    @property
    def inherent(self) -> bool:
        """True if this akshara carries an inherent vowel (schwa candidate)."""
        return bool(self.consonants) and self.vowel is None and not self.halanta

    @property
    def is_conjunct(self) -> bool:
        return len(self.consonants) > 1


def segment(word: str) -> list[Akshara]:
    """Split a normalized word into aksharas. Stray or unknown characters are skipped."""
    out: list[Akshara] = []
    i, n = 0, len(word)
    while i < n:
        start, ch = i, word[i]
        consonants: list[str] = []
        vowel, halanta = None, False
        if ch in CONSONANTS:
            consonants.append(ch)
            i += 1
            while i + 1 < n and word[i] == HALANTA and word[i + 1] in CONSONANTS:
                consonants.append(word[i + 1])
                i += 2
            if i < n and word[i] in MATRAS:
                vowel = word[i]
                i += 1
            elif i < n and word[i] == HALANTA:
                halanta = True
                i += 1
        elif ch in VOWELS:
            vowel = ch
            i += 1
        else:
            log.warning("segment: skipping unexpected character %r (U+%04X) in %r", ch, ord(ch), word)
            i += 1
            continue
        signs = []
        while i < n and word[i] in SIGNS:
            signs.append(word[i])
            i += 1
        out.append(Akshara(word[start:i], tuple(consonants), vowel, halanta, tuple(signs)))
    return out


def format_aksharas(aksharas: list[Akshara]) -> str:
    return " | ".join(a.text for a in aksharas)
