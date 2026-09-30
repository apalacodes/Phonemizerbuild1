"""Kokoro-82M voice: speaks an IPA string directly (onnxruntime, no kokoro package).

Model files (models/kokoro/, gitignored; or the folder in $KOKORO_DIR), ~350 MB:
  kokoro-v1.0.onnx, voices-v1.0.bin  https://github.com/thewh1teagle/kokoro-onnx/releases (model-files-v1.0)
  config.json                        https://huggingface.co/hexgrad/Kokoro-82M (vocab)
Download them with: python -m tts.kokoro_voice

Input symbols are the espeak-style IPA strings built by tts/synth.py; SYMBOL_FIXES turns
the few espeak labels that Kokoro reads differently into plain IPA.
"""

import json
import logging
import os
import sys
import urllib.request
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import onnxruntime as ort

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = Path(os.environ.get("KOKORO_DIR", ROOT / "models" / "kokoro"))
MODEL_URLS = {
    "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
    "config.json": "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/config.json",
}
SAMPLE_RATE = 24000
MAX_TOKENS = 510
HINDI_VOICES = ("hm_omega", "hm_psi", "hf_alpha", "hf_beta")

# espeak-ne labels (used in our symbols) -> IPA as Kokoro reads it.
# espeak writes च छ ज झ as palatal stops c cʰ ɟ ɟʰ; Nepali has alveolar affricates.
SYMBOL_FIXES = {"c": "ʦ", "ɟ": "ʣ"}


@dataclass
class KokoroVoice:
    session: ort.InferenceSession
    vocab: dict[str, int]
    styles: np.ndarray  # (510, 1, 256) for the chosen voice
    voice: str
    sample_rate: int = SAMPLE_RATE
    last_missing: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, model_dir: Path = MODEL_DIR, voice: str = "hm_omega") -> "KokoroVoice":
        model_dir = Path(model_dir)
        session = ort.InferenceSession(str(model_dir / "kokoro-v1.0.onnx"), providers=["CPUExecutionProvider"])
        vocab = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))["vocab"]
        styles = np.load(model_dir / "voices-v1.0.bin")[voice]
        return cls(session, vocab, styles, voice)

    @staticmethod
    def available() -> bool:
        return all((MODEL_DIR / f).exists() for f in ("kokoro-v1.0.onnx", "voices-v1.0.bin", "config.json"))

    def to_ipa(self, symbols: list[str]) -> str:
        """espeak-style symbols -> the IPA string Kokoro reads."""
        return "".join(SYMBOL_FIXES.get(ch, ch) for ch in "".join(symbols))

    def symbols_to_ids(self, symbols: list[str]) -> list[int]:
        """Kokoro token ids: 0, one id per known codepoint, 0. Unknown codepoints are dropped."""
        self.last_missing = set()
        ids = []
        for ch in self.to_ipa(symbols):
            if ch in self.vocab:
                ids.append(self.vocab[ch])
            else:
                self.last_missing.add(ch)
        if self.last_missing:
            log.warning("kokoro: dropped symbols not in vocab: %s", " ".join(sorted(self.last_missing)))
        if len(ids) > MAX_TOKENS - 2:
            log.warning("kokoro: input truncated to %d tokens", MAX_TOKENS - 2)
            ids = ids[:MAX_TOKENS - 2]
        return [0, *ids, 0]

    def synthesize(self, symbols: list[str], length_scale: float | None = None) -> tuple[np.ndarray, int]:
        """Return (float32 mono audio in [-1, 1], sample_rate). length_scale > 1 is slower."""
        ids = self.symbols_to_ids(symbols)
        speed = 1.0 / (length_scale or 1.0)
        audio = self.session.run(None, {
            "tokens": np.array([ids], dtype=np.int64),
            "style": self.styles[len(ids) - 2].astype(np.float32),
            "speed": np.array([speed], dtype=np.float32),
        })[0]
        return np.clip(audio.astype(np.float32), -1.0, 1.0), self.sample_rate


def write_wav(path: Path, audio: np.ndarray, sample_rate: int) -> None:
    """Write float audio in [-1, 1] as 16-bit mono WAV."""
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())


def download(model_dir: Path = MODEL_DIR) -> None:
    """Fetch the Kokoro model files that are missing from model_dir."""
    model_dir.mkdir(parents=True, exist_ok=True)
    for name, url in MODEL_URLS.items():
        target = model_dir / name
        if target.exists():
            print(f"have {target}")
            continue
        print(f"downloading {name} ...", flush=True)
        urllib.request.urlretrieve(url, target.with_suffix(".part"))
        target.with_suffix(".part").rename(target)
    print(f"Kokoro model ready in {model_dir}")


if __name__ == "__main__":
    download(Path(sys.argv[1]) if len(sys.argv) > 1 else MODEL_DIR)
