"""Check the generated phonemes by ear, and benchmark them against espeak-ng.

  uv run streamlit run check_phoneme.py

Sentence: paste Nepali text, see how each word is broken down (aksharas, schwa rule per akshara,
our phonemes vs espeak-ng's), hear the sentence and every word alone. Words that are in the
benchmark show its reference, and the sentence gets a PER for both systems on those words.
Benchmark: word accuracy and PER of espeak-ng and our phonemizer on data/benchmark.tsv
(same numbers as bench/evaluate.py), per basis, by error kind, and every error to listen to.
PER = phoneme edit distance / reference phonemes.
"""

import logging
from pathlib import Path

import streamlit as st

from g2p import analyze_word, phonemize_word
from g2p.compare import edit_distance, espeak_ipa, espeak_to_ours, load_benchmark, score
from g2p.normalize import tokenize
from tts import synth
from tts.kokoro_voice import HINDI_VOICES, KokoroVoice

BENCHMARK = Path(__file__).resolve().parent / "data" / "benchmark.tsv"
MODES = {"hybrid": "hybrid (espeak stress/length + our sounds)", "ours": "ours only", "espeak": "espeak-ng"}
BASIS = {"owner": "by ear", "audio": "from alignment", "agree": "= Wiktionary"}

logging.disable(logging.WARNING)
st.set_page_config(page_title="Check phonemes", page_icon="🗣️", layout="wide")


@st.cache_resource(show_spinner="Loading voice…")
def load_voice(name: str) -> KokoroVoice:
    return KokoroVoice.load(voice=name)


def espeak_phonemes(word: str) -> list[str]:
    return espeak_to_ours(espeak_ipa(word))


@st.cache_data(show_spinner="Scoring espeak-ng and our phonemizer on the benchmark (~20 s)…")
def run_benchmark(mtime: float) -> dict:
    bench = load_benchmark(BENCHMARK)
    return {"n": len(bench), "espeak": score(bench, espeak_phonemes), "ours": score(bench, phonemize_word)}


@st.cache_data
def benchmark_ref(mtime: float) -> dict[str, tuple[str, list[str]]]:
    return {w: (basis, ref) for w, basis, ref in load_benchmark(BENCHMARK)}


def play(symbols: list[str], where) -> None:
    audio, sr = voice.synthesize(symbols, length_scale=speed)
    where.audio(audio, sample_rate=sr)


with st.sidebar:
    mode = st.radio("Phonemes given to the voice", list(MODES), format_func=MODES.get)
    speaker = st.selectbox("Kokoro voice", HINDI_VOICES)
    speed = st.slider("Speed (higher = slower)", 0.5, 2.0, 1.0, 0.05)

st.title("Check phonemes")
if not KokoroVoice.available():
    st.error("Kokoro model missing: `uv run python -m tts.kokoro_voice`")
    st.stop()
voice = load_voice(speaker)
mtime = BENCHMARK.stat().st_mtime
refs = benchmark_ref(mtime)
tab_sentence, tab_bench = st.tabs(["Sentence", "Benchmark: espeak vs ours"])

with tab_sentence:
    text = st.text_area("Nepali text", height=120, placeholder="यहाँ लामो वाक्य लेख्नुहोस्…")
    if text.strip():
        display, symbols = synth.phonemes_for(text, g2p=mode)
        play(symbols, st)
        st.caption("phonemes")
        st.code(display, language=None)
        st.caption("sent to the voice (exactly)")
        st.code(voice.to_ipa(symbols), language=None)

        words = tokenize(text)
        dist = {"ours": 0, "espeak": 0}
        ref_len = covered = 0
        rows = []
        for word in words:
            a = analyze_word(word)
            esp = espeak_phonemes(word)
            basis, ref = refs.get(word, (None, None))
            if ref:
                covered += 1
                ref_len += len(ref)
                dist["ours"] += edit_distance(a.phonemes, ref)
                dist["espeak"] += edit_distance(esp, ref)
            rows.append((word, a, esp, basis, ref))

        if covered:
            m1, m2, m3 = st.columns(3)
            m1.metric("words in the benchmark", f"{covered} of {len(words)}")
            m2.metric("PER ours", f"{dist['ours'] / ref_len:.1%}")
            m3.metric("PER espeak-ng", f"{dist['espeak'] / ref_len:.1%}")
        else:
            st.caption("None of these words is in the benchmark, so there is no reference to score against.")
        st.caption(f"ours and espeak-ng disagree on {sum(a.phonemes != e for _, a, e, _, _ in rows)} "
                   f"of {len(rows)} words")

        st.subheader("Word by word")
        widths = [2, 3, 3, 3, 3, 3, 4]
        for col, label in zip(st.columns(widths), ["word", "aksharas", "schwa rules", "ours", "espeak-ng",
                                                     "benchmark", "alone"]):
            col.caption(label)
        for word, a, esp, basis, ref in rows:
            c = st.columns(widths)
            c[0].markdown(f"**{word}**")
            c[1].write(" | ".join(ak.text for ak in a.aksharas) + "".join(f" + {s}" for s in a.suffixes))
            c[2].write(" ".join(f"{ak.text}:{rid}{'+' if keep else '−'}"
                                for ak, (keep, rid) in zip(a.aksharas, a.decisions) if rid) or "—")
            c[3].code(" ".join(a.phonemes), language=None)
            c[4].code(" ".join(esp) + ("" if esp == a.phonemes else "  ≠"), language=None)
            if ref:
                marks = f"ours {'✓' if a.phonemes == ref else '✗'} · espeak {'✓' if esp == ref else '✗'}"
                c[5].code(" ".join(ref), language=None)
                c[5].caption(f"{BASIS[basis]} · {marks}")
            else:
                c[5].write("—")
            play(synth.phonemes_for(word, g2p=mode)[1], c[6])
        st.caption("A word sounds wrong? Fix it in app.py (Review / Benchmark tab) or add it to data/exceptions.tsv.")

with tab_bench:
    r = run_benchmark(mtime)
    esp, ours = r["espeak"], r["ours"]
    st.caption(f"data/benchmark.tsv: {r['n']:,} trusted words. PER = phoneme edit distance / reference phonemes. "
               "Our rules produced or were corrected to these words, so for ours this is a regression check; "
               "for espeak-ng it is a real benchmark.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("PER ours", f"{ours['per']:.1%}")
    c2.metric("PER espeak-ng", f"{esp['per']:.1%}")
    c3.metric("word accuracy ours", f"{ours['acc']:.1%}")
    c4.metric("word accuracy espeak-ng", f"{esp['acc']:.1%}")

    st.subheader("Per basis")
    st.dataframe([{
        "basis": f"{b} ({BASIS[b]})", "words": esp["per_basis"][b][1],
        "PER ours": f"{ours['per_basis'][b][2] / ours['per_basis'][b][3]:.1%}",
        "PER espeak-ng": f"{esp['per_basis'][b][2] / esp['per_basis'][b][3]:.1%}",
        "accuracy ours": f"{ours['per_basis'][b][0] / ours['per_basis'][b][1]:.1%}",
        "accuracy espeak-ng": f"{esp['per_basis'][b][0] / esp['per_basis'][b][1]:.1%}",
    } for b in BASIS if b in esp["per_basis"]], width="stretch", hide_index=True)

    st.subheader("Errors by kind")
    kinds = sorted(set(esp["kinds"]) | set(ours["kinds"]), key=lambda k: -esp["kinds"][k])
    st.dataframe([{"kind": k, "espeak-ng": esp["kinds"][k], "ours": ours["kinds"][k]} for k in kinds],
                 width="stretch", hide_index=True)
    st.caption(f"speed: ours {ours['wps']:,.0f} words/s · espeak-ng {esp['wps']:,.0f} words/s")

    st.subheader("Errors")
    who = st.radio("System", ["espeak-ng", "ours"], horizontal=True)
    errors = esp["errors"] if who == "espeak-ng" else ours["errors"]
    f1, f2 = st.columns(2)
    kind = f1.selectbox("Kind", ["all"] + kinds)
    query = f2.text_input("Search word", "")
    shown = [e for e in errors if (kind == "all" or e[4] == kind) and (not query or query in e[0])]
    st.dataframe([{"word": e[0], "basis": e[1], who: e[2], "benchmark": e[3], "kind": e[4], "edits": e[5]}
                  for e in shown], width="stretch", hide_index=True, height=280)
    if shown:
        word = st.selectbox("Hear a word", [e[0] for e in shown])
        e = next(x for x in shown if x[0] == word)
        for label, symbols in [("benchmark", synth.hybrid_for_phonemes(word, e[3].split())),
                               (who, synth.phonemes_for(word, g2p="espeak")[1] if who == "espeak-ng"
                                else synth.hybrid_for_phonemes(word, e[2].split()))]:
            c1, c2, c3 = st.columns([2, 3, 4])
            c1.markdown(f"**{label}**")
            c2.code(e[3] if label == "benchmark" else e[2], language=None)
            play(symbols, c3)
    elif who == "ours":
        st.success("Our phonemizer reproduces every benchmark word.")
