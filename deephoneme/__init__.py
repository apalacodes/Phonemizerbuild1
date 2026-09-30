"""deephoneme: rule-based Nepali grapheme-to-phoneme converter.

    from deephoneme import phonemize, phonemize_word
    phonemize("नेपालमा घर छ")      # 'n e p a l m a | gʱ ʌ r | tsʰ ʌ'
    phonemize_word("समय")          # ['s', 'ʌ', 'm', 'ʌ', 'j']

The implementation lives in the g2p package (rules S0-S11, POST-1..3, owner exceptions).
"""

from g2p import analyze_word, phonemize, phonemize_word

__all__ = ["analyze_word", "phonemize", "phonemize_word"]
