import unicodedata

from g2p.normalize import normalize, tokenize


def test_strips_zwj_zwnj():
    assert normalize("र्‍या") == "र्या"
    assert normalize("क‌ख") == "कख"


def test_nukta_precomposed_and_decomposed_unify():
    assert normalize("ड़") == "ड"
    assert normalize("ड़") == "ड"
    assert normalize("ज़") == normalize("ज़") == "ज"


def test_output_is_nfc():
    decomposed = unicodedata.normalize("NFD", "नेपाल")
    assert normalize(decomposed) == unicodedata.normalize("NFC", "नेपाल")


def test_devanagari_digits():
    assert normalize("२०८१") == "2081"


def test_avagraha_removed():
    assert normalize("होऽ") == "हो"


def test_tokenize_splits_on_punctuation():
    assert tokenize("नेपाल, घर। छ?") == ["नेपाल", "घर", "छ"]
    assert tokenize("  म  ॥ ") == ["म"]
