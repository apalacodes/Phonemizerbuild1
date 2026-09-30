"""Split a word into stem + case/plural suffixes (data/suffixes.txt).

Longest suffix first, repeated for stacked suffixes (हरूलाई -> हरू + लाई).
A suffix is stripped only on an akshara boundary and only if the stem keeps
at least MIN_STEM_AKSHARAS aksharas. Every split is logged to stdout.
"""

import functools
import logging
import sys

from .normalize import normalize
from .paths import DATA_DIR
from .segment import segment

SUFFIXES_TXT = DATA_DIR / "suffixes.txt"
MIN_STEM_AKSHARAS = 2


class _StdoutHandler(logging.StreamHandler):
    """Writes to whatever sys.stdout is at emit time (so redirection/capture works)."""

    @property
    def stream(self):
        return sys.stdout

    @stream.setter
    def stream(self, _value):
        pass


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
if not log.handlers:
    _handler = _StdoutHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(_handler)
    log.propagate = False


@functools.cache
def load_suffixes() -> tuple[str, ...]:
    """Suffixes from data/suffixes.txt, longest first. Blank lines and # comments ignored."""
    with open(SUFFIXES_TXT, encoding="utf-8") as f:
        words = {normalize(line.strip()) for line in f if line.strip() and not line.startswith("#")}
    return tuple(sorted(words, key=len, reverse=True))


def split_suffixes(word: str) -> tuple[str, list[str]]:
    """Return (stem, suffixes in word order). The word must already be normalized."""
    stem, suffixes = word, []
    while True:
        aks = segment(stem)
        for suffix in load_suffixes():
            n = len(segment(suffix))
            if len(aks) - n < MIN_STEM_AKSHARAS:
                continue
            if "".join(a.text for a in aks[-n:]) == suffix:
                stem = "".join(a.text for a in aks[:-n])
                suffixes.insert(0, suffix)
                break
        else:
            break
    if suffixes:
        log.info("suffix split: %s -> %s + %s", word, stem, " + ".join(suffixes))
    return stem, suffixes
