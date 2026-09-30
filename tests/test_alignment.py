"""MFA output readers (g2p/alignment.py)."""

import io
import wave

from g2p.alignment import cut_wav, read_textgrid

TEXTGRID = '''File type = "ooTextFile"
Object class = "TextGrid"
xmin = 0
xmax = 1.0
tiers? <exists>
size = 2
item []:
    item [1]:
        class = "IntervalTier"
        name = "words"
        xmin = 0
        xmax = 1.0
        intervals: size = 2
        intervals [1]:
            xmin = 0
            xmax = 0.4
            text = ""
        intervals [2]:
            xmin = 0.4
            xmax = 1.0
            text = "सय"
    item [2]:
        class = "IntervalTier"
        name = "phones"
        xmin = 0
        xmax = 1.0
        intervals: size = 2
        intervals [1]:
            xmin = 0.4
            xmax = 0.7
            text = "s"
        intervals [2]:
            xmin = 0.7
            xmax = 1.0
            text = "ʌ"
'''


def test_read_textgrid(tmp_path):
    p = tmp_path / "u.TextGrid"
    p.write_text(TEXTGRID, encoding="utf-8")
    tiers = read_textgrid(p)
    assert tiers["words"] == [(0.0, 0.4, ""), (0.4, 1.0, "सय")]
    assert tiers["phones"] == [(0.4, 0.7, "s"), (0.7, 1.0, "ʌ")]


def test_cut_wav(tmp_path):
    p = tmp_path / "u.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(1000)
        w.writeframes(bytes(2000))  # 1 s
    with wave.open(io.BytesIO(cut_wav(p, 0.25, 0.75))) as w:
        assert w.getnframes() == 500
    with wave.open(io.BytesIO(cut_wav(p, -0.1, 2.0))) as w:  # clamped to the file
        assert w.getnframes() == 1000
