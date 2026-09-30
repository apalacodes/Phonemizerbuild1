"""Post-rules applied while mapping aksharas to phonemes (CLAUDE.md POST-1..3).

POST-1: ं before a stop -> homorganic nasal; elsewhere -> nasalize the preceding vowel.
POST-2: व -> b word-initially and after ं, w elsewhere (मानव m a n ʌ w, अदुवा ʌ d̪ u w a).
POST-3: ँ -> combining tilde on the preceding vowel.
"""

import logging

from .segment import Akshara

log = logging.getLogger(__name__)

NASAL = "̃"  # combining tilde
VOWEL_PHONEMES = {"i", "e", "a", "ʌ", "o", "u", "ʌi", "ʌu"}

# Stop series -> homorganic nasal (our inventory has one n for palatal/retroflex/dental).
HOMORGANIC_NASAL = {
    **dict.fromkeys("कखगघ", "ŋ"),
    **dict.fromkeys("चछजझ", "n"),
    **dict.fromkeys("टठडढ", "n"),
    **dict.fromkeys("तथदध", "n"),
    **dict.fromkeys("पफबभव", "m"),  # व is b (POST-2), so संवाद -> s ʌ m b a d̪
}


def anusvara_nasal(next_ak: Akshara | None) -> str | None:
    """POST-1: the homorganic nasal for ं when the next akshara starts with a stop, else None."""
    if next_ak is None or not next_ak.consonants:
        return None
    return HOMORGANIC_NASAL.get(next_ak.consonants[0])


def anusvara_cluster(aks: list[Akshara], i: int) -> bool:
    """True if akshara i follows ं + stop, i.e. ं spells a nasal conjunct (अंक = अङ्क)."""
    return i > 0 and "ं" in aks[i - 1].signs and anusvara_nasal(aks[i]) is not None


def nasalize_last_vowel(phonemes: list[str]) -> None:
    """POST-3 (and POST-1 'elsewhere'): add a combining tilde to the last vowel, in place."""
    for j in range(len(phonemes) - 1, -1, -1):
        if phonemes[j] in VOWEL_PHONEMES:
            phonemes[j] += NASAL
            return
    log.warning("postrules: nasal sign with no vowel to nasalize in %r", phonemes)


def apply_signs(ak: Akshara, next_ak: Akshara | None, phonemes: list[str], visarga: list[str]) -> None:
    """Apply ँ ं ः of `ak` to its phonemes, in place. `visarga` is ः's mapping."""
    for sign in ak.signs:
        if sign == "ँ":
            nasalize_last_vowel(phonemes)
        elif sign == "ं":
            nasal = anusvara_nasal(next_ak)
            if nasal is None:
                nasalize_last_vowel(phonemes)
            else:
                phonemes.append(nasal)
        elif sign == "ः":
            phonemes += visarga


def va_is_w(aks: list[Akshara], i: int, j: int) -> bool:
    """POST-2: consonant j of akshara i, if it is व, is w -- unless it is the first sound of the
    word or follows ं (वर्षा b ʌ r s a, संवाद s ʌ m b a d̪)."""
    if aks[i].consonants[j] != "व":
        return False
    if i == 0 and j == 0:
        return False
    return not (j == 0 and i > 0 and "ं" in aks[i - 1].signs)
