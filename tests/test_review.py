"""Review decisions -> data/exceptions.tsv, tested on temporary copies of the data files."""

import shutil

import pytest

from g2p import phonemize_word, reference, schwa


@pytest.fixture
def tmp_data(tmp_path, monkeypatch):
    shutil.copy(schwa.DATA_DIR / "exceptions.tsv", tmp_path / "exceptions.tsv")
    monkeypatch.setattr(schwa, "DATA_DIR", tmp_path)
    monkeypatch.setattr(reference, "DECISIONS_TSV", tmp_path / "review_decisions.tsv")
    schwa.load_exceptions.cache_clear()
    yield tmp_path
    schwa.load_exceptions.cache_clear()


def test_custom_decision_becomes_exception(tmp_data):
    assert phonemize_word("नगर") == "n ʌ g ʌ r".split()
    reference.record_decision("नगर", "custom", "n ʌ g ʌ r ʌ".split())
    assert phonemize_word("नगर") == "n ʌ g ʌ r ʌ".split()            # S0 now applies
    assert phonemize_word("नगरमा") == "n ʌ g ʌ r ʌ m a".split()      # also with a suffix
    assert reference.load_decisions()["नगर"] == ("custom", "n ʌ g ʌ r ʌ")


def test_keep_ours_is_recorded_but_not_an_exception(tmp_data):
    reference.record_decision("तीन", "ours", "t̪ i n".split())
    assert "तीन" not in schwa.load_exceptions()
    assert reference.load_decisions()["तीन"][0] == "ours"


def test_save_exception_replaces_existing_entry(tmp_data):
    schwa.save_exception("अठार", "ʌ ʈʰ a r".split())
    schwa.save_exception("अठार", "ʌ ʈʰ a r ʌ".split())
    lines = [l for l in (tmp_data / "exceptions.tsv").read_text(encoding="utf-8").splitlines() if l.startswith("अठार")]
    assert lines == ["अठार\tʌ ʈʰ a r ʌ"]


def test_owner_decided_words_keep_their_pronunciation():
    """Every word the owner decided by ear (exceptions, Review tab, W5 verdicts; real data files)
    must come out of the G2P exactly as decided, e.g. उनतीस u n t̪ i s, योगदानहरू j o g d̪ a n ɦ ʌ r u."""
    owner = {w: " ".join(p) for w, p in schwa.load_exceptions().items()}
    owner |= {w: p for w, (_d, p) in reference.load_decisions().items()}
    owner |= {w: p for (_r, w), (_v, p) in reference.load_rule_verdicts().items()}
    assert {"उनतीस", "योगदानहरू"} <= owner.keys()
    wrong = {w: (" ".join(phonemize_word(w)), p) for w, p in owner.items() if " ".join(phonemize_word(w)) != p}
    assert not wrong
