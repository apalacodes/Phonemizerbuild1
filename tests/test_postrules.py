"""POST-1..3 (CLAUDE.md), through the full pipeline."""

import unicodedata

import pytest

from g2p import phonemize_word
from g2p.postrules import anusvara_nasal
from g2p.segment import segment


@pytest.mark.parametrize("word, expected", [
    ("संगीत", "s ʌ ŋ g i t̪"),     # POST-1 velar
    ("संख्या", "s ʌ ŋ kʰ j a"),    # POST-1 velar, before a conjunct
    ("अंक", "ʌ ŋ k ʌ"),          # POST-1 + ं-stop counts as a conjunct (S10)
    ("संत", "s ʌ n t̪ ʌ"),        # POST-1 dental
    ("संबन्ध", "s ʌ m b ʌ n d̪ʱ ʌ"),  # POST-1 labial
    ("पंछी", "p ʌ n tsʰ i"),       # POST-1 palatal
    ("कंठ", "k ʌ n ʈʰ ʌ"),        # POST-1 retroflex
    ("संवाद", "s ʌ m b a d̪"),     # POST-1 before व (= b)
    ("संसार", "s ʌ̃ s a r"),       # POST-1 elsewhere: nasalize
    ("हंस", "ɦ ʌ̃ s"),            # POST-1 elsewhere, final
    ("तपाईंको", "t̪ ʌ p a ĩ k o"),  # ं before a suffix boundary: nasalize
    ("बैंक", "b ʌi ŋ k"),         # loanword: S9 still deletes
])
def test_post1_anusvara(word, expected):
    assert " ".join(phonemize_word(word)) == unicodedata.normalize("NFD", expected)


def test_post1_nasal_table():
    assert anusvara_nasal(segment("क")[0]) == "ŋ"
    assert anusvara_nasal(segment("प")[0]) == "m"
    assert anusvara_nasal(segment("स")[0]) is None
    assert anusvara_nasal(None) is None


def test_post2_va():
    assert phonemize_word("मानव") == "m a n ʌ w".split()   # W1: w after a vowel
    assert phonemize_word("विकास") == "b i k a s".split()  # word-initial: b


@pytest.mark.parametrize("word, expected", [
    ("महँगो", "m ʌ ɦ ʌ̃ g o"),
    ("गाउँ", "g a ũ"),
    ("आँखा", "ã kʰ a"),
])
def test_post3_chandrabindu(word, expected):
    # nasal vowels are always vowel + U+0303 (typed ã/ũ may be precomposed)
    assert " ".join(phonemize_word(word)) == unicodedata.normalize("NFD", expected)


@pytest.mark.parametrize("word, expected", [
    ("अदुवा", "ʌ d̪ u w a"),      # between vowels
    ("आश्विन", "a s w i n"),      # after a consonant
    ("मानव", "m a n ʌ w"),
    ("वर्षा", "b ʌ r s a"),       # word-initial stays b
    ("संवाद", "s ʌ m b a d̪"),    # after ं stays b
])
def test_post2_va(word, expected):
    assert " ".join(phonemize_word(word)) == expected
