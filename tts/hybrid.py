"""Hybrid phonemizer: espeak-ng's prosody (stress, length) + our G2P's segments.

Per word, espeak's segments are aligned to our phonemes (Levenshtein on a shared
canonical inventory). Then:
  match      -> keep espeak's segment, with its stress and length marks (vowels);
                consonants use our label when espeak's differs (w -> b, ʃ -> s, r -> ɾ)
  substitute -> our phoneme, carrying espeak's stress mark
  ours only  -> our phoneme (a schwa espeak deleted: रहन, दुख), unstressed schwa = light ə
  espeak only-> dropped (a schwa espeak kept wrongly: रिस्क); its stress moves on
Diphthongs (ऐ औ) always use ours instead of espeak's ɛː/ɔː.
Pairs in data/hybrid_keep_espeak.tsv override all of this in espeak's favour (क्ष: ʂ).
"""

import functools
import subprocess
import unicodedata

from tts.ipa_map import ROOT, STRESS, is_vowel, load_map

KEEP_ESPEAK_TSV = ROOT / "data" / "hybrid_keep_espeak.tsv"

SECONDARY = "ˌ"
STRESS_MARKS = {STRESS, SECONDARY}
MODIFIERS = {"ː", "ʰ", "̃", "̪", "ʲ", "̩", "̯", "ˑ", "ʷ"}
# Vowels whose espeak label (incl. length, e.g. ɪː uː) is kept on a match.
ESPEAK_VOWELS = {"i", "e", "a", "ʌ", "o", "u"}

# espeak-ng -v ne label -> our inventory (for alignment only)
ESPEAK_TO_OURS = {
    "ɡ": "g", "ɡʰ": "gʱ", "c": "ts", "cʰ": "tsʰ", "ɟ": "dz", "ɟʰ": "dzʱ",
    "t": "t̪", "tʰ": "t̪ʰ", "d": "d̪", "dʰ": "d̪ʱ", "bʰ": "bʱ", "ɖʰ": "ɖʱ",
    "ɾ": "r", "h": "ɦ", "ʃ": "s", "ʂ": "s", "ɳ": "n", "ɲ": "n", "w": "b", "ʋ": "b",
    "ə": "ʌ", "ɪ": "i", "ʊ": "u", "ɛ": "ʌi", "ɔ": "ʌu",
}


def _nfd(s: str) -> str:
    return unicodedata.normalize("NFD", s)


def espeak_segments(ipa: str) -> list[tuple[str, str]]:
    """Split espeak IPA into (stress marks, segment) pairs; modifiers stay with their base."""
    ipa = _nfd(ipa).replace("‍", "").replace("_", "")
    segs: list[tuple[str, str]] = []
    pending = ""
    for ch in ipa:
        if ch in STRESS_MARKS:
            pending += ch
        elif ch in MODIFIERS and segs:
            segs[-1] = (segs[-1][0], segs[-1][1] + ch)
        elif not ch.isspace():
            segs.append((pending, ch))
            pending = ""
    return segs


def canonical(segment: str) -> str:
    """espeak segment -> our phoneme (length, palatalization dropped; nasalization kept)."""
    nasal = "̃" in segment
    base = segment.replace("̃", "").replace("ʲ", "").replace("ː", "")
    base = ESPEAK_TO_OURS.get(base, base)
    return base + "̃" if nasal else base


def _cost(a: str, b: str) -> float:
    if a == b:
        return 0
    return 1 if is_vowel(a) == is_vowel(b) else 2


def align(espeak: list[str], ours: list[str]) -> list[tuple[int | None, int | None]]:
    """Levenshtein alignment: list of (espeak index or None, ours index or None)."""
    n, m = len(espeak), len(ours)
    d = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        d[i][0] = i
    for j in range(1, m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + _cost(espeak[i - 1], ours[j - 1]))
    ops = []
    i, j = n, m
    while i or j:
        if i and j and d[i][j] == d[i - 1][j - 1] + _cost(espeak[i - 1], ours[j - 1]):
            ops.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif j and d[i][j] == d[i][j - 1] + 1:
            ops.append((None, j - 1))
            j -= 1
        else:
            ops.append((i - 1, None))
            i -= 1
    return ops[::-1]


@functools.cache
def load_keep_espeak() -> frozenset[tuple[str, str]]:
    """(espeak segment, our phoneme) pairs where espeak's segment is kept."""
    pairs = set()
    with open(KEEP_ESPEAK_TSV, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.strip() and not line.startswith("#"):
                espeak, ours = line.split("\t")
                pairs.add((_nfd(espeak), _nfd(ours)))
    return frozenset(pairs)


def _ours_symbol(phoneme: str, stress: str) -> str:
    table = load_map()
    if STRESS in stress:
        return stress + table.get(STRESS + phoneme, table.get(phoneme, phoneme))
    return stress + table.get(phoneme, phoneme)


def fix_word(espeak_ipa: str, ours: list[str], final_schwa: int | None = None, schwa_style: str = "ə") -> str:
    """espeak's IPA for one word, corrected to our phonemes (see module docstring).

    `final_schwa` is the index (in `ours`) of a kept stem-final schwa. With schwa_style ˌə or ʌ
    it is voiced that way unless it carries the main stress; "ə" leaves the output unchanged.
    """
    ours = [_nfd(p) for p in ours]
    if not ours:
        return _nfd(espeak_ipa).replace("‍", "")
    segs = espeak_segments(espeak_ipa)
    canon = [canonical(s) for _, s in segs]
    out, pending = [], ""
    for ei, oi in align(canon, ours):
        stress = segs[ei][0] if ei is not None else ""
        if oi is None:  # espeak-only segment: drop, keep its stress for the next vowel
            pending = pending or stress
            continue
        p = ours[oi]
        if is_vowel(p) and not stress and pending:
            stress, pending = pending, ""
        if oi == final_schwa and p == "ʌ" and schwa_style != "ə" and STRESS not in stress:
            out.append(schwa_style)
        elif ei is not None and (segs[ei][1], p) in load_keep_espeak():
            out.append(stress + segs[ei][1])
        elif ei is not None and canon[ei] == p:
            core = segs[ei][1].replace("ʲ", "")
            if is_vowel(p):
                keep_espeak = p.replace("̃", "") in ESPEAK_VOWELS
            else:
                keep_espeak = core == load_map().get(p, p)
            out.append(stress + core if keep_espeak else _ours_symbol(p, stress))
        else:
            out.append(_ours_symbol(p, stress))
    return "".join(out)


@functools.cache
def espeak_ipa(text: str) -> str:
    return subprocess.run(
        ["espeak-ng", "-v", "ne", "-q", "--ipa=3", text],
        capture_output=True, text=True, check=True,
    ).stdout


def espeak_words(words: list[str]) -> list[str]:
    """espeak IPA per word. One call per clause keeps espeak's clause context
    (unstressed function words); falls back to per-word calls if the word count differs."""
    got = espeak_ipa(" ".join(words)).split()
    if len(got) == len(words):
        return got
    return ["".join(espeak_ipa(w).split()) for w in words]
