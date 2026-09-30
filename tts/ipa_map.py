"""Our phoneme inventory -> espeak-style IPA symbols (data/ipa_map.tsv), as spoken by the voice."""

import functools
import logging
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IPA_MAP_TSV = ROOT / "data" / "ipa_map.tsv"
STRESS = "ˈ"
VOWEL_BASES = {"i", "e", "a", "ʌ", "o", "u", "ʌi", "ʌu"}

log = logging.getLogger(__name__)


def _nfd(s: str) -> str:
    return unicodedata.normalize("NFD", s)


@functools.cache
def load_map() -> dict[str, str]:
    """our phoneme -> IPA symbol string (both NFD)."""
    table = {}
    with open(IPA_MAP_TSV, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            ours, ipa = line.split("\t")
            table[_nfd(ours)] = _nfd(ipa)
    return table


def is_vowel(phoneme: str) -> bool:
    return _nfd(phoneme).replace("̃", "") in VOWEL_BASES


SCHWA_STYLES = {"ə": "light", "ˌə": "medium", "ʌ": "full"}


def word_to_ipa(
    phonemes: list[str], stress: bool = True, final_schwa: int | None = None, schwa_style: str = "ə",
) -> str:
    """Map one word's phonemes to an IPA symbol string (used by the "ours" mode).

    With stress=True the first vowel gets ˈ (and its stressed form, e.g. ʌ instead of ə),
    as espeak marks one stress per word.
    `final_schwa` is the index of a kept stem-final schwa (वर्ष, वर्षको); unless it carries the
    main stress it is voiced as `schwa_style`: ə (light), ˌə (medium) or ʌ (full).
    """
    table = load_map()
    out, stressed = [], not stress
    for k, p in enumerate(phonemes):
        p = _nfd(p)
        if not stressed and is_vowel(p):
            stressed = True
            out.append(STRESS + table.get(STRESS + p, table.get(p, p)))
            continue
        if k == final_schwa and p == "ʌ":
            out.append(schwa_style)
            continue
        if p not in table:
            log.warning("ipa map: no entry for %r, passing through", p)
        out.append(table.get(p, p))
    return "".join(out)
