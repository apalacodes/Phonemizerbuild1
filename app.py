"""Nepali G2P playground.

Run:  uv run streamlit run app.py
Type Nepali text, see phonemes from our G2P and espeak-ng, and hear both through the Piper voice.
"""

import shutil
import subprocess
from pathlib import Path

import streamlit as st

MODEL = Path("models/piper/ne_NP-google-medium.onnx")
SAMPLES = [
    "नेपालमा घर छ",
    "हामी भोलि काठमाडौँ जान्छौं",
    "मेरो देशको नाम नेपाल हो",
    "उसले पार्कमा सुन्दर फूल देख्यो",
    "आज धेरै गर्मी छ",
]

st.set_page_config(page_title="Nepali G2P", page_icon="🗣️", layout="wide")


# ---------- backends (fail gracefully while phases are still being built) ----------

def _try_import():
    errors = {}
    g2p = synth = voice_mod = None
    try:
        import g2p as g2p  # noqa: F811
    except Exception as e:  # noqa: BLE001
        errors["g2p"] = e
    try:
        from tts import synth as synth  # noqa: F811
    except Exception as e:  # noqa: BLE001
        errors["tts.synth"] = e
    try:
        from tts import piper_voice as voice_mod  # noqa: F811
    except Exception as e:  # noqa: BLE001
        errors["tts.piper_voice"] = e
    return g2p, synth, voice_mod, errors


g2p, synth, voice_mod, import_errors = _try_import()


@st.cache_resource(show_spinner="Loading Piper voice…")
def load_voice():
    return voice_mod.PiperVoice.load(MODEL)


def espeak_raw_wav(text: str) -> bytes | None:
    if not shutil.which("espeak-ng"):
        return None
    out = subprocess.run(["espeak-ng", "-v", "ne", "--stdout", text], capture_output=True)
    return out.stdout or None


# ---------- sidebar ----------

with st.sidebar:
    st.header("Settings")
    modes = st.multiselect(
        "Phonemizers", ["ours", "espeak"], default=["ours", "espeak"],
        help="Both are spoken by your Piper voice so you can compare them fairly.",
    )
    length_scale = st.slider("Speed (length scale, higher = slower)", 0.5, 2.0, 1.0, 0.05)
    noise_scale = st.slider("Noise scale", 0.0, 1.0, 0.667, 0.01)
    noise_w = st.slider("Noise W", 0.0, 1.0, 0.8, 0.01)
    raw_espeak = st.checkbox("Also play espeak-ng's own voice", value=False)
    show_words = st.checkbox("Per-word comparison table", value=True)

    st.divider()
    st.caption("Backend status")
    for name in ["g2p", "tts.synth", "tts.piper_voice"]:
        if name in import_errors:
            st.error(f"{name}: not ready ({type(import_errors[name]).__name__})")
        else:
            st.success(f"{name}: ok")
    st.write("✅ model found" if MODEL.exists() else f"❌ missing {MODEL}")
    st.write("✅ espeak-ng found" if shutil.which("espeak-ng") else "❌ espeak-ng not installed")


# ---------- main ----------

st.title("Nepali G2P playground")

sample = st.selectbox("Try a sample", ["—"] + SAMPLES)
text = st.text_area(
    "Nepali text", value="" if sample == "—" else sample, height=100,
    placeholder="यहाँ नेपाली लेख्नुहोस्…",
)

if st.button("Phonemize & speak", type="primary", disabled=not text.strip()):
    if "tts.synth" in import_errors:
        st.error("tts/synth.py isn't built yet — finish phase 7 first.")
        st.stop()

    voice = None
    if "tts.piper_voice" not in import_errors and MODEL.exists():
        voice = load_voice()

    cols = st.columns(max(len(modes), 1))
    for col, mode in zip(cols, modes):
        with col:
            st.subheader("Our G2P" if mode == "ours" else "espeak-ng")
            try:
                display, symbols = synth.phonemes_for(text, g2p=mode)
            except Exception as e:  # noqa: BLE001
                st.error(f"Phonemizer failed: {e}")
                continue
            st.code(display, language=None)

            if voice is None:
                st.warning("Piper voice not available.")
                continue
            try:
                audio, sr = voice.synthesize(
                    symbols, length_scale=length_scale,
                    noise_scale=noise_scale, noise_w=noise_w,
                )
                st.audio(audio, sample_rate=sr)
            except Exception as e:  # noqa: BLE001
                st.error(f"Synthesis failed: {e}")
            missing = getattr(voice, "last_missing", None)
            if missing:
                st.caption(f"⚠️ Symbols not in the voice's map (dropped): {' '.join(sorted(missing))}")

    if raw_espeak:
        st.subheader("espeak-ng's own voice (baseline)")
        wav = espeak_raw_wav(text)
        st.audio(wav, format="audio/wav") if wav else st.warning("espeak-ng not available.")

    if show_words and "g2p" not in import_errors:
        st.subheader("Per word")
        rows = []
        for w in text.split():
            row = {"word": w}
            for mode in modes:
                try:
                    row[mode] = synth.phonemes_for(w, g2p=mode)[0]
                except Exception as e:  # noqa: BLE001
                    row[mode] = f"error: {e}"
            if {"ours", "espeak"} <= set(modes):
                row["differ"] = "⚠️" if row["ours"].replace(" ", "") != row["espeak"].replace(" ", "") else ""
            rows.append(row)
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption("espeak strings are shown in its own IPA; 'differ' is a rough flag — listen to confirm.")