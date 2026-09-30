"""Hybrid = espeak prosody + our segments. espeak strings below were captured from espeak-ng -v ne."""

import shutil
import unicodedata

import pytest

from g2p import phonemize_word
from tts.hybrid import canonical, espeak_segments, fix_word
from tts.synth import clauses, phonemes_for


def nfd(s):
    return unicodedata.normalize("NFD", s)


@pytest.mark.parametrize("word, espeak, expected", [
    ("रहन", "ɾˈʌhən", "ɾˈʌhənə"),               # our schwa added, light ə (S0)
    ("दुख", "dˈukʰ", "dˈukʰə"),                 # our schwa added, light ə (S0)
    ("रिस्क", "ɾˈɪskə", "ɾˈɪsk"),               # espeak's extra schwa dropped (S9)
    ("र", "ɾə", "ɾə"),                          # unstressed function word stays unstressed
    ("ठूलो", "ʈʰˈuːloː", "ʈʰˈuːloː"),           # espeak's long uː kept
    ("असुरक्षित", "ˌəsuɾˈʌkʂɪt", "ˌəsuɾˈʌkʂɪt"),  # क्ष: espeak ʂ kept (hybrid_keep_espeak.tsv)
    ("धेरै", "dʰˈeːɾɛː", "dʰˈeːɾai"),           # ऐ: our diphthong, voiced as ai
    ("ऐना", "ˈʌ\u200dɪnaː", "ˈainaː"),
    ("अनुभव", "ənubʰˌəwˌə", "ənubʰˌəw"),        # व -> w (W1), final schwa dropped
    ("हेर्नु", "hˈeːrrnuʲˌu", "hˈeːɾnˌu"),      # espeak's doubled r / extra u removed
    ("औंसीको", "ˈʌ\u200dʊnsɪːkˌoː", "ˈʌũsɪːkˌoː"),  # nasal vowel, not n
    ("नेपाल", "neːpˈaːl", "neːpˈaːl"),          # agreement: espeak unchanged
])
def test_fix_word(word, espeak, expected):
    assert fix_word(espeak, phonemize_word(word)) == nfd(expected)


def test_fix_word_without_our_phonemes_uses_espeak():
    assert fix_word("tiːn", []) == "tiːn"


def test_segments_and_canonical():
    assert espeak_segments("ɡʰˈʌɾə") == [("", "ɡʰ"), ("ˈ", "ʌ"), ("", "ɾ"), ("", "ə")]
    assert [canonical(s) for s in ["ɡʰ", "cʰ", "ʃ", "w", "aː", "ɪː", "ə", "ɛː"]] == \
        ["gʱ", "tsʰ", "s", "b", "a", "i", "ʌ", "ʌi"]


def test_clauses_keep_pauses():
    assert clauses('घर छ, "नाम" के हो? राम्रो।') == [
        (["घर", "छ"], ","), (["नाम", "के", "हो"], "?"), (["राम्रो"], "."),
    ]


@pytest.mark.skipif(not shutil.which("espeak-ng"), reason="espeak-ng not installed")
def test_hybrid_sentence():
    display, symbols = phonemes_for("रहन धेरै दुख र रिस्क हुन्छ।", "hybrid", schwa_style="ə")
    assert display == nfd("ɾˈʌhənə dʰˈeːɾai dˈukʰə ɾə ɾˈɪsk hˈuncʰə .")
    assert "".join(symbols).endswith("hˈuncʰə.")


@pytest.mark.skipif(not shutil.which("espeak-ng"), reason="espeak-ng not installed")
def test_hybrid_medium_final_schwa():
    # stem-final kept schwa gets secondary stress; one-syllable र stays light
    display, _ = phonemes_for("वर्षको रहन र", "hybrid", schwa_style="ˌə")
    assert display == nfd("bˈʌɾsˌəkˌoː ɾˈʌhənˌə ɾə .")


def test_fix_word_schwa_style():
    assert fix_word("dˈukʰ", "d̪ u kʰ ʌ".split(), final_schwa=3, schwa_style="ˌə") == nfd("dˈukʰˌə")
    assert fix_word("dˈukʰ", "d̪ u kʰ ʌ".split(), final_schwa=3, schwa_style="ə") == nfd("dˈukʰə")
