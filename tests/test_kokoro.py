import numpy as np
import pytest

from tts.kokoro_voice import KokoroVoice
from tts.synth import phonemes_for

pytestmark = pytest.mark.skipif(not KokoroVoice.available(), reason="Kokoro model not downloaded")


@pytest.fixture(scope="module")
def voice():
    return KokoroVoice.load(voice="hm_omega")


def test_espeak_affricates_become_ipa(voice):
    assert voice.to_ipa(list("cʰˈə ɟˈaː")) == "ʦʰˈə ʣˈaː"


def test_all_our_symbols_known(voice):
    # every symbol any mode can send for a sentence covering our inventory
    text = "सरकारले अठार वर्षको अधिकार कोही पनि बताएको छ। हिजो पार्कमा संगीत सुन्दै अदुवा चिया पिउँदा धेरै खुसी।"
    for mode in ("ours", "hybrid", "wiktionary", "espeak"):
        voice.symbols_to_ids(phonemes_for(text, mode)[1])
        assert voice.last_missing == set(), mode


def test_synthesize_smoke(voice):
    audio, sr = voice.synthesize(phonemes_for("नेपाल", "hybrid")[1])
    assert sr == 24000 and audio.dtype == np.float32
    assert 0.2 < len(audio) / sr < 3 and np.abs(audio).max() <= 1.0
