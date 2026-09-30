"""Nepali G2P playground.

Run:  uv run streamlit run app.py
Type Nepali text, see phonemes from our hybrid G2P, Wiktionary and espeak-ng, and hear them all
through the same Kokoro-82M voice (it reads IPA directly).
"""

import shutil
import subprocess
from pathlib import Path

import streamlit as st

SAMPLES = [
    "नेपालमा घर छ",
    "हामी भोलि काठमाडौँ जान्छौं",
    "मेरो देशको नाम नेपाल हो",
    "उसले पार्कमा सुन्दर फूल देख्यो",
    "आज धेरै गर्मी छ",
    'असुरक्षित ट्रेन यात्रामा रहन धेरै दुख र ठूलो रिस्क हुन्छ। "औंसीको रातमा ऐना हेर्नु अनौठो अनुभव हो।"',
]
MODE_LABELS = {
    "hybrid": "Hybrid (espeak prosody + our G2P)", "ours": "Our G2P", "espeak": "espeak-ng",
    "wiktionary": "Wiktionary IPA",
}
WIKT_DUMP = Path("bench/ref/kaikki-nepali.jsonl")

st.set_page_config(page_title="Nepali G2P", page_icon="🗣️", layout="wide")


# ---------- backends (fail gracefully while phases are still being built) ----------

def _try_import():
    errors = {}
    g2p = synth = None
    try:
        import g2p as g2p  # noqa: F811
    except Exception as e:  # noqa: BLE001
        errors["g2p"] = e
    try:
        from tts import synth as synth  # noqa: F811
    except Exception as e:  # noqa: BLE001
        errors["tts.synth"] = e
    return g2p, synth, errors


g2p, synth, import_errors = _try_import()

from tts.kokoro_voice import HINDI_VOICES, KokoroVoice  # noqa: E402

VOICE_LABELS = {
    "hm_omega": "hm_omega (Hindi male)", "hm_psi": "hm_psi (Hindi male)",
    "hf_alpha": "hf_alpha (Hindi female)", "hf_beta": "hf_beta (Hindi female)",
}


@st.cache_resource(show_spinner="Loading voice…")
def load_voice(name: str):
    return KokoroVoice.load(voice=name)


def sent_to_voice(voice, symbols: list[str]) -> str:
    """The exact IPA string the voice reads (Kokoro relabels c/ɟ as ʦ/ʣ)."""
    return voice.to_ipa(symbols)


def get_voice():
    """The sidebar's voice, or None if the Kokoro model is not downloaded."""
    return load_voice(speaker) if KokoroVoice.available() else None


def espeak_raw_wav(text: str) -> bytes | None:
    if not shutil.which("espeak-ng"):
        return None
    out = subprocess.run(["espeak-ng", "-v", "ne", "--stdout", text], capture_output=True)
    return out.stdout or None


# ---------- sidebar ----------

with st.sidebar:
    st.header("Settings")
    speaker = st.selectbox("Kokoro voice", HINDI_VOICES, format_func=lambda s: VOICE_LABELS.get(s, s),
                           help="Kokoro-82M speaks the IPA it is given.")
    modes = st.multiselect(
        "Phonemizers", ["hybrid", "ours", "espeak", "wiktionary"], default=["hybrid", "wiktionary", "espeak"],
        help="All are spoken by the same speaker so you can compare them fairly. "
             "hybrid = espeak's stress/length with our G2P's sounds and schwa. "
             "wiktionary = Wiktionary's IPA where it has the word (others marked *).",
    )
    length_scale = st.slider("Speed (length scale, higher = slower)", 0.5, 2.0, 1.0, 0.05)
    raw_espeak = st.checkbox("Also play espeak-ng's own voice", value=False)
    show_words = st.checkbox("Per-word comparison table", value=True)

    st.divider()
    st.caption("Backend status")
    for name in ["g2p", "tts.synth"]:
        if name in import_errors:
            st.error(f"{name}: not ready ({type(import_errors[name]).__name__})")
        else:
            st.success(f"{name}: ok")
    st.write("✅ Kokoro model found" if KokoroVoice.available() else "❌ Kokoro model missing (see tts/kokoro_voice.py)")
    st.write("✅ espeak-ng found" if shutil.which("espeak-ng") else "❌ espeak-ng not installed")
    st.write("✅ Wiktionary dump found" if WIKT_DUMP.exists()
             else "❌ Wiktionary dump missing (run uv run bench/wiktionary.py)")


# ---------- main ----------

st.title("Nepali G2P playground")
tab_text, tab_bench, tab_audio, tab_review, tab_words, tab_lab = st.tabs(
    ["Text", "Benchmark", "Audio check", "Review", "Wiktionary words", "IPA lab"])

with tab_text:
    sample = st.selectbox("Try a sample", ["—"] + SAMPLES)
    text = st.text_area(
        "Nepali text", value="" if sample == "—" else sample, height=100,
        placeholder="यहाँ नेपाली लेख्नुहोस्…",
    )

    if st.button("Phonemize & speak", type="primary", disabled=not text.strip()):
        if "tts.synth" in import_errors:
            st.error(f"tts/synth.py failed to import: {import_errors['tts.synth']}")
            st.stop()

        voice = get_voice()

        cols = st.columns(max(len(modes), 1))
        for col, mode in zip(cols, modes):
            with col:
                st.subheader(MODE_LABELS.get(mode, mode))
                try:
                    display, symbols = synth.phonemes_for(
                        text, g2p=mode)
                except Exception as e:  # noqa: BLE001
                    st.error(f"Phonemizer failed: {e}")
                    continue
                st.caption("G2P output")
                st.code(display, language=None)

                if voice is None:
                    st.warning("Voice not available.")
                    continue
                st.caption("Sent to the voice (exactly)")
                st.code(sent_to_voice(voice, symbols), language=None)
                try:
                    audio, sr = voice.synthesize(symbols, length_scale=length_scale)
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
                        row[mode] = synth.phonemes_for(
                            w, g2p=mode)[0].rstrip(" .,?!")
                    except Exception as e:  # noqa: BLE001
                        row[mode] = f"error: {e}"
                fixed = "hybrid" if "hybrid" in modes else "ours"
                if {fixed, "espeak"} <= set(modes):
                    row["differ"] = "⚠️" if row[fixed].replace(" ", "") != row["espeak"].replace(" ", "") else ""
                rows.append(row)
            st.dataframe(rows, width="stretch", hide_index=True)
            st.caption("espeak strings are shown in its own IPA; 'differ' is a rough flag — listen to confirm.")


# ---------- Wiktionary word browser ----------

@st.cache_data(show_spinner="Comparing our G2P with Wiktionary…")
def wikt_rows() -> list[dict]:
    from g2p.reference import wiktionary_entries
    return wiktionary_entries()


with tab_words:
    if not WIKT_DUMP.exists():
        st.info("Wiktionary dump not downloaded yet: run `uv run bench/wiktionary.py` once.")
    else:
        rows = wikt_rows()
        c1, c2, c3 = st.columns([2, 2, 2])
        split = c1.radio("Split", ["all", "dev", "test"], horizontal=True,
                         help="test = 279 hand-edited entries, held out from rule tuning")
        only_diff = c2.checkbox("Only where ours ≠ Wiktionary", value=True)
        query = c3.text_input("Search word", "")
        shown = [
            r for r in rows
            if (split == "all" or r["split"] == split)
            and (not only_diff or not r["match"])
            and (not query or query in r["word"])
        ]
        pool = [r for r in rows if split == "all" or r["split"] == split]
        st.caption(f"{len(shown)} words shown · ours matches Wiktionary on "
                   f"{sum(r['match'] for r in pool) / max(len(pool), 1):.1%} of the {split} split")
        st.dataframe([{k: r[k] for k in ("word", "split", "wiktionary", "wikt_phonemes", "ours")} for r in shown],
                     width="stretch", hide_index=True, height=260)

        word = st.selectbox("Word to hear", [r["word"] for r in shown], index=0 if shown else None)
        if word:
            a = g2p.analyze_word(word)
            rules = " ".join(f"{ak.text}:{rid}{'+' if keep else '-'}"
                             for ak, (keep, rid) in zip(a.aksharas, a.decisions) if rid)
            parts = " | ".join(ak.text for ak in a.aksharas) + "".join(f" + {x}" for x in a.suffixes)
            st.markdown(f"**{word}** — aksharas `{parts}` — schwa rules `{rules or '—'}` — ours `{' '.join(a.phonemes)}`")
            voice = get_voice()
            for col, mode in zip(st.columns(3), ["hybrid", "wiktionary", "espeak"]):
                with col:
                    st.subheader(MODE_LABELS[mode])
                    display, symbols = synth.phonemes_for(
                        word, g2p=mode)
                    st.code(display.rstrip(" ."), language=None)
                    if voice is not None:
                        audio, sr = voice.synthesize(symbols, length_scale=length_scale)
                        st.audio(audio, sample_rate=sr)


# ---------- IPA lab: edit the exact symbols sent to the voice ----------

with tab_lab:
    st.caption("Type a word, then edit any row's IPA and press Enter to hear it: ə (light schwa), "
               "ʌ (full), ˈ primary / ˌ secondary stress, ː long, ʰ aspiration, ̃ nasal.")
    lab_word = st.text_input("Word", "अठार", key="lab_word")
    if lab_word.strip():
        lab_voice = get_voice()
        for mode in ["ours", "hybrid", "wiktionary", "espeak", "custom"]:
            if mode == "custom":
                start = ""
            else:
                start = "".join(synth.phonemes_for(lab_word, g2p=mode)[1]).rstrip(".")
            c1, c2, c3 = st.columns([1, 3, 3])
            c1.markdown(f"**{mode}**")
            edited = c2.text_input(mode, start, key=f"lab_{mode}_{lab_word}",
                                   label_visibility="collapsed")
            if edited.strip() and lab_voice is not None:
                audio, sr = lab_voice.synthesize(list(edited.strip() + "."), length_scale=length_scale)
                c3.audio(audio, sample_rate=sr)
                if lab_voice.last_missing:
                    c3.caption(f"dropped (unknown to the voice): {' '.join(sorted(lab_voice.last_missing))}")


# ---------- review: correct lexicon words that disagree with Wiktionary ----------

with tab_review:
    from g2p.reference import load_decisions, load_lexicon, record_decision, review_candidates

    review_voice = get_voice()

    def play(label: str, phonemes: str, word: str, key: str) -> None:
        """One row: phonemes (our inventory), the exact string sent to the voice, audio."""
        c1, c2, c3, c4 = st.columns([2, 3, 3, 3])
        c1.markdown(f"**{label}**")
        c2.code(phonemes or "—", language=None)
        if not phonemes.strip():
            return
        symbols = synth.hybrid_for_phonemes(word, phonemes.split())
        if review_voice is not None:
            c3.code(sent_to_voice(review_voice, symbols), language=None)
            audio, sr = review_voice.synthesize(symbols, length_scale=length_scale)
            c4.audio(audio, sample_rate=sr)

    if not load_lexicon():
        st.info("Lexicon not built yet: run `uv run bench/build_lexicon.py`.")
    else:
        decided = load_decisions()
        candidates = review_candidates(50)
        st.caption(
            f"{len(decided)} reviewed so far · next {len(candidates)} train headwords where our G2P "
            "disagrees with Wiktionary (schwa cases first). Wiktionary is a reference, not the truth: "
            "listen and choose. Choices other than 'keep ours' go to data/exceptions.tsv; afterwards run "
            "`uv run bench/build_lexicon.py` and `uv run bench/build_benchmark.py`."
        )
        st.dataframe([{k: c[k] for k in ("word", "kind", "ours", "wiktionary")} for c in candidates],
                     width="stretch", hide_index=True, height=240)
        if candidates:
            word = st.selectbox("Word to review", [c["word"] for c in candidates], key="review_word")
            c = next(x for x in candidates if x["word"] == word)
            st.markdown(f"**{word}** — {c['kind']} — Wiktionary IPA `{c['wiktionary_ipa']}`")
            h1, h2, h3, h4 = st.columns([2, 3, 3, 3])
            h2.caption("phonemes (our inventory)")
            h3.caption("sent to the voice (exactly)")
            play("Ours", c["ours"], word, "ours")
            play("Wiktionary", c["wiktionary"], word, "wikt")
            custom = st.text_input("Your version (phonemes, space-separated)", c["ours"], key=f"custom_{word}")
            play("Yours", custom, word, "custom")
            b1, b2, b3 = st.columns(3)
            if b1.button("✔ Keep ours", key=f"keep_{word}"):
                record_decision(word, "ours", c["ours"].split())
                st.rerun()
            if b2.button("✔ Use Wiktionary", key=f"wikt_{word}"):
                record_decision(word, "wiktionary", c["wiktionary"].split())
                st.rerun()
            if b3.button("✔ Save mine", key=f"mine_{word}", disabled=not custom.strip()):
                record_decision(word, "custom", custom.split())
                st.rerun()
        st.divider()
        st.subheader("Look up any lexicon word")
        look = st.text_input("Word", "", key="lexicon_lookup")
        if look.strip():
            row = load_lexicon().get(look.strip())
            if row is None:
                st.warning("Not in data/lexicon.tsv.")
            else:
                st.markdown(f"source **{row['source']}** · lemma {row['lemma']} · split **{row['split']}** · "
                            f"Wiktionary `{row['wiktionary'] or '—'}` · agrees {row['agrees'] or '—'}")
                st.caption("phonemes column (our G2P)")
                st.code(row["phonemes"], language=None)
                st.caption("hybrid column = exactly what the voice is given")
                st.code(row["hybrid"], language=None)
                if review_voice is not None:
                    audio, sr = review_voice.synthesize(list(row["hybrid"] + "."), length_scale=length_scale)
                    st.audio(audio, sample_rate=sr)


# ---------- audio check: words where the recordings (MFA) preferred a rival schwa form ----------

with tab_audio:
    from g2p.alignment import load_suspects, word_clips
    from g2p.reference import load_decisions, record_decision

    suspects = load_suspects()
    if not suspects:
        st.info("No alignments yet: run MFA (see CLAUDE.md, 'Forced alignment') and "
                "`uv run bench/mfa_report.py`.")
    else:
        decided = load_decisions()
        # 'audio' decisions came from an earlier alignment; a new run may contradict them, so they stay listed
        todo = [r for r in suspects if decided.get(r["word"], ("audio",))[0] == "audio"]
        c1, c2 = st.columns([3, 2])
        min_share = c2.slider("Show words where the rival won at least this share of tokens", 0.0, 1.0, 0.5, 0.05)
        shown = [r for r in todo if r["rival"] / r["tokens"] >= min_share]
        c1.caption(
            f"{len(shown)} words to check ({len(suspects) - len(todo)} decided). The aligner is evidence, "
            "not truth: it favours shorter forms. Listen to the recording, then choose. "
            "'Rival' and 'mine' go to data/exceptions.tsv; afterwards run `uv run bench/mfa_prepare.py` "
            "and `uv run bench/build_words.py` to rebuild the dictionaries."
        )
        st.dataframe([{"word": r["word"], "tokens": r["tokens"], "chose ours": r["ours"], "chose rival": r["rival"],
                       "ours": r["ours_phonemes"], "rival": r["rival_phonemes"], "rule": r["rule"]}
                      for r in shown], width="stretch", hide_index=True, height=240)
        if shown:
            word = st.selectbox("Word to check", [r["word"] for r in shown], key="audio_word")
            r = next(x for x in shown if x["word"] == word)
            st.markdown(f"**{word}** · rule `{r['rule']}` · rival kind `{r['rival_kind']}` · "
                        f"recordings chose ours {r['ours']}× and the rival {r['rival']}×"
                        + (f" · speakers: ours {r['ours_speakers']}, rival {r['rival_speakers']}"
                           if r.get("rival_speakers") else ""))

            st.subheader("The speaker (your recordings)")
            for utt in r["utts"][:3]:
                for k, clip in enumerate(word_clips(word, utt)):
                    a1, a2, a3 = st.columns([2, 3, 4])
                    a1.markdown(f"`{utt}`")
                    a2.audio(clip["wav"], format="audio/wav")
                    a3.audio(clip["context_wav"], format="audio/wav")
                    a3.caption("with neighbouring words · MFA phones: " +
                               " ".join(f"{p}({int(d * 1000)}ms)" for p, d in clip["phones"]))

            st.subheader("Synthetic (Kokoro)")
            voice = get_voice()

            def say(label: str, phonemes: str) -> None:
                b1, b2, b3 = st.columns([2, 3, 4])
                b1.markdown(f"**{label}**")
                b2.code(phonemes or "—", language=None)
                if voice is not None and phonemes.strip():
                    audio, sr = voice.synthesize(synth.hybrid_for_phonemes(word, phonemes.split()),
                                                 length_scale=length_scale)
                    b3.audio(audio, sample_rate=sr)

            say("Ours", r["ours_phonemes"])
            say("Rival", r["rival_phonemes"])
            custom = st.text_input("Your version (phonemes, space-separated)", r["ours_phonemes"],
                                   key=f"audio_custom_{word}")
            say("Yours", custom)

            d1, d2, d3 = st.columns(3)
            if d1.button("✔ Ours is right", key=f"audio_ours_{word}"):
                record_decision(word, "ours", r["ours_phonemes"].split())
                st.rerun()
            if d2.button("✔ Rival is right", key=f"audio_rival_{word}"):
                record_decision(word, "rival", r["rival_phonemes"].split())
                st.rerun()
            if d3.button("✔ Save mine", key=f"audio_mine_{word}", disabled=not custom.strip()):
                record_decision(word, "custom", custom.split())
                st.rerun()


# ---------- benchmark: listen to the trusted words, in batches, next to the real recordings ----------

with tab_bench:
    import io
    import random
    import wave

    import numpy as np

    from g2p.alignment import utterance_index, word_clips
    from g2p.reference import load_benchmark_rows, record_decision

    BASIS_LABELS = {"owner": "owner (by ear)", "audio": "audio (accepted from alignment)", "agree": "agree (= Wiktionary)"}

    def wav_to_float(data: bytes) -> np.ndarray:
        with wave.open(io.BytesIO(data)) as w:
            return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768

    rows = load_benchmark_rows()
    if not rows:
        st.info("No benchmark yet: run `uv run bench/build_benchmark.py`.")
    else:
        index = utterance_index()
        f1, f2, f3, f4 = st.columns([3, 2, 2, 2])
        bases = f1.multiselect("Basis", list(BASIS_LABELS), default=["audio"], format_func=BASIS_LABELS.get)
        only_heard = f2.checkbox("Only words in my recordings", value=True)
        query = f3.text_input("Search", "", key="bench_query")
        seed = f4.number_input("Shuffle seed", 0, 9999, 0, help="change it for a different order")
        pool = [r for r in rows if r["basis"] in bases and (not only_heard or r["word"] in index)
                and (not query or query in r["word"])]
        random.Random(seed).shuffle(pool)
        st.caption(f"{len(pool)} words · 'hybrid' is exactly what the voice is given")

        # --- batch listening ---
        st.subheader("Listen to a batch")
        b1, b2, b3 = st.columns([2, 2, 3])
        size = b1.number_input("Words per batch", 5, 50, 10)
        n_batches = max(1, -(-len(pool) // size))
        batch_no = b2.number_input(f"Batch (of {n_batches})", 1, n_batches, 1)
        with_real = b3.checkbox("After each word, play the real recording", value=True)
        batch = pool[(batch_no - 1) * size: batch_no * size]
        st.dataframe([{"#": i + 1, "word": r["word"], "phonemes": r["phonemes"], "basis": r["basis"],
                       "in recordings": len(index.get(r["word"], []))} for i, r in enumerate(batch)],
                     width="stretch", hide_index=True)
        if batch and st.button("▶ Build batch audio", type="primary", disabled=get_voice() is None):
            voice = get_voice()
            gap = np.zeros(int(0.5 * 24000), dtype=np.float32)
            parts = []
            for r in batch:
                audio, sr = voice.synthesize(list(r["hybrid"] + "."), length_scale=length_scale)
                parts += [audio, gap[: len(gap) // 2]]
                utts = index.get(r["word"], [])
                clips = word_clips(r["word"], utts[0]) if with_real and utts else []
                if clips:
                    parts += [wav_to_float(clips[0]["wav"])]
                parts.append(gap)
            st.audio(np.concatenate(parts), sample_rate=24000)
            st.caption("Order: " + " → ".join(r["word"] for r in batch) +
                       (" (each: voice, then the recording)" if with_real else ""))

        # --- one word, closely ---
        st.subheader("One word")
        word = st.selectbox("Word", [r["word"] for r in batch] + [r["word"] for r in pool if r not in batch],
                            key="bench_word") if pool else None
        if word:
            r = next(x for x in pool if x["word"] == word)
            a = g2p.analyze_word(word)
            rules = " ".join(f"{ak.text}:{rid}{'+' if keep else '-'}"
                             for ak, (keep, rid) in zip(a.aksharas, a.decisions) if rid)
            st.markdown(f"**{word}** · basis **{r['basis']}** · rules `{rules or '—'}` · "
                        f"espeak agrees: {r['espeak_agrees']} · Wiktionary `{r['wiktionary'] or '—'}`")
            voice = get_voice()
            c1, c2, c3 = st.columns([2, 3, 4])
            c1.markdown("**Voice**")
            c2.code(f"{r['phonemes']}\n{r['hybrid']}", language=None)
            if voice is not None:
                audio, sr = voice.synthesize(list(r["hybrid"] + "."), length_scale=length_scale)
                c3.audio(audio, sample_rate=sr)
            for utt in index.get(word, [])[:3]:
                for clip in word_clips(word, utt)[:1]:
                    c1, c2, c3 = st.columns([2, 3, 4])
                    c1.markdown(f"`{utt}`")
                    c2.audio(clip["wav"], format="audio/wav")
                    c3.audio(clip["context_wav"], format="audio/wav")
                    c3.caption("with neighbouring words · MFA phones: " +
                               " ".join(f"{p}({int(d * 1000)}ms)" for p, d in clip["phones"]))
            fix = st.text_input("Sounds wrong? Your version (phonemes, space-separated)", r["phonemes"],
                                key=f"bench_fix_{word}")
            if fix.strip() != r["phonemes"]:
                c1, c2, c3 = st.columns([2, 3, 4])
                c1.markdown("**Yours**")
                symbols = synth.hybrid_for_phonemes(word, fix.split())
                c2.code("".join(symbols), language=None)
                if voice is not None:
                    audio, sr = voice.synthesize(symbols, length_scale=length_scale)
                    c3.audio(audio, sample_rate=sr)
                if st.button("✔ Save mine (exceptions.tsv)", key=f"bench_save_{word}"):
                    record_decision(word, "custom", fix.split())
                    st.success(f"Saved {word} = {fix}. Rebuild: uv run bench/build_benchmark.py")
