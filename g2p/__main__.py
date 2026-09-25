"""uv run python -m g2p WORD... -> segmentation, schwa rule per akshara, phonemes."""

import sys

from . import analyze_word
from .normalize import tokenize


def main(argv: list[str]) -> None:
    for word in tokenize(" ".join(argv)):
        aks, suffixes, decisions, phonemes = analyze_word(word)
        rules = " ".join(f"{a.text}:{rid}{'+' if keep else '-'}" for a, (keep, rid) in zip(aks, decisions) if rid)
        parts = " | ".join(a.text for a in aks) + "".join(f" + {s}" for s in suffixes)
        print(f"{word}\t{parts}\t{rules}\t{' '.join(phonemes)}")


if __name__ == "__main__":
    main(sys.argv[1:])
