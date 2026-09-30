"""Aligner dictionary entries (g2p/variants.py): our pronunciation first, then rivals for MFA to reject."""

import pytest

from g2p import phonemize_word
from g2p.variants import schwa_variants


@pytest.mark.parametrize("word, ours, rivals", [
    ("कमल", "k ʌ m ʌ l", ["k ʌ m ʌ l ʌ"]),          # S11 decision tested against a kept schwa
    ("सुलह", "s u l ʌ ɦ ʌ", ["s u l ʌ ɦ"]),          # S8 decision tested against a deleted schwa
    ("समय", "s ʌ m ʌ j", []),                        # S0: owner decided by audio, no rivals
    ("घरमा", "gʱ ʌ r m a", ["gʱ ʌ r ʌ m a"]),        # stem-final schwa; suffix unchanged
    ("कपडा", "k ʌ p ʌ ɖ a", ["k ʌ p ɖ a"]),         # S3 tested against medial syncope
    ("सुख", "s u kʰ ʌ", []),                        # S0: owner decided, no rivals
    ("म", "m ʌ", []),                               # single akshara
    ("गरेको", "g ʌ r e k o", []),                    # no schwa to test
])
def test_ours_first_then_rivals(word, ours, rivals):
    v = schwa_variants(word)
    assert v[0] == ("ours", ours.split())
    assert [" ".join(p) for _, p in v[1:]] == rivals
    assert all(k.startswith("rival_") for k, _ in v[1:])


def test_ours_is_the_g2p_output():
    for w in ["नेपालको", "सम्बन्ध", "मानव", "संगीत"]:
        assert schwa_variants(w)[0] == ("ours", phonemize_word(w))
