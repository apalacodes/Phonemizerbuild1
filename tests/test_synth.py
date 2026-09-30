import shutil

import pytest

from tts.ipa_map import word_to_ipa
from tts.synth import phonemes_for


@pytest.mark.parametrize("phonemes, expected", [
    ("gʱ ʌ r", "ɡʰˈʌɾ"),                 # stressed schwa stays ʌ
    ("n e p a l", "nˈeːpaːl"),
    ("m ʌ ɦ ʌ̃ g o", "mˈʌhʌ̃ɡoː"),  # unstressed nasal schwa
    ("t̪ ʌ l ʌ", "tˈʌlə"),                # unstressed schwa -> ə
    ("dz u n", "ɟˈun"),
])
def test_word_to_ipa(phonemes, expected):
    assert word_to_ipa(phonemes.split()) == expected


def test_word_to_ipa_without_stress():
    assert word_to_ipa("gʱ ʌ r ʌ".split(), stress=False) == "ɡʰəɾə"


def test_phonemes_for_ours_sentences():
    display, symbols = phonemes_for("घर छ। नाम, काम", "ours")
    assert display == "gʱ ʌ r | tsʰ ʌ . n a m , k a m ."
    assert "".join(symbols) == "ɡʰˈʌɾ cʰˈʌ. nˈaːm, kˈaːm."


def test_phonemes_for_rejects_unknown_g2p():
    with pytest.raises(ValueError):
        phonemes_for("घर", "other")


@pytest.mark.skipif(not shutil.which("espeak-ng"), reason="espeak-ng not installed")
def test_phonemes_for_espeak():
    display, symbols = phonemes_for("घर", "espeak")
    assert "ɡ" in display and symbols[-1] == "."


@pytest.mark.parametrize("style, expected", [("ə", "ɾˈʌhənə"), ("ˌə", "ɾˈʌhənˌə"), ("ʌ", "ɾˈʌhənʌ")])
def test_word_to_ipa_final_schwa_style(style, expected):
    assert word_to_ipa("r ʌ ɦ ʌ n ʌ".split(), final_schwa=5, schwa_style=style) == expected


def test_ours_mode_final_schwa_only_on_stem_end():
    _, symbols = phonemes_for("वर्षको र", "ours", schwa_style="ˌə")
    assert "".join(symbols) == "bˈʌɾsˌəkoː ɾˈʌ."


def test_wiktionary_mode_falls_back_to_ours():
    display, _ = phonemes_for("क्ष्ज्ञ", "wiktionary")
    assert display.startswith("*")
