"""Log words the lexicon does not know yet: a review queue, never an exception.

The phonemizer cannot tell that a pronunciation is wrong, only that a word is new. When logging is
on, every word that is not in the lexicon (and not logged before) is appended once to a TSV with the
rule pronunciation and the rule behind each schwa, for the owner's ear or the next alignment run:

  word  phonemes  rules  first_seen

Off by default. Turn it on with the environment variable DEEPHONEME_NEW_WORDS=<log path> (works for
every program that imports the phonemizer), the CLI flag --log-new, or enable() from Python.
Known words: DEEPHONEME_LEXICON=<file> (word<TAB>... per line), else the first that exists of
lexicon.dict (the deephoneme repo), bench/out/nepali_all.dict and data/lexicon.tsv (the workshop).
"""

import datetime
import logging
import os
import threading
from pathlib import Path

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
LEXICON_CANDIDATES = [ROOT / "lexicon.dict", ROOT / "bench" / "out" / "nepali_all.dict", ROOT / "data" / "lexicon.tsv"]


class NewWordLog:
    def __init__(self, path: Path, lexicon: Path | None = None):
        self.path = Path(path)
        self.lexicon = lexicon or next((p for p in LEXICON_CANDIDATES if p.exists()), None)
        self._known: set[str] | None = None
        self._lock = threading.Lock()

    def _load(self) -> set[str]:
        known: set[str] = set()
        if self.lexicon is None:
            log.warning("new-word log: no lexicon found; set DEEPHONEME_LEXICON (every word counts as new)")
        else:
            with open(self.lexicon, encoding="utf-8") as f:
                known = {line.split("\t", 1)[0].strip() for line in f}
        if self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                known |= {line.split("\t", 1)[0] for line in f}
        return known

    def see(self, word: str, analysis) -> bool:
        """Record `word` if it is new; returns True when it was written."""
        with self._lock:
            if self._known is None:
                self._known = self._load()
            if word in self._known:
                return False
            self._known.add(word)
            rules = " ".join(f"{ak.text}:{rid}{'+' if keep else '-'}"
                             for ak, (keep, rid) in zip(analysis.aksharas, analysis.decisions) if rid) or "-"
            new_file = not self.path.exists()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                if new_file:
                    f.write("word\tphonemes\trules\tfirst_seen\n")
                f.write(f"{word}\t{' '.join(analysis.phonemes)}\t{rules}\t{datetime.date.today().isoformat()}\n")
            return True


_active: NewWordLog | None = None


def enable(path: str | Path, lexicon: str | Path | None = None) -> NewWordLog:
    """Start logging unseen words to `path`."""
    global _active
    _active = NewWordLog(Path(path), Path(lexicon) if lexicon else None)
    return _active


def disable() -> None:
    global _active
    _active = None


def active() -> NewWordLog | None:
    return _active


if os.environ.get("DEEPHONEME_NEW_WORDS"):
    enable(os.environ["DEEPHONEME_NEW_WORDS"], os.environ.get("DEEPHONEME_LEXICON"))
