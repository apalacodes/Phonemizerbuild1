"""Keep/delete decision for every inherent vowel (schwa rules, CLAUDE.md).

S0 (exceptions.tsv) is a whole-word override applied by the caller via
lookup_exception(). The positional rules S1-S11 take (aksharas, i, ctx) for an
inherent-vowel akshara at index i of the stem and return True (KEEP),
False (DELETE) or None (rule does not apply). First matching rule wins.
Word-list rules match the stem (after suffix splitting) or the full word.
"""

import functools
from dataclasses import dataclass
from pathlib import Path

from .normalize import normalize
from .segment import Akshara

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
KEEP, DELETE = True, False

# Named in the S9 rule itself (CLAUDE.md): a native word that behaves like a loan.
S9_EXTRA_WORDS = frozenset({"मञ्च"})


@dataclass(frozen=True)
class Context:
    word: str  # full normalized word
    stem: str  # word with case suffixes removed


@functools.cache
def load_list(filename: str) -> frozenset[str]:
    """One word per line from data/<filename>; blank lines and # comments ignored."""
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return frozenset(normalize(s) for line in f if (s := line.strip()) and not s.startswith("#"))


@functools.cache
def load_exceptions() -> dict[str, list[str]]:
    """word -> phonemes from data/exceptions.tsv."""
    table = {}
    with open(DATA_DIR / "exceptions.tsv", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or line.startswith("#"):
                continue
            word, phonemes = line.split("\t")
            table[normalize(word)] = phonemes.split()
    return table


def lookup_exception(word: str) -> list[str] | None:
    """S0: word in exceptions.tsv -> use the lexicon entry (full override)."""
    phonemes = load_exceptions().get(word)
    return list(phonemes) if phonemes is not None else None


def _listed(ctx: Context, filename: str) -> bool:
    words = load_list(filename)
    return ctx.stem in words or ctx.word in words


def rule_s1(aks: list[Akshara], i: int, ctx: Context) -> bool | None:
    """S1: a conjunct or halanta-consonant follows, or ं / ँ is on this akshara -> KEEP."""
    if any(s in "ंँ" for s in aks[i].signs):
        return KEEP
    if i + 1 < len(aks):
        nxt = aks[i + 1]
        if nxt.is_conjunct or nxt.halanta:
            return KEEP
    return None


def rule_s2(aks: list[Akshara], i: int, ctx: Context) -> bool | None:
    """S2: first akshara of the word -> KEEP."""
    return KEEP if i == 0 else None


def rule_s3(aks: list[Akshara], i: int, ctx: Context) -> bool | None:
    """S3: not the final akshara (Nepali rarely deletes medially) -> KEEP."""
    return KEEP if i < len(aks) - 1 else None


def rule_s4(aks: list[Akshara], i: int, ctx: Context) -> bool | None:
    """S4: final letter is ङ -> DELETE."""
    return DELETE if aks[i].consonants[-1] == "ङ" else None


def rule_s5(aks: list[Akshara], i: int, ctx: Context) -> bool | None:
    """S5: word in pronouns.txt -> DELETE."""
    return DELETE if _listed(ctx, "pronouns.txt") else None


def rule_s6(aks: list[Akshara], i: int, ctx: Context) -> bool | None:
    """S6: word in adverbs.txt or postpositions.txt -> KEEP."""
    return KEEP if _listed(ctx, "adverbs.txt") or _listed(ctx, "postpositions.txt") else None


def rule_s7(aks: list[Akshara], i: int, ctx: Context) -> bool | None:
    """S7: word ends with a pattern in verb_endings.txt -> KEEP."""
    return KEEP if any(ctx.stem.endswith(p) for p in load_list("verb_endings.txt")) else None


def rule_s8(aks: list[Akshara], i: int, ctx: Context) -> bool | None:
    """S8: final letter is छ, य or ह -> KEEP."""
    return KEEP if aks[i].consonants[-1] in "छयह" else None


def rule_s9(aks: list[Akshara], i: int, ctx: Context) -> bool | None:
    """S9: final akshara is a conjunct and word in loanwords.txt (or the word is मञ्च) -> DELETE."""
    if not aks[i].is_conjunct:
        return None
    if _listed(ctx, "loanwords.txt") or ctx.stem in S9_EXTRA_WORDS or ctx.word in S9_EXTRA_WORDS:
        return DELETE
    return None


def rule_s10(aks: list[Akshara], i: int, ctx: Context) -> bool | None:
    """S10: final akshara is a conjunct -> KEEP."""
    return KEEP if aks[i].is_conjunct else None


def rule_s11(aks: list[Akshara], i: int, ctx: Context) -> bool | None:
    """S11: otherwise (incl. घ ण थ फ व श ष) -> DELETE."""
    return DELETE


RULES = [
    ("S1", rule_s1),
    ("S2", rule_s2),
    ("S3", rule_s3),
    ("S4", rule_s4),
    ("S5", rule_s5),
    ("S6", rule_s6),
    ("S7", rule_s7),
    ("S8", rule_s8),
    ("S9", rule_s9),
    ("S10", rule_s10),
    ("S11", rule_s11),
]


def decide_with_rules(aks: list[Akshara], word: str | None = None) -> list[tuple[bool, str | None]]:
    """(keep, rule ID) per stem akshara; aksharas without an inherent vowel get (True, None).

    `word` is the full word before suffix splitting (defaults to the stem).
    """
    stem = "".join(a.text for a in aks)
    ctx = Context(word=word if word is not None else stem, stem=stem)
    out = []
    for i, ak in enumerate(aks):
        if not ak.inherent:
            out.append((KEEP, None))
            continue
        for rule_id, rule in RULES:
            decision = rule(aks, i, ctx)
            if decision is not None:
                out.append((decision, rule_id))
                break
    return out


def decide(aks: list[Akshara], word: str | None = None) -> list[bool]:
    """Keep mask for mapping.word_phonemes()."""
    return [keep for keep, _ in decide_with_rules(aks, word)]
