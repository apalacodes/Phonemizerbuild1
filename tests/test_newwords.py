"""Opt-in log of words the lexicon does not know (g2p/newwords.py)."""

from g2p import newwords, phonemize, phonemize_word


def test_off_by_default():
    assert newwords.active() is None


def test_logs_each_unknown_word_once(tmp_path):
    lexicon = tmp_path / "lexicon.dict"
    lexicon.write_text("घर\tgʱ ʌ r\n", encoding="utf-8")
    log = tmp_path / "new.tsv"
    newwords.enable(log, lexicon)
    try:
        phonemize("घर कमल")
        phonemize_word("कमल")          # already logged
    finally:
        newwords.disable()
    rows = log.read_text(encoding="utf-8").splitlines()
    assert rows[0] == "word\tphonemes\trules\tfirst_seen"
    assert [r.split("\t")[:3] for r in rows[1:]] == [["कमल", "k ʌ m ʌ l", "क:S2+ म:S3+ ल:S11-"]]


def test_existing_log_is_not_duplicated(tmp_path):
    lexicon = tmp_path / "lexicon.dict"
    lexicon.write_text("", encoding="utf-8")
    log = tmp_path / "new.tsv"
    log.write_text("word\tphonemes\trules\tfirst_seen\nकमल\tk ʌ m ʌ l\t-\t2026-01-01\n", encoding="utf-8")
    newwords.enable(log, lexicon)
    try:
        phonemize_word("कमल")
    finally:
        newwords.disable()
    assert log.read_text(encoding="utf-8").count("कमल") == 1
