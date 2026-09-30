import unicodedata

import pytest

from g2p.mapping import load_table, raw_phonemes, word_phonemes
from g2p.segment import segment

INVENTORY = {
    "i", "e", "a", "ʌ", "o", "u", "ʌi", "ʌu",
    "ĩ", "ẽ", "ã", "ʌ̃", "ũ", "õ", "ʌĩ", "ʌũ",  # nasalized (POST-1/3); only via G2P output or exceptions
    "k", "kʰ", "g", "gʱ", "ŋ", "ts", "tsʰ", "dz", "dzʱ", "n", "ʈ", "ʈʰ", "ɖ", "ɖʱ",
    "t̪", "t̪ʰ", "d̪", "d̪ʱ", "p", "pʰ", "b", "bʱ", "m", "j", "r", "l", "s", "ɦ",
    "w",  # POST-2: only via exceptions.tsv
}


def test_table_uses_only_inventory_symbols():
    for grapheme, phonemes in load_table().items():
        assert set(phonemes) <= INVENTORY, grapheme


def test_table_has_all_consonants():
    table = load_table()
    for c in "कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह":
        assert len(table[c]) == 1, c


@pytest.mark.parametrize("word, expected", [
    ("सम्बन्ध", "s ʌ m b ʌ n d̪ʱ ʌ"),
    ("महँगो", "m ʌ ɦ ʌ̃ g o"),
    ("ज्ञान", "g j a n ʌ"),
    ("कस्तो", "k ʌ s t̪ o"),
    ("नेपालको", "n e p a l ʌ k o"),
    ("झन्", "dzʱ ʌ n"),
    ("क्षमा", "k tsʰ ʌ m a"),
    ("ऋषि", "r i s i"),
    ("मानव", "m a n ʌ w ʌ"),  # POST-2: non-initial व -> w
    ("मार्च", "m a r ts ʌ"),
    ("भएर", "bʱ ʌ e r ʌ"),
    ("चिसो", "ts i s o"),
    ("कैलाश", "k ʌi l a s ʌ"),
])
def test_raw_phonemes_keep_every_schwa(word, expected):
    assert " ".join(raw_phonemes(word)) == expected


def test_keep_mask_drops_schwa():
    aks = segment("कमल")
    assert " ".join(word_phonemes(aks, keep=[True, True, False])) == "k ʌ m ʌ l"


def test_visarga():
    assert raw_phonemes("दुःख") == ["d̪", "u", "ɦ", "kʰ", "ʌ"]


def test_chandrabindu_nasalizes_matra():
    assert raw_phonemes("गाँउ") == ["g", "ã", "u"]


def test_exceptions_use_only_inventory_symbols():
    from g2p.schwa import load_exceptions
    inventory = {unicodedata.normalize("NFD", p) for p in INVENTORY}  # the G2P writes ã as a + U+0303
    for word, phonemes in load_exceptions().items():
        assert set(phonemes) <= inventory, word


@pytest.mark.parametrize("filename", [
    "pronouns.txt", "adverbs.txt", "postpositions.txt", "verb_endings.txt", "loanwords.txt", "suffixes.txt",
])
def test_word_lists_are_normalized_devanagari(filename):
    from g2p.normalize import normalize
    from g2p.schwa import DATA_DIR
    for line in (DATA_DIR / filename).read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            assert line == line.strip() == normalize(line), (filename, line)
            assert all("ऀ" <= ch <= "ॿ" for ch in line), (filename, line)
