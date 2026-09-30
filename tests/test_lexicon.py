"""Integrity of data/lexicon.tsv (built by bench/build_lexicon.py)."""

import csv
from pathlib import Path

import pytest

from tests.test_mapping import INVENTORY

LEXICON = Path(__file__).resolve().parent.parent / "data" / "lexicon.tsv"
pytestmark = pytest.mark.skipif(not LEXICON.exists(), reason="lexicon not built")


@pytest.fixture(scope="module")
def rows():
    with open(LEXICON, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE))


def test_phonemes_use_inventory(rows):
    nasal = "̃"
    bad = {p for r in rows for p in r["phonemes"].split() if p.replace(nasal, "") not in INVENTORY}
    assert not bad


def test_words_unique_and_pronounced(rows):
    words = [r["word"] for r in rows]
    assert len(words) == len(set(words))
    assert all(r["phonemes"] and r["hybrid"] for r in rows)


def test_heldout_lemmas_never_in_train(rows):
    test_lemmas = {r["lemma"] for r in rows if r["split"] == "test"}
    assert not [r["word"] for r in rows if r["split"] == "train" and r["lemma"] in test_lemmas]
