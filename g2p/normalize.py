"""Text normalization: NFC, ZWJ/ZWNJ removal, nukta unification, digits, punctuation."""

import re
import unicodedata

NUKTA = "़"
AVAGRAHA = "ऽ"
ZERO_WIDTH = {"‌": None, "‍": None, "﻿": None}  # ZWNJ, ZWJ, BOM

# Precomposed nukta letters (U+0958-U+095F). Nepali does not contrast them, so
# every nukta form collapses to its base letter.
NUKTA_LETTERS = {
    "क़": "क", "ख़": "ख", "ग़": "ग", "ज़": "ज",
    "ड़": "ड", "ढ़": "ढ", "फ़": "फ", "य़": "य",
}

DEVANAGARI_DIGITS = {chr(0x0966 + i): str(i) for i in range(10)}

_PUNCT = re.compile(r"[।॥,.?!;:\"'“”‘’()\[\]{}<>«»…\-–—/|]+")


def normalize(text: str) -> str:
    """Return text in NFC with zero-width chars, nukta and avagraha removed, digits in ASCII."""
    text = unicodedata.normalize("NFC", text)
    text = text.translate(str.maketrans(ZERO_WIDTH))
    text = text.translate(str.maketrans(NUKTA_LETTERS))
    text = text.replace(NUKTA, "").replace(AVAGRAHA, "")
    text = text.translate(str.maketrans(DEVANAGARI_DIGITS))
    return unicodedata.normalize("NFC", text)


def tokenize(text: str) -> list[str]:
    """Normalize text and split it into words; punctuation acts as a separator."""
    return _PUNCT.sub(" ", normalize(text)).split()
