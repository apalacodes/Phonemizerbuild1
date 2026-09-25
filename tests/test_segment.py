import pytest

from g2p.segment import format_aksharas, segment


@pytest.mark.parametrize("word, expected", [
    ("सम्बन्ध", "स | म्ब | न्ध"),
    ("महँगो", "म | हँ | गो"),
    ("ज्ञान", "ज्ञा | न"),
    ("कस्तो", "क | स्तो"),
    ("नेपालको", "ने | पा | ल | को"),
    ("झन्", "झ | न्"),
    ("कमल", "क | म | ल"),
    ("छ", "छ"),
    ("आज", "आ | ज"),
    ("भएर", "भ | ए | र"),
    ("संगीत", "सं | गी | त"),
    ("मार्च", "मा | र्च"),
])
def test_segmentation(word, expected):
    assert format_aksharas(segment(word)) == expected


def test_akshara_fields():
    s, mb, ndh = segment("सम्बन्ध")
    assert s.consonants == ("स",) and s.inherent and not s.is_conjunct
    assert mb.consonants == ("म", "ब") and mb.is_conjunct and mb.inherent
    assert ndh.is_conjunct


def test_halanta_akshara():
    jh, n = segment("झन्")
    assert jh.inherent
    assert n.halanta and not n.inherent and n.vowel is None


def test_matra_and_signs():
    ma, ha, go = segment("महँगो")
    assert ha.signs == ("ँ",) and ha.inherent
    assert go.vowel == "ो" and not go.inherent
    assert segment("संगीत")[0].signs == ("ं",)


def test_independent_vowel():
    aa = segment("आज")[0]
    assert aa.consonants == () and aa.vowel == "आ" and not aa.inherent


def test_unknown_chars_skipped():
    assert format_aksharas(segment("कx")) == "क"
    assert format_aksharas(segment("ाक")) == "क"
