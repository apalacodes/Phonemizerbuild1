"""Compare phonemizers: espeak-ng's IPA mapped to our inventory, error kinds, and PER scoring.

Standard library only; espeak-ng itself is an external program (espeak-ng -v ne).
PER = phoneme edit distance / reference phonemes.
"""

import collections
import functools
import re
import subprocess
import time
import unicodedata
from collections.abc import Callable
from pathlib import Path

NASAL = "̃"
VOWELS = {"i", "e", "a", "ʌ", "o", "u", "ʌi", "ʌu"}

# Our inventory as tokens, longest first, for tokenizing normalized IPA strings.
TOKENS = sorted([
    "tsʰ", "dzʱ", "t̪ʰ", "d̪ʱ", "kʰ", "gʱ", "ts", "dz", "ʈʰ", "ɖʱ", "t̪", "d̪", "pʰ", "bʱ",
    "ʌi", "ʌu", "k", "g", "ŋ", "ʈ", "ɖ", "n", "p", "b", "m", "j", "r", "l", "s", "ɦ", "w",
    "i", "e", "a", "ʌ", "o", "u",
], key=len, reverse=True)


def _nfd(s: str) -> str:
    return unicodedata.normalize("NFD", s)


def tokenize(ipa: str) -> list[str]:
    """Greedy longest-match into our inventory; a following U+0303 stays on its vowel.
    Unknown characters become their own token (so they count as differences)."""
    out, i = [], 0
    while i < len(ipa):
        for t in TOKENS:
            if ipa.startswith(t, i):
                out.append(t)
                i += len(t)
                break
        else:
            out.append(ipa[i])
            i += 1
        if i < len(ipa) and ipa[i] == NASAL and out:
            out[-1] += NASAL
            i += 1
    return out


# ---------- espeak IPA -> our inventory (CLAUDE.md bench rules, w kept as w) ----------

_ESPEAK_SUB = [
    ("tʃ", "ts"), ("dʒ", "dz"), ("ɡ", "g"), ("c", "ts"), ("ɟ", "dz"), ("ɾ", "r"), ("h", "ɦ"),
    ("ʃ", "s"), ("ʂ", "s"), ("ɳ", "n"), ("ɲ", "n"), ("ʋ", "w"), ("ə", "ʌ"), ("ɪ", "i"), ("ʊ", "u"),
    ("ɛ", "ʌi"), ("ɔ", "ʌu"),
]
_ASPIRATED_VOICED = {"gʰ": "gʱ", "dzʰ": "dzʱ", "dʰ": "d̪ʱ", "bʰ": "bʱ", "ɖʰ": "ɖʱ"}


def espeak_to_ours(ipa: str) -> list[str]:
    s = _nfd(ipa)
    for ch in "ˈˌːʲ_‍ ":
        s = s.replace(ch, "")
    for a, b in _ESPEAK_SUB:
        s = s.replace(a, b)
    for a, b in _ASPIRATED_VOICED.items():
        s = s.replace(a, b)
    s = re.sub("t(?![̪sʰ])", "t̪", s)  # espeak's plain t/d are dental
    s = s.replace("tʰ", "t̪ʰ")
    s = re.sub("(?<![ɖ̪])d(?![̪zʱ])", "d̪", s)
    return tokenize(s)


def ipa_to_ours(ipa: str) -> list[str]:
    """General IPA for one word (e.g. a hand-written or generated ground truth) -> our phoneme tokens.

    Notation only, never pronunciation: ɾ -> r, dʰ gʰ bʰ -> d̪ʱ gʱ bʱ, plain t d -> dental t̪ d̪,
    a plain h right after a stop -> aspiration (sathi -> s a t̪ʰ i), h elsewhere -> ɦ, stress and
    length marks dropped (the same mapping as espeak_to_ours); a nasalized diphthong written with
    the tilde on its first part (ʌ̃i, ʌ̃u) is our ʌĩ, ʌũ."""
    s = re.sub(r"(?<=[kgtdpbʈɖ])h", "ʰ", _nfd(ipa))
    s = re.sub(f"ʌ{NASAL}([iu])", f"ʌ\\1{NASAL}", s)
    return espeak_to_ours(s)


def load_sentences(path: Path, basis: str = "sentences") -> tuple[list[tuple[str, str, list[str]]], list[dict]]:
    """A sentence-level ground truth file (TSV or CSV, columns sentence, sentence_ipa); see parse_sentences."""
    return parse_sentences(path.read_text(encoding="utf-8-sig"), basis)


def parse_sentences(text: str, basis: str = "sentences") -> tuple[list[tuple[str, str, list[str]]], list[dict]]:
    """Sentence-level ground truth: a header with the columns sentence and sentence_ipa (IPA words
    separated by spaces), tab- or comma-separated.

    A word may list several accepted pronunciations separated by "/" (dzʌnʌta/dzʌnta): the first is
    the reference, the others are accepted alternatives (see alternatives_of and score).

    Returns benchmark rows (word, basis, phonemes) for score(), and one dict per sentence:
    {sentence, words, ipa_words, variants, ok}: variants[i] = the accepted pronunciations of word i
    (our symbols); ok is False when the word counts differ (then the sentence is left out of the
    rows, since its words cannot be paired)."""
    import csv
    import io

    from .normalize import tokenize as split_words

    first = text.lstrip("﻿").splitlines()[0] if text.strip() else ""
    table = list(csv.DictReader(io.StringIO(text.lstrip("﻿")), dialect="excel-tab" if "\t" in first else "excel"))
    if not table or not {"sentence", "sentence_ipa"} <= set(table[0]):
        raise ValueError("a sentence ground truth needs a header row with the columns: sentence, sentence_ipa")
    rows, sentences = [], []
    for rec in table:
        if not (rec.get("sentence") or "").strip():
            continue
        sentence = rec["sentence"].strip()
        words, ipa_words = split_words(sentence), (rec.get("sentence_ipa") or "").split()
        ok = len(words) == len(ipa_words)
        variants = [[ipa_to_ours(v) for v in ipa.split("/") if v] for ipa in ipa_words]
        sentences.append({"sentence": sentence, "words": words, "ipa_words": ipa_words,
                          "variants": variants, "ok": ok})
        if ok:
            rows += [(w, basis, v[0]) for w, v in zip(words, variants)]
    return rows, sentences


def dual_words(sentences: list[dict]) -> dict[str, dict[str, list[str]]]:
    """Words a sentence ground truth pronounces in more than one way depending on the sentence
    (दिन d̪ i n / d̪ i n ʌ): word -> {pronunciation: [sentences where it is used]}. Word-by-word
    phonemizers can only give one of them."""
    seen: dict[str, dict[str, list[str]]] = {}
    for s in sentences:
        if s["ok"]:
            for w, v in zip(s["words"], s["variants"]):
                if w.isascii():  # digits the text left as numerals
                    continue
                seen.setdefault(w, {}).setdefault(" ".join(v[0]), []).append(s["sentence"])
    return {w: forms for w, forms in seen.items() if len(forms) > 1}


def alternatives_of(sentences: list[dict]) -> dict[str, list[list[str]]]:
    """word -> all accepted pronunciations, for the words that list more than one ("/")."""
    out: dict[str, list[list[str]]] = {}
    for s in sentences:
        if s["ok"]:
            for w, v in zip(s["words"], s["variants"]):
                if len(v) > 1:
                    out[w] = v
    return out


@functools.cache
def espeak_ipa(word: str) -> str:
    return subprocess.run(["espeak-ng", "-v", "ne", "-q", "--ipa=3", word],
                          capture_output=True, text=True, check=True).stdout.strip()


def diff_kind(system: list[str], ref: list[str]) -> str:
    """Rough label for the main difference between two phoneme lists."""
    if system == ref:
        return "match"
    s_end, r_end = system[-1:] or [""], ref[-1:] or [""]
    final_schwa = {"ʌ", "o"}
    if system[:-1] == ref and s_end[0] in final_schwa:
        return "final schwa: system keeps, ref deletes"
    if ref[:-1] == system and r_end[0] in final_schwa:
        return "final schwa: system deletes, ref keeps"
    if len(system) == len(ref) and system[:-1] == ref[:-1] and {s_end[0], r_end[0]} == {"ʌ", "o"}:
        return "final ʌ vs o"
    if [p.replace("w", "b") for p in system] == [p.replace("w", "b") for p in ref]:
        return "w vs b"
    if [p for p in system if p != "ʌ"] == [p for p in ref if p != "ʌ"]:
        return "medial schwa"
    if [p.rstrip(NASAL) for p in system] == [p.rstrip(NASAL) for p in ref]:
        return "nasalization"
    return "other"


def edit_distance(a: list[str], b: list[str]) -> int:
    """Levenshtein distance between two phoneme lists."""
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def load_benchmark(path: Path) -> list[tuple[str, str, list[str]]]:
    """(word, basis, phonemes) rows of a benchmark TSV with columns word, phonemes, ..., basis."""
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t")
    iw, ip, ib = header.index("word"), header.index("phonemes"), header.index("basis")
    return [(r[iw], r[ib], r[ip].split()) for r in (line.split("\t") for line in lines[1:])]


def score(bench: list[tuple[str, str, list[str]]], system: Callable[[str], list[str]],
          alternatives: dict[str, list[list[str]]] | None = None) -> dict:
    """Score one system (word -> phonemes) on benchmark rows.

    `alternatives`: word -> every accepted pronunciation; the output is right when it matches any
    of them, and the edit distance is taken to the closest one.

    Returns acc (word accuracy), per (edit distance / reference phonemes), wps, and
    per_basis: basis -> [correct, words, edit distance, reference phonemes], kinds (error kind counts),
    errors [(word, basis, system phonemes, benchmark phonemes, kind, edit distance)].
    """
    alternatives = alternatives or {}
    t0 = time.time()
    outputs = {w: system(w) for w, _, _ in bench}
    wps = len(bench) / max(time.time() - t0, 1e-9)
    exact = dist = length = 0
    per_basis, kinds, errors = collections.defaultdict(lambda: [0, 0, 0, 0]), collections.Counter(), []
    for word, basis, ref in bench:
        out = outputs[word]
        accepted = alternatives.get(word) or [ref]
        ok = out in accepted
        ref = min(accepted, key=lambda a: edit_distance(out, a))
        d = edit_distance(out, ref)
        exact, dist, length = exact + ok, dist + d, length + len(ref)
        b = per_basis[basis]
        b[0], b[1], b[2], b[3] = b[0] + ok, b[1] + 1, b[2] + d, b[3] + len(ref)
        if not ok:
            kind = diff_kind(out, ref)
            kinds[kind] += 1
            errors.append((word, basis, " ".join(out), " ".join(ref), kind, d))
    return {"acc": exact / len(bench), "per": dist / max(length, 1), "wps": wps,
            "per_basis": dict(per_basis), "kinds": kinds, "errors": errors}
