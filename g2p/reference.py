"""Reference pronunciations: Wiktionary (via the kaikki.org dump) and espeak-ng,
converted to our phoneme inventory so they can be compared with our G2P or spoken.

Wiktionary's Nepali IPA is generated from spelling by Module:ne-pron unless an editor
passes a respelling ({{ne-IPA|...}}); those hand-edited words are the held-out test set
(see heldout_words) and must never be used to tune rules.
"""

import collections
import functools
import json
import re
import unicodedata
from pathlib import Path

from .compare import NASAL, TOKENS, VOWELS, _nfd, diff_kind, espeak_ipa, espeak_to_ours, tokenize  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
REF_DIR = ROOT / "bench" / "ref"
KAIKKI = REF_DIR / "kaikki-nepali.jsonl"
KAIKKI_URL = "https://kaikki.org/dictionary/Nepali/kaikki.org-dictionary-Nepali.jsonl"
ARGS_TSV = REF_DIR / "ne_ipa_args.tsv"

DEVANAGARI = re.compile(r"^[ऀ-ॿ]+$")



# ---------- Wiktionary IPA -> our inventory ----------

# brackets, stress, syllable/word joins, optional-segment parens, and diacritics we ignore:
# unreleased, lowered, breathy vowel, non-syllabic, laminal, retracted, extra-short, tie bar
_WIKT_DROP = "[]/ˈˌ.‿()̞̤̯̻̠̆̚͡ʲ◌"
_WIKT_SUB = [
    ("ɽ̃", "n"), ("ɽ", "ɖ"), ("ɳ", "n"), ("ɡ", "g"), ("ɾ", "r"), ("ɸ", "pʰ"),
    ("ʔ", "ɦ"), ("h", "ɦ"), ("ɭ", "l"), ("ʃ", "s"), ("æ", "e"), ("ɒ", "o"), ("ɔ", "o"),
    ("x", "kʰ"),
]


def wikt_to_ours(ipa: str) -> list[str]:
    """Wiktionary IPA -> our phoneme tokens. w and a final o are kept as they are."""
    s = _nfd(ipa).replace("̈", "")  # ä -> a (the diaeresis only ever marks ä)
    s = s.replace("t̠", "ʈ").replace("d̠", "ɖ")  # ष्ट: t̠ is our retroflex
    s = re.sub("(?<![td])̪", "", s)  # dental mark only matters on t/d (n̪ -> n)
    for ch in _WIKT_DROP:
        s = s.replace(ch, "")
    for a, b in _WIKT_SUB:
        s = s.replace(a, b)
    s = re.sub(r"(?<!d)z", "dz", s)  # "(d)z" already became dz; bare z is ज
    tokens = []
    for t in tokenize(s):
        if t == "ː":  # geminate consonant -> double it; long vowel -> ignore
            if tokens and tokens[-1].rstrip(NASAL) not in VOWELS:
                tokens.append(tokens[-1])
            continue
        tokens.append(t)
    return tokens


# ---------- data ----------

@functools.cache
def load_wiktionary() -> dict[str, tuple[str, ...]]:
    """word -> IPA variants (single Devanagari words only). {} if the dump is not downloaded."""
    if not KAIKKI.exists():
        return {}
    words: dict[str, list[str]] = collections.defaultdict(list)
    with open(KAIKKI, encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if e.get("pos") in {"character", "suffix", "prefix", "infix"}:
                continue
            word = unicodedata.normalize("NFC", e["word"])
            if not DEVANAGARI.match(word):
                continue
            for s in e.get("sounds", []):
                if "ipa" in s and s["ipa"] not in words[word]:
                    words[word].append(s["ipa"])
    return {w: tuple(v) for w, v in words.items() if v}


@functools.cache
def load_template_args() -> dict[str, str]:
    """word -> {{ne-IPA}} arguments ('' = generated from spelling), from ARGS_TSV."""
    if not ARGS_TSV.exists():
        return {}
    out = {}
    for line in ARGS_TSV.read_text(encoding="utf-8").splitlines():
        word, _, args = line.partition("\t")
        out[word] = args
    return out


def heldout_words() -> frozenset[str]:
    """Held-out test set: words whose Wiktionary IPA an editor supplied by hand."""
    return frozenset(w for w, a in load_template_args().items() if a)


def wiktionary_phonemes(word: str) -> list[str] | None:
    """Our-inventory phonemes of Wiktionary's first IPA variant for `word`, or None."""
    variants = load_wiktionary().get(unicodedata.normalize("NFC", word))
    return wikt_to_ours(variants[0]) if variants else None


def wiktionary_entries() -> list[dict]:
    """One row per Wiktionary word: split (dev/test), Wiktionary IPA, and whether our G2P
    matches any variant. For browsing/listening; never for tuning on the test split."""
    from g2p import phonemize_word  # local import: g2p/__init__ does not depend on this module

    heldout = heldout_words()
    rows = []
    for word, variants in sorted(load_wiktionary().items()):
        ours = phonemize_word(word)
        refs = [wikt_to_ours(v) for v in variants]
        rows.append({
            "word": word,
            "split": "test" if word in heldout else "dev",
            "wiktionary": " / ".join(variants),
            "wikt_phonemes": " / ".join(" ".join(r) for r in refs),
            "ours": " ".join(ours),
            "match": ours in refs,
        })
    return rows


# ---------- manual review of lexicon words that disagree with Wiktionary ----------

LEXICON_TSV = ROOT / "data" / "lexicon.tsv"
DECISIONS_TSV = ROOT / "data" / "review_decisions.tsv"
BENCHMARK_TSV = ROOT / "data" / "benchmark.tsv"


def load_benchmark_rows() -> list[dict]:
    """Rows of data/benchmark.tsv: word, phonemes, hybrid (exactly what the voice gets), basis, espeak_agrees, wiktionary."""
    if not BENCHMARK_TSV.exists():
        return []
    lines = BENCHMARK_TSV.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    return [dict(zip(header, line.split("\t"))) for line in lines[1:]]
REVIEW_PRIORITY = [
    "medial schwa", "final schwa: system deletes, ref keeps", "final schwa: system keeps, ref deletes",
    "final ʌ vs o", "nasalization", "w vs b", "other",
]


def load_lexicon() -> dict[str, dict]:
    """word -> row of data/lexicon.tsv (built by bench/build_lexicon.py)."""
    if not LEXICON_TSV.exists():
        return {}
    lines = LEXICON_TSV.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    return {r[0]: dict(zip(header, r)) for r in (line.split("\t") for line in lines[1:])}


def load_decisions() -> dict[str, tuple[str, str]]:
    """word -> (decision, phonemes) from data/review_decisions.tsv."""
    if not DECISIONS_TSV.exists():
        return {}
    out = {}
    for line in DECISIONS_TSV.read_text(encoding="utf-8").splitlines()[1:]:
        word, decision, phonemes = line.split("\t")
        out[word] = (decision, phonemes)
    return out


def review_candidates(n: int = 50) -> list[dict]:
    """Train headwords where our phonemes disagree with Wiktionary and no decision is recorded,
    schwa cases first, shortest words first. Test (held-out) words are never offered."""
    decided = load_decisions()
    wikt = load_wiktionary()
    out = []
    for word, row in load_lexicon().items():
        if row["source"] != "headword" or row["split"] != "train" or row["agrees"] != "no" or word in decided:
            continue
        ours = row["phonemes"].split()
        refs = [wikt_to_ours(v) for v in wikt.get(word, ())]
        if not refs:
            continue
        ref = min(refs, key=lambda r: sum(a != b for a, b in zip(r, ours)) + abs(len(r) - len(ours)))
        kind = diff_kind(ours, ref)
        out.append({"word": word, "kind": kind, "ours": row["phonemes"], "wiktionary": " ".join(ref),
                    "wiktionary_ipa": row["wiktionary"], "hybrid": row["hybrid"]})
    rank = {k: i for i, k in enumerate(REVIEW_PRIORITY)}
    out.sort(key=lambda r: (rank.get(r["kind"], len(rank)), len(r["word"]), r["word"]))
    return out[:n]


def record_decision(word: str, decision: str, phonemes: list[str]) -> None:
    """Record a review decision: 'ours', 'wiktionary', 'rival' (the audio check's alternative form),
    'custom', or the name of a word list the word was added to (e.g. 'loanwords.txt').
    'wiktionary', 'rival' and 'custom' are also written to data/exceptions.tsv (rule S0), so the
    G2P, and every dictionary built from it, uses them from now on."""
    from g2p import schwa

    decisions = load_decisions()
    decisions[word] = (decision, " ".join(phonemes))
    with open(DECISIONS_TSV, "w", encoding="utf-8") as f:
        f.write("word\tdecision\tphonemes\n")
        for w in sorted(decisions):
            f.write(f"{w}\t{decisions[w][0]}\t{decisions[w][1]}\n")
    if decision in ("wiktionary", "rival", "custom"):
        schwa.save_exception(word, phonemes)


# ---------- owner verdicts from the (finished) W5 medial-syncope check ----------
# W5 was rejected (right on 13 of 68 words). Its verdicts stay as owner-verified pronunciations:
# 'right'/'custom' words are in data/exceptions.tsv; 'wrong' words confirm our current output.

RULE_REVIEW_TSV = ROOT / "data" / "rule_review.tsv"


def load_rule_verdicts() -> dict[tuple[str, str], tuple[str, str]]:
    """(rule, word) -> (verdict, phonemes) from data/rule_review.tsv."""
    if not RULE_REVIEW_TSV.exists():
        return {}
    out = {}
    for line in RULE_REVIEW_TSV.read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip():  # blank or tab-only rows (spreadsheet editors append them)
            continue
        rule, word, verdict, phonemes = line.split("\t")
        out[rule, word] = (verdict, phonemes)
    return out
