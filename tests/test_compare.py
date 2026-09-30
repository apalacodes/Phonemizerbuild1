"""Phonemizer comparison and PER scoring (g2p/compare.py)."""

from g2p.compare import diff_kind, edit_distance, espeak_to_ours, score


def test_edit_distance():
    assert edit_distance("k ʌ m ʌ l".split(), "k ʌ m ʌ l".split()) == 0
    assert edit_distance("k ʌ m ʌ l ʌ".split(), "k ʌ m ʌ l".split()) == 1
    assert edit_distance([], ["a", "b"]) == 2


def test_espeak_to_ours():
    assert espeak_to_ours("neːpˈaːl") == ["n", "e", "p", "a", "l"]
    assert espeak_to_ours("sˈʌməj") == ["s", "ʌ", "m", "ʌ", "j"]


def test_score_per_and_kinds():
    bench = [("कमल", "owner", "k ʌ m ʌ l".split()), ("घर", "agree", "gʱ ʌ r".split())]
    outputs = {"कमल": "k ʌ m ʌ l ʌ".split(), "घर": "gʱ ʌ r".split()}
    r = score(bench, outputs.__getitem__)
    assert r["acc"] == 0.5
    assert r["per"] == 1 / 8  # one insertion over 5 + 3 reference phonemes
    assert r["per_basis"]["owner"] == [0, 1, 1, 5]
    assert r["errors"][0][4] == diff_kind(outputs["कमल"], bench[0][2]) == "final schwa: system keeps, ref deletes"


def test_ipa_to_ours_is_notation_only():
    from g2p.compare import ipa_to_ours
    assert ipa_to_ours("sʌɾkaɾko") == "s ʌ r k a r k o".split()
    assert ipa_to_ours("dʰeɾʌi") == "d̪ʱ e r ʌi".split()
    assert ipa_to_ours("sathi") == "s a t̪ʰ i".split()      # plain h after a stop = aspiration
    assert ipa_to_ours("bihan") == "b i ɦ a n".split()      # h elsewhere = ɦ
    assert ipa_to_ours("tjo") == "t̪ j o".split()


def test_parse_sentences_pairs_words():
    from g2p.compare import parse_sentences
    text = "sentence\tsentence_ipa\nघर छ\tgʰʌɾ tsʰʌ\nआज घर\tadz\n"
    rows, sents = parse_sentences(text)
    assert rows == [("घर", "sentences", ["gʱ", "ʌ", "r"]), ("छ", "sentences", ["tsʰ", "ʌ"])]
    assert [s["ok"] for s in sents] == [True, False]  # second: 2 words vs 1 IPA word, left out
    csv_rows, _ = parse_sentences("sentence,sentence_ipa\nघर छ,gʰʌɾ tsʰʌ\n")
    assert csv_rows == rows


def test_alternatives_count_as_right():
    from g2p.compare import alternatives_of, parse_sentences, score
    rows, sents = parse_sentences("sentence\tsentence_ipa\nजनता छ\tdzʌnʌta/dzʌnta tsʰʌ\n")
    alts = alternatives_of(sents)
    assert alts == {"जनता": [["dz", "ʌ", "n", "ʌ", "t̪", "a"], ["dz", "ʌ", "n", "t̪", "a"]]}
    short = {"जनता": ["dz", "ʌ", "n", "t̪", "a"], "छ": ["tsʰ", "ʌ"]}
    assert score(rows, short.__getitem__, alts)["acc"] == 1.0   # the alternative is accepted
    assert score(rows, short.__getitem__)["acc"] == 0.5         # without alternatives it is an error


def test_ipa_nasal_diphthong_notation():
    from g2p.compare import ipa_to_ours
    import unicodedata
    expected = [unicodedata.normalize("NFD", t) for t in ["bʱ", "ʌĩ", "s", "i"]]
    assert ipa_to_ours("bʱʌ̃isi") == ipa_to_ours("bʱʌĩsi") == expected


def test_dual_words_found_across_sentences():
    from g2p.compare import dual_words, parse_sentences
    text = "sentence\tsentence_ipa\nएक दिन\tek d̪in\nदिन छ\td̪inʌ tsʰʌ\n"
    _, sents = parse_sentences(text)
    assert dual_words(sents) == {"दिन": {"d̪ i n": ["एक दिन"], "d̪ i n ʌ": ["दिन छ"]}}
