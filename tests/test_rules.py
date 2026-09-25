"""Required tests from CLAUDE.md, plus one test per implemented schwa rule."""

import pytest

from g2p import phonemize_word, schwa
from g2p.segment import segment


def xfail(reason):
    return pytest.mark.xfail(reason=reason, strict=True)


# word, expected, rules (as listed in CLAUDE.md), marks
REQUIRED = [
    ("कमल", "k ʌ m ʌ l", "S11", ()),
    ("समय", "s ʌ m ʌ j ʌ", "S2, S8", ()),
    ("कस्तो", "k ʌ s t̪ o", "S1", ()),
    ("झन्", "dzʱ ʌ n", "halanta", ()),
    ("गुरुङ", "g u r u ŋ", "S4", ()),
    ("रङ", "r ʌ ŋ", "S4", ()),
    ("माघ", "m a gʱ", "S11", ()),
    ("कारण", "k a r ʌ n", "S11", ()),
    ("साथ", "s a t̪ʰ", "S11", ()),
    ("देश", "d̪ e s", "S11", ()),
    ("मानव", "m a n ʌ b", "S11, POST-2", ()),
    ("अन्त", "ʌ n t̪ ʌ", "S10", ()),
    ("सम्बन्ध", "s ʌ m b ʌ n d̪ʱ ʌ", "S10", ()),
    ("हुन्छ", "ɦ u n tsʰ ʌ", "S7/S8/S10", ()),
    ("भएर", "bʱ ʌ e r ʌ", "S7", ()),
    ("रहन", "r ʌ ɦ ʌ n ʌ", "S7 (infinitive)", ()),
    ("छन्", "tsʰ ʌ n", "halanta", ()),
    ("यस", "j ʌ s", "S5", ()),
    ("जुन", "dz u n", "S5", ()),
    ("अब", "ʌ b ʌ", "S6", ()),
    ("आज", "a dz ʌ", "S6", ()),
    ("सुख", "s u kʰ ʌ", "S0", ()),
    ("दुख", "d̪ u kʰ ʌ", "S0", ()),
    ("पार्क", "p a r k", "S9", ()),
    ("मार्च", "m a r ts", "S9", ()),
    ("मञ्च", "m ʌ n ts", "S9", ()),
    ("घरमा", "gʱ ʌ r m a", "suffix split + S11", ()),
    ("नेपालको", "n e p a l k o", "suffix split + S11", ()),
    ("संगीत", "s ʌ ŋ g i t̪", "POST-1, S11", (xfail("POST-1 (phase 4)"),)),
    ("महँगो", "m ʌ ɦ ʌ̃ g o", "S1, POST-3", ()),
    ("छ", "tsʰ ʌ", "S2", ()),
    ("म", "m ʌ", "S2", ()),
    ("ज्ञान", "g j a n", "mapping, S11", ()),
]


@pytest.mark.parametrize(
    "word, expected",
    [pytest.param(w, e, id=w, marks=m) for w, e, _, m in REQUIRED],
)
def test_required(word, expected):
    assert " ".join(phonemize_word(word)) == expected


def rule_for(word, index):
    """(keep, rule ID) that schwa.py chose for akshara `index` of `word`."""
    return schwa.decide_with_rules(segment(word))[index]


def test_s1_conjunct_follows():
    assert rule_for("कस्तो", 0) == (True, "S1")


def test_s1_halanta_follows():
    assert rule_for("झन्", 0) == (True, "S1")


def test_s1_chandrabindu():
    assert rule_for("महँगो", 1) == (True, "S1")


def test_s2_first_akshara():
    assert rule_for("छ", 0) == (True, "S2")
    assert rule_for("कमल", 0) == (True, "S2")


def test_s3_medial():
    assert rule_for("कमल", 1) == (True, "S3")


def test_s4_final_nga():
    assert rule_for("रङ", 1) == (False, "S4")


def test_s8_final_ya_cha_ha():
    assert rule_for("समय", 2) == (True, "S8")
    assert rule_for("सुलह", 2) == (True, "S8")
    # Final छ is caught earlier by S7 (छ is in verb_endings.txt); same KEEP result.
    assert rule_for("कच्छ", 1) == (True, "S7")


def test_s5_pronoun():
    assert rule_for("यस", 1) == (False, "S5")
    assert rule_for("हजुर", 2) == (False, "S5")


def test_s5_pronoun_stem_after_suffix_split():
    assert phonemize_word("हजुरको") == "ɦ ʌ dz u r k o".split()


def test_s6_adverb():
    assert rule_for("अब", 1) == (True, "S6")


def test_s6_postposition():
    assert rule_for("बाट", 1) == (True, "S6")
    assert phonemize_word("तलको") == "t̪ ʌ l ʌ k o".split()


def test_s7_verb_ending():
    assert rule_for("भएर", 2) == (True, "S7")
    assert rule_for("गरेर", 2) == (True, "S7")
    assert rule_for("गरेछ", 2) == (True, "S7")
    assert rule_for("गर्दैन", 2) == (True, "S7")


def test_s7_does_not_catch_nouns():
    assert rule_for("घर", 1) == (False, "S11")
    assert rule_for("ज्ञान", 1) == (False, "S11")


def test_s9_loanword_final_conjunct():
    assert rule_for("पार्क", 1) == (False, "S9")
    assert rule_for("मञ्च", 1) == (False, "S9")


def test_s9_needs_conjunct():
    assert rule_for("अन्त", 1) == (True, "S10")


def test_s0_exception_overrides_rules():
    assert phonemize_word("सुख") == "s u kʰ ʌ".split()


def test_s0_exception_blocks_verb_ending():
    # ट्रेन ends in ेन (S7 verb ending) but is an English loan.
    assert phonemize_word("ट्रेन") == "ʈ r e n".split()


def test_s6_postposition_final_consonant_only():
    assert rule_for("वर", 1) == (True, "S6")
    assert rule_for("माझ", 1) == (True, "S6")
    assert rule_for("बीच", 1) == (False, "S11")


def test_s0_exception_on_stem():
    assert phonemize_word("सुखमा") == "s u kʰ ʌ m a".split()


def test_s10_final_conjunct():
    assert rule_for("अन्त", 1) == (True, "S10")


def test_s11_default_delete():
    assert rule_for("कमल", 2) == (False, "S11")


def test_non_inherent_aksharas_have_no_rule():
    assert schwa.decide_with_rules(segment("नेपाल"))[:2] == [(True, None), (True, None)]
