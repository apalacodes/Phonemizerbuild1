import pytest

from g2p.suffix import load_suffixes, split_suffixes


def test_longest_first():
    suffixes = load_suffixes()
    assert suffixes.index("भन्दा") < suffixes.index("मा")


@pytest.mark.parametrize("word, stem, suffixes", [
    ("घरमा", "घर", ["मा"]),
    ("नेपालको", "नेपाल", ["को"]),
    ("केटाहरूलाई", "केटा", ["हरू", "लाई"]),
    ("केटाहरूको", "केटा", ["हरू", "को"]),
    ("घरदेखि", "घर", ["देखि"]),
    ("साथीसँग", "साथी", ["सँग"]),
    ("यहाँसम्म", "यहाँ", ["सम्म"]),
    ("उनीभन्दा", "उनी", ["भन्दा"]),
])
def test_split(word, stem, suffixes):
    assert split_suffixes(word) == (stem, suffixes)


@pytest.mark.parametrize("word", [
    "आमा",   # stem would be 1 akshara
    "मलाई",  # stem would be 1 akshara
    "पक्का",  # का is not a whole akshara (क्का)
    "नेपाल",
])
def test_no_split(word):
    assert split_suffixes(word) == (word, [])


def test_split_logged_to_stdout(capsys):
    split_suffixes("घरमा")
    assert "suffix split: घरमा -> घर + मा" in capsys.readouterr().out


def test_no_log_without_split(capsys):
    split_suffixes("नेपाल")
    assert capsys.readouterr().out == ""
