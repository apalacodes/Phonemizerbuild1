"""deephoneme tester: type Nepali, see the phonemes and the rule behind each schwa, hear them (Kokoro-82M).

  uv run --extra app python -m deephoneme.speech.kokoro_voice   # once: download the voice (~350 MB, models/kokoro/)
  uv run --extra app streamlit run app.py

Modes: hybrid = espeak-ng's stress/length with our sounds and schwa (needs espeak-ng installed);
ours = our phonemes only; espeak = espeak-ng as-is, for comparison.
"""

import shutil
from pathlib import Path

import streamlit as st

from deephoneme import analyze_word
from deephoneme.speech import synth
from deephoneme.speech.ipa_map import word_to_ipa
from deephoneme.speech.kokoro_voice import HINDI_VOICES, MODEL_DIR, KokoroVoice

LEXICON = Path(__file__).resolve().parent / "lexicon.dict"
HAVE_ESPEAK = shutil.which("espeak-ng") is not None
MODE_LABELS = {"hybrid": "Hybrid (espeak prosody + our G2P)", "ours": "Our G2P", "espeak": "espeak-ng"}
SAMPLES = ["नेपालमा घर छ", "मेरो देशको नाम नेपाल हो", "हामी भोलि काठमाडौं जान्छौं", "आज धेरै गर्मी छ"]

st.set_page_config(page_title="deephoneme", page_icon="🗣️", layout="wide")


@st.cache_resource(show_spinner="Loading voice…")
def load_voice(name: str) -> KokoroVoice:
    return KokoroVoice.load(voice=name)


@st.cache_data(show_spinner="Loading lexicon…")
def load_lexicon() -> dict[str, str]:
    if not LEXICON.exists():
        return {}
    with open(LEXICON, encoding="utf-8") as f:
        return dict(line.rstrip("\n").split("\t", 1) for line in f)


def symbols_for(word: str, phonemes: list[str]) -> list[str]:
    """Voice symbols for one word with explicit phonemes (hybrid if espeak-ng is there, else ours)."""
    if HAVE_ESPEAK:
        return synth.hybrid_for_phonemes(word, phonemes)
    fs = synth._final_schwa(phonemes, len(phonemes))
    return list(word_to_ipa(phonemes, True, fs, synth.DEFAULT_SCHWA) + ".")


def speak(symbols: list[str], where=st) -> None:
    if voice is None:
        return
    audio, sr = voice.synthesize(symbols, length_scale=length_scale)
    where.audio(audio, sample_rate=sr)
    if voice.last_missing:
        where.caption(f"dropped (unknown to the voice): {' '.join(sorted(voice.last_missing))}")


with st.sidebar:
    st.header("deephoneme")
    speaker = st.selectbox("Kokoro voice", HINDI_VOICES)
    available = [m for m in MODE_LABELS if HAVE_ESPEAK or m == "ours"]
    modes = st.multiselect("Modes", available, default=available[:2], format_func=MODE_LABELS.get)
    length_scale = st.slider("Speed (higher = slower)", 0.5, 2.0, 1.0, 0.05)
    st.divider()
    st.write("✅ voice found" if KokoroVoice.available() else
             f"❌ voice missing: run `uv run --extra app python -m deephoneme.speech.kokoro_voice` (→ {MODEL_DIR})")
    st.write("✅ espeak-ng found" if HAVE_ESPEAK else "⚠️ espeak-ng not installed: only 'ours' mode")
    st.write(f"📖 lexicon: {len(load_lexicon()):,} words")

voice = load_voice(speaker) if KokoroVoice.available() else None
tab_speak, tab_word, tab_lab = st.tabs(["Speak", "Word", "IPA lab"])

with tab_speak:
    sample = st.selectbox("Sample", ["—"] + SAMPLES)
    text = st.text_area("Nepali text", "" if sample == "—" else sample, height=100)
    if st.button("Phonemize & speak", type="primary", disabled=not text.strip()):
        for col, mode in zip(st.columns(max(len(modes), 1)), modes):
            with col:
                st.subheader(MODE_LABELS[mode])
                display, symbols = synth.phonemes_for(text, g2p=mode)
                st.code(display, language=None)
                if voice is not None:
                    st.caption("sent to the voice")
                    st.code(voice.to_ipa(symbols), language=None)
                speak(symbols, col)

with tab_word:
    word = st.text_input("Word", "नेपालको").strip()
    if word:
        a = analyze_word(word)
        parts = " | ".join(ak.text for ak in a.aksharas) + "".join(f" + {s}" for s in a.suffixes)
        rules = " ".join(f"{ak.text}:{rid}{'+' if keep else '−'}"
                         for ak, (keep, rid) in zip(a.aksharas, a.decisions) if rid)
        st.markdown(f"aksharas `{parts}` · schwa rules `{rules or '—'}` (+ keep, − delete)")
        entry = load_lexicon().get(word)
        st.markdown(f"lexicon.dict: `{entry}`" if entry else "lexicon.dict: not listed (the rules still pronounce it)")
        c1, c2, c3 = st.columns([1, 3, 4])
        c1.markdown("**Ours**")
        c2.code(" ".join(a.phonemes), language=None)
        speak(symbols_for(word, a.phonemes), c3)
        c1, c2, c3 = st.columns([1, 3, 4])
        c1.markdown("**Try**")
        mine = c2.text_input("phonemes", " ".join(a.phonemes), key=f"try_{word}", label_visibility="collapsed")
        if mine.strip():
            speak(symbols_for(word, mine.split()), c3)
        st.caption("To make a pronunciation permanent, add `word<TAB>phonemes` to deephoneme/data/exceptions.tsv.")

with tab_lab:
    st.caption("Edit the exact symbols sent to the voice: ə light schwa, ʌ full, ˈ ˌ stress, ː long, ʰ aspiration.")
    lab_word = st.text_input("Word", "अठार", key="lab_word").strip()
    if lab_word:
        for mode in modes + ["custom"]:
            start = "" if mode == "custom" else "".join(synth.phonemes_for(lab_word, g2p=mode)[1]).rstrip(".")
            c1, c2, c3 = st.columns([1, 3, 4])
            c1.markdown(f"**{mode}**")
            edited = c2.text_input(mode, start, key=f"lab_{mode}_{lab_word}", label_visibility="collapsed")
            if edited.strip():
                speak(list(edited.strip() + "."), c3)
