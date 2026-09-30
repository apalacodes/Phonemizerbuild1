"""deephoneme self-test.  uv run test.py [--quick]

1. rule samples: one word per rule, with the expected phonemes
2. exceptions: every entry in deephoneme/data/exceptions.tsv is honoured
3. benchmark: every verified word in benchmark.tsv comes out as recorded (PER 0)
4. lexicon: the phonemizer still produces every entry of lexicon.dict (--quick: a 20,000-word sample)
"""

import random
import sys
from pathlib import Path

from deephoneme import phonemize_word
from deephoneme.compare import load_benchmark, score
from deephoneme.schwa import load_exceptions

HERE = Path(__file__).resolve().parent

RULE_SAMPLES = [  # word, expected phonemes, rule
    ("कमल", "k ʌ m ʌ l", "S11"),
    ("समय", "s ʌ m ʌ j", "S0 (owner, audio check)"),
    ("कस्तो", "k ʌ s t̪ o", "S1"),
    ("झन्", "dzʱ ʌ n", "halanta"),
    ("गुरुङ", "g u r u ŋ", "S4"),
    ("रङ", "r ʌ ŋ", "S4"),
    ("माघ", "m a gʱ", "S11"),
    ("कारण", "k a r ʌ n", "S11"),
    ("साथ", "s a t̪ʰ", "S11"),
    ("देश", "d̪ e s", "S11"),
    ("मानव", "m a n ʌ w", "S11, POST-2"),
    ("अन्त", "ʌ n t̪ ʌ", "S10"),
    ("सम्बन्ध", "s ʌ m b ʌ n d̪ʱ ʌ", "S10"),
    ("हुन्छ", "ɦ u n tsʰ ʌ", "S7"),
    ("भएर", "bʱ ʌ e r ʌ", "S7"),
    ("रहन", "r ʌ ɦ ʌ n ʌ", "S7 (infinitive)"),
    ("छन्", "tsʰ ʌ n", "halanta"),
    ("यस", "j ʌ s", "S5"),
    ("जुन", "dz u n", "S5"),
    ("अब", "ʌ b ʌ", "S6"),
    ("आज", "a dz ʌ", "S6"),
    ("सुख", "s u kʰ ʌ", "S0"),
    ("दुख", "d̪ u kʰ ʌ", "S0"),
    ("पार्क", "p a r k", "S9"),
    ("मार्च", "m a r ts", "S9"),
    ("मञ्च", "m ʌ n ts", "S9"),
    ("घरमा", "gʱ ʌ r m a", "suffix split + S11"),
    ("नेपालको", "n e p a l k o", "suffix split + S11"),
    ("संगीत", "s ʌ ŋ g i t̪", "POST-1, S11"),
    ("महँगो", "m ʌ ɦ ʌ̃ g o", "S1, POST-3"),
    ("छ", "tsʰ ʌ", "S2"),
    ("म", "m ʌ", "S2"),
    ("ज्ञान", "g j a n", "mapping, S11"),
]


def _check(label: str, cases) -> int:
    fails = [(w, exp, got) for w, exp in cases if (got := " ".join(phonemize_word(w))) != exp]
    for w, exp, got in fails[:20]:
        print(f"  FAIL {w}: expected '{exp}', got '{got}'")
    print(f"{'ok  ' if not fails else 'FAIL'} {label}: {len(fails)} of {len(cases)} wrong")
    return len(fails)


def test_rule_samples():
    assert _check("rule samples", [(w, exp) for w, exp, _ in RULE_SAMPLES]) == 0


def test_exceptions():
    assert _check("exceptions", [(w, " ".join(p)) for w, p in load_exceptions().items()]) == 0


def test_benchmark():
    r = score(load_benchmark(HERE / "benchmark.tsv"), phonemize_word)
    for word, _basis, got, exp, _kind, _d in r["errors"][:20]:
        print(f"  FAIL {word}: expected '{exp}', got '{got}'")
    print(f"{'ok  ' if not r['errors'] else 'FAIL'} benchmark: {len(r['errors'])} of "
          f"{sum(b[1] for b in r['per_basis'].values())} wrong, PER {r['per']:.1%}")
    assert not r["errors"]


def test_lexicon(quick: bool = True):
    with open(HERE / "lexicon.dict", encoding="utf-8") as f:
        entries = [line.rstrip("\n").split("\t") for line in f]
    if quick:
        entries = random.Random(0).sample(entries, min(20000, len(entries)))
    assert _check("lexicon.dict" + (" (sample)" if quick else ""), entries) == 0


if __name__ == "__main__":
    import logging
    logging.disable(logging.WARNING)
    failed = 0
    for test in (test_rule_samples, test_exceptions, test_benchmark, lambda: test_lexicon(quick="--quick" in sys.argv)):
        try:
            test()
        except AssertionError:
            failed += 1
    sys.exit(1 if failed else 0)
