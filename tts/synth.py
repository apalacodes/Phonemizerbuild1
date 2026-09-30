"""Text -> phonemes -> IPA symbols -> Kokoro voice -> wav.

--g2p ours        our rule-based G2P
--g2p espeak      espeak-ng as-is (baseline)
--g2p hybrid      espeak-ng's stress/length, corrected to our G2P's segments (tts/hybrid.py)
--g2p wiktionary  Wiktionary's IPA with espeak's stress/length; ours where it lacks the word (*)

A kept stem-final schwa is voiced as DEFAULT_SCHWA (ˌə, medium); --schwa ə / ʌ for light / full.

uv run tts/synth.py "नेपाल" --g2p hybrid -o out.wav
"""

import argparse
import re
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a script: make the repo root importable
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from g2p import analyze_word
from g2p.normalize import normalize, tokenize
from g2p.reference import wiktionary_phonemes
from tts.hybrid import espeak_ipa, espeak_words, fix_word
from tts.ipa_map import is_vowel, word_to_ipa

ROOT = Path(__file__).resolve().parent.parent
G2P_MODES = ("ours", "espeak", "hybrid", "wiktionary")
DEFAULT_SCHWA = "ˌə"
_CLAUSE = re.compile(r"([^।॥.?!,;:]+)([।॥.?!,;:]*)")


def clauses(text: str) -> list[tuple[list[str], str]]:
    """Split text into (words, terminator) clauses. Terminators become pause symbols:
    । ॥ . -> "."   ? -> "?"   ! -> "!"   , ; : -> ","   (end of text -> ".")."""
    out = []
    for chunk, punct in _CLAUSE.findall(normalize(text)):
        words = tokenize(chunk)
        if not words:
            continue
        if "?" in punct:
            term = "?"
        elif "!" in punct:
            term = "!"
        elif punct and set(punct) <= set(",;:"):
            term = ","
        else:
            term = "."
        out.append((words, term))
    return out


def _join(parts: list[tuple[str, str]]) -> list[str]:
    """[(clause symbols, terminator)] -> one symbol list: "clause, clause. clause."""
    return list(" ".join(sym + term for sym, term in parts))


def _ours_word(word: str) -> tuple[list[str], int | None]:
    """Our phonemes and the index of a kept stem-final schwa (or None). One-syllable words
    (र छ म) are excluded: their schwa is the only vowel and stays as it is."""
    a = analyze_word(word)
    return a.phonemes, _final_schwa(a.phonemes, a.stem_len)


def _final_schwa(phonemes: list[str], stem_len: int) -> int | None:
    k = stem_len - 1
    if k < 1 or phonemes[k] != "ʌ" or not any(is_vowel(p) for p in phonemes[:k]):
        return None
    return k


def _ours(text, stress, schwa_style):
    display, parts = [], []
    for words, term in clauses(text):
        analysed = [_ours_word(w) for w in words]
        display.append(" | ".join(" ".join(p) for p, _ in analysed) + f" {term}")
        parts.append((" ".join(word_to_ipa(p, stress, fs, schwa_style) for p, fs in analysed), term))
    return " ".join(display), _join(parts)


def _espeak(text):
    display, parts = [], []
    for words, term in clauses(text):
        ipa = " ".join(espeak_ipa(" ".join(words)).split()).replace("\u200d", "")
        display.append(f"{ipa} {term}")
        parts.append((ipa, term))
    return " ".join(display), _join(parts)


def _hybrid(text, schwa_style):
    display, parts = [], []
    for words, term in clauses(text):
        fixed = []
        for w, e in zip(words, espeak_words(words)):
            phonemes, fs = _ours_word(w)
            fixed.append(fix_word(e, phonemes, fs, schwa_style))
        display.append(" ".join(fixed) + f" {term}")
        parts.append((" ".join(fixed), term))
    return " ".join(display), _join(parts)


def _wiktionary(text, schwa_style):
    """Wiktionary's segments with espeak's stress/length (same treatment as hybrid), so it
    differs from hybrid only in the sounds. Words Wiktionary lacks use ours, marked *."""
    display, parts = [], []
    for words, term in clauses(text):
        fixed = []
        for w, e in zip(words, espeak_words(words)):
            phonemes = wiktionary_phonemes(w)
            if phonemes:
                fixed.append(fix_word(e, phonemes, _final_schwa(phonemes, len(phonemes)), schwa_style))
            else:
                phonemes, fs = _ours_word(w)
                fixed.append("*" + fix_word(e, phonemes, fs, schwa_style))
        display.append(" ".join(fixed) + f" {term}")
        parts.append((" ".join(fixed).replace("*", ""), term))
    return " ".join(display), _join(parts)


def hybrid_for_phonemes(word: str, phonemes: list[str], schwa_style: str = DEFAULT_SCHWA) -> list[str]:
    """Voice symbols for one word given explicit phonemes (our inventory), with espeak's
    stress/length, exactly as the hybrid mode would speak them. Used to audition corrections."""
    return list(fix_word(espeak_ipa(word), phonemes, _final_schwa(phonemes, len(phonemes)), schwa_style) + ".")


def phonemes_for(
    text: str, g2p: str, stress: bool = True, schwa_style: str = DEFAULT_SCHWA,
) -> tuple[str, list[str]]:
    """(human-readable phoneme string, voice symbols) for `text`. g2p: one of G2P_MODES."""
    if g2p == "ours":
        return _ours(text, stress, schwa_style)
    if g2p == "espeak":
        return _espeak(text)
    if g2p == "hybrid":
        return _hybrid(text, schwa_style)
    if g2p == "wiktionary":
        return _wiktionary(text, schwa_style)
    raise ValueError(f"unknown g2p {g2p!r}; use one of {G2P_MODES}")


def main() -> None:
    from tts.kokoro_voice import HINDI_VOICES, KokoroVoice, write_wav

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("text")
    parser.add_argument("--g2p", choices=G2P_MODES, default="hybrid")
    parser.add_argument("-o", "--output", type=Path, default=Path("out.wav"))
    parser.add_argument("--voice", choices=HINDI_VOICES, default="hm_omega")
    parser.add_argument("--no-stress", action="store_true", help="ours only: do not add ˈ to each word")
    parser.add_argument("--schwa", default=DEFAULT_SCHWA, choices=["ə", "ˌə", "ʌ"], help="kept final schwa")
    parser.add_argument("--length-scale", type=float)
    args = parser.parse_args()

    display, symbols = phonemes_for(args.text, args.g2p, not args.no_stress, args.schwa)
    voice = KokoroVoice.load(voice=args.voice)
    print(display)
    print("voice:", voice.to_ipa(symbols))
    audio, sr = voice.synthesize(symbols, length_scale=args.length_scale)
    write_wav(args.output, audio, sr)
    if voice.last_missing:
        print("dropped:", " ".join(sorted(voice.last_missing)))
    print(f"wrote {args.output} ({len(audio) / sr:.2f}s)")


if __name__ == "__main__":
    main()
