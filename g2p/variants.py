"""Our pronunciation of a word plus rival schwa pronunciations, for forced alignment.

The rivals are NOT corrections: they are deliberately different forms put next to ours in the
aligner's dictionary. The aligner picks whichever fits the audio; when it picks a rival, the word
goes to the owner's ear for review. Only schwa decisions change:
- rival_final: the stem-final schwa decided by S3-S11 flipped (kept <-> deleted);
- rival_medial: a schwa kept by S3 in a V C ʌ C V context deleted (syncope), one position at a time;
- rival_rules: for a word whose pronunciation came from an exception accepted from audio (decision
  'audio'), the pure-rule pronunciation, so a new alignment run can confirm or overturn it.
Exceptions decided by ear (S0) and schwas forced by S1/S2 get no variants.
"""

from . import analyze_word, schwa
from .mapping import word_phonemes
from .normalize import normalize
from .segment import segment
from .suffix import split_suffixes

FLIPPABLE_FINAL = {"S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10", "S11"}


def _simple_cv(ak) -> bool:
    return len(ak.consonants) == 1 and ak.vowel is not None


def rule_phonemes(word: str) -> list[str]:
    """The pronunciation the rules alone give (S1-S11 and post-rules), ignoring exceptions.tsv."""
    word = normalize(word)
    stem, suffixes = split_suffixes(word)
    aks = segment(stem)
    keep = [k for k, _ in schwa.decide_with_rules(aks, word=word)]
    return word_phonemes(aks, keep) + [p for s in suffixes for p in word_phonemes(segment(s))]


def schwa_variants(word: str, max_variants: int = 4, retest: frozenset[str] = frozenset()) -> list[tuple[str, list[str]]]:
    """[(kind, phonemes)]: our pronunciation first (kind 'ours'), then 'rival_final' / 'rival_medial'.

    `retest`: words (or stems) whose exception was accepted from audio; such a word gets the
    pure-rule pronunciation as its rival ('rival_rules') instead of no rival at all.
    """
    a = analyze_word(word)
    out = [("ours", a.phonemes)]
    if not a.decisions or a.decisions[0][1] == "S0":
        w = normalize(word)
        if w in retest or split_suffixes(w)[0] in retest:
            rules = rule_phonemes(w)
            if rules != a.phonemes:
                out.append(("rival_rules", rules))
        return out
    keep = [k for k, _ in a.decisions]
    suffix = [p for s in a.suffixes for p in word_phonemes(segment(s))]
    aks = a.aksharas

    def build(kind: str, flip: int) -> None:
        k = list(keep)
        k[flip] = not k[flip]
        ph = word_phonemes(aks, k) + suffix
        if all(ph != p for _, p in out):
            out.append((kind, ph))

    last = len(aks) - 1
    if aks[last].inherent and a.decisions[last][1] in FLIPPABLE_FINAL and len(aks) > 1:
        build("rival_final", last)
    for i in range(1, last):
        if (a.decisions[i] == (True, "S3") and len(aks[i].consonants) == 1
                and (aks[i - 1].vowel is not None or aks[i - 1].inherent) and _simple_cv(aks[i + 1])):
            build("rival_medial", i)
    return out[:max_variants]
