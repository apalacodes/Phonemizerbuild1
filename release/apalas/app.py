"""Apala's phonemizer: compare it with espeak-ng, and benchmark it against your own ground truth.

  uv run --extra app streamlit run app.py

1. Compare with espeak-ng: paste Nepali text; per word our phonemes vs espeak-ng's, where they differ
   and how, and both spoken by the same Kokoro voice so you hear the difference.
2. Benchmark: score our phonemizer (and espeak-ng) against ground-truth pronunciations: the bundled
   ground_truth.tsv (words) or ground_truth_sentences.tsv (sentences with IPA), or a file you upload
   (columns word, phonemes, optional basis; or sentence, sentence_ipa).
   PER = phoneme edit distance / ground-truth phonemes.
"""

import csv
import io
import logging
import shutil
from pathlib import Path

import streamlit as st

from deephoneme import analyze_word, phonemize_word
from deephoneme.compare import (
    alternatives_of, diff_kind, edit_distance, espeak_ipa, espeak_to_ours, load_sentences, parse_sentences, score,
)
from deephoneme.normalize import tokenize
from deephoneme.speech import synth
from deephoneme.speech.kokoro_voice import HINDI_VOICES, MODEL_DIR, KokoroVoice

GROUND_TRUTH = Path(__file__).resolve().parent / "ground_truth.tsv"
SENTENCES = Path(__file__).resolve().parent / "ground_truth_sentences.tsv"
HAVE_ESPEAK = shutil.which("espeak-ng") is not None

logging.disable(logging.WARNING)
st.set_page_config(page_title="Apala's phonemizer", page_icon="🗣️", layout="wide")


@st.cache_resource(show_spinner="Loading voice…")
def load_voice(name: str) -> KokoroVoice:
    return KokoroVoice.load(voice=name)


def espeak_phonemes(word: str) -> list[str]:
    return espeak_to_ours(espeak_ipa(word))


def parse_ground_truth(data: bytes) -> list[tuple[str, str, list[str]]]:
    """(word, basis, phonemes) from a TSV/CSV with a header containing word and phonemes (basis optional)."""
    text = data.decode("utf-8-sig")
    dialect = "excel-tab" if "\t" in text.splitlines()[0] else "excel"
    rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
    if not rows or not {"word", "phonemes"} <= set(rows[0]):
        raise ValueError("the file needs a header row with the columns: word, phonemes (and optionally basis)")
    return [(r["word"].strip(), (r.get("basis") or "yours").strip(), r["phonemes"].split())
            for r in rows if r.get("word") and r.get("phonemes")]


@st.cache_data(show_spinner="Scoring…")
def run_benchmark(rows: tuple, with_espeak: bool, alts: tuple = ()) -> dict:
    bench = [(w, b, list(p)) for w, b, p in rows]
    alternatives = {w: [list(v) for v in vs] for w, vs in alts}
    out = {"ours": score(bench, phonemize_word, alternatives)}
    if with_espeak:
        out["espeak-ng"] = score(bench, espeak_phonemes, alternatives)
    return out


def play(symbols: list[str], where) -> None:
    if voice is not None:
        audio, sr = voice.synthesize(symbols, length_scale=speed)
        where.audio(audio, sample_rate=sr)


def ours_symbols(word: str, phonemes: list[str]) -> list[str]:
    """Voice symbols for our phonemes: hybrid (espeak-ng stress/length) when espeak-ng is installed."""
    if HAVE_ESPEAK:
        return synth.hybrid_for_phonemes(word, phonemes)
    return synth.phonemes_for(word, g2p="ours")[1]


with st.sidebar:
    st.header("Apala's phonemizer")
    speaker = st.selectbox("Kokoro voice", HINDI_VOICES)
    speed = st.slider("Speed (higher = slower)", 0.5, 2.0, 1.0, 0.05)
    st.divider()
    st.write("✅ Kokoro voice found" if KokoroVoice.available() else
             f"❌ voice missing: `uv run --extra app python -m deephoneme.speech.kokoro_voice` (→ {MODEL_DIR})")
    st.write("✅ espeak-ng found" if HAVE_ESPEAK else "❌ espeak-ng missing: `sudo apt install espeak-ng`")

voice = load_voice(speaker) if KokoroVoice.available() else None
tab_compare, tab_bench = st.tabs(["1 · Compare with espeak-ng", "2 · Benchmark against ground truth"])

with tab_compare:
    text = st.text_area("Nepali text", height=110, placeholder="यहाँ वाक्य लेख्नुहोस्…")
    if text.strip() and not HAVE_ESPEAK:
        st.error("espeak-ng is not installed, so there is nothing to compare with: `sudo apt install espeak-ng`.")
    elif text.strip():
        words = tokenize(text)
        rows = [(w, analyze_word(w), espeak_phonemes(w)) for w in words]
        differ = [(w, a, e) for w, a, e in rows if a.phonemes != e]
        ours_len = sum(len(a.phonemes) for _, a, _ in rows)
        dist = sum(edit_distance(e, a.phonemes) for _, a, e in rows)
        m1, m2 = st.columns(2)
        m1.metric("words where they differ", f"{len(differ)} of {len(rows)}")
        m2.metric("phoneme differences (espeak-ng vs ours)", f"{dist / max(ours_len, 1):.1%}",
                  help="edit distance between the two outputs / our phonemes. A disagreement, not an error rate: "
                       "use the Benchmark tab to know who is right.")

        c1, c2 = st.columns(2)
        for col, mode, label in [(c1, "hybrid", "ours (hybrid)"), (c2, "espeak", "espeak-ng")]:
            display, symbols = synth.phonemes_for(text, g2p=mode)
            col.subheader(label)
            col.code(display, language=None)
            play(symbols, col)

        st.subheader("Word by word")
        widths = [2, 3, 3, 3, 3, 3, 3]
        for col, label in zip(st.columns(widths), ["word", "schwa rules", "ours", "espeak-ng", "difference",
                                                     "hear ours", "hear espeak-ng"]):
            col.caption(label)
        for w, a, e in rows:
            c = st.columns(widths)
            c[0].markdown(f"**{w}**")
            c[1].write(" ".join(f"{ak.text}:{rid}{'+' if keep else '−'}"
                                for ak, (keep, rid) in zip(a.aksharas, a.decisions) if rid) or "—")
            c[2].code(" ".join(a.phonemes), language=None)
            c[3].code(" ".join(e), language=None)
            c[4].write("same" if a.phonemes == e else diff_kind(e, a.phonemes))
            play(ours_symbols(w, a.phonemes), c[5])
            if a.phonemes != e:
                play(synth.phonemes_for(w, g2p="espeak")[1], c[6])

with tab_bench:
    source = st.radio("Ground truth", ["ground_truth.tsv (words, bundled)",
                                       "ground_truth_sentences.tsv (sentences, bundled)", "upload my own file"],
                      horizontal=True)
    rows, sentences = None, None
    if source.startswith("upload"):
        up = st.file_uploader("TSV or CSV with a header: word, phonemes (space-separated), optional basis — "
                              "or sentences: sentence, sentence_ipa (IPA words separated by spaces)",
                              type=["tsv", "csv", "txt"])
        if up is not None:
            try:
                text = up.getvalue().decode("utf-8-sig")
                if "sentence_ipa" in text.splitlines()[0]:
                    rows, sentences = parse_sentences(text)
                else:
                    rows = parse_ground_truth(up.getvalue())
            except (ValueError, UnicodeDecodeError, IndexError) as err:
                st.error(str(err))
    elif source.startswith("ground_truth_sentences"):
        rows, sentences = load_sentences(SENTENCES)
    else:
        rows = parse_ground_truth(GROUND_TRUTH.read_bytes())
    if sentences is not None:
        skipped = [s for s in sentences if not s["ok"]]
        st.caption(f"{len(sentences)} sentences, {len(rows)} words. The IPA is converted to our symbols "
                   "(notation only: ɾ→r, dʰ→d̪ʱ, plain t d→t̪ d̪, h after a stop→ʰ) before scoring."
                   + (f" {len(skipped)} sentence(s) left out: their word count differs from the IPA's."
                      if skipped else ""))
    with_espeak = st.checkbox("Also score espeak-ng (about 20 s per 3,000 words)", value=HAVE_ESPEAK,
                              disabled=not HAVE_ESPEAK)

    if rows:
        alts = alternatives_of(sentences) if sentences is not None else {}
        r = run_benchmark(tuple((w, b, tuple(p)) for w, b, p in rows), with_espeak,
                          tuple((w, tuple(tuple(v) for v in vs)) for w, vs in alts.items()))
        systems = list(r)
        st.caption(f"{len(rows):,} ground-truth words. PER = phoneme edit distance / ground-truth phonemes"
                   + (" (for a word with alternatives: the closest accepted one)." if alts else "."))
        cols = st.columns(2 * len(systems))
        for i, s in enumerate(systems):
            cols[2 * i].metric(f"PER {s}", f"{r[s]['per']:.1%}")
            cols[2 * i + 1].metric(f"word accuracy {s}", f"{r[s]['acc']:.1%}")

        def right(out: str, accepted: list[list[str]]) -> bool:
            return out.split() in accepted

        def dist(out: str, accepted: list[list[str]]) -> int:
            return min(edit_distance(out.split(), a) for a in accepted)

        if alts:
            st.subheader("Flagged: words with an alternative pronunciation")
            st.caption("The ground truth accepts more than one form (written a/b in the file). A system is right "
                       "with either, but ours only ever produces one: a shortcoming to keep in mind.")
            st.dataframe([{"word": w, "accepted pronunciations": "  /  ".join(" ".join(v) for v in vs),
                           "ours": " ".join(phonemize_word(w)),
                           "ours never says": "  /  ".join(" ".join(v) for v in vs if v != phonemize_word(w))}
                          for w, vs in alts.items()], width="stretch", hide_index=True)

        if sentences is not None:
            st.subheader("Per sentence")
            ours_of = {w: " ".join(phonemize_word(w)) for w, _, _ in rows}
            esp_of = {w: " ".join(espeak_phonemes(w)) for w, _, _ in rows} if "espeak-ng" in systems else {}
            table, usable = [], [s for s in sentences if s["ok"]]
            for i, s in enumerate(usable, 1):
                pairs = list(zip(s["words"], s["variants"]))
                n = sum(len(v[0]) for _, v in pairs)
                row = {"#": i, "sentence": s["sentence"],
                       "words wrong (ours)": sum(not right(ours_of[w], v) for w, v in pairs),
                       "PER ours": f"{sum(dist(ours_of[w], v) for w, v in pairs) / n:.1%}"}
                if esp_of:
                    row["words wrong (espeak-ng)"] = sum(not right(esp_of[w], v) for w, v in pairs)
                    row["PER espeak-ng"] = f"{sum(dist(esp_of[w], v) for w, v in pairs) / n:.1%}"
                table.append(row)
            st.dataframe(table, width="stretch", hide_index=True, height=260)
            pick = st.selectbox("Look at a sentence", range(len(usable)),
                                format_func=lambda i: f"{i + 1}. {usable[i]['sentence']}")
            s = usable[pick]
            # the ground truth is heard as written; where it lists alternatives, the last one (its own form)
            listen = [("ground truth", [ours_symbols(w, v[-1]) for w, v in zip(s["words"], s["variants"])]),
                      ("ours", [ours_symbols(w, ours_of[w].split()) for w in s["words"]])]
            if HAVE_ESPEAK:
                listen.append(("espeak-ng", [synth.phonemes_for(s["sentence"], g2p="espeak")[1]]))
            for col, (label, parts) in zip(st.columns(len(listen)), listen):
                col.markdown(f"**{label}**")
                play([ch for part in parts for ch in "".join(part).rstrip(".") + " "][:-1] + ["."], col)
            widths = [2, 3, 3, 3, 3]
            for col, label in zip(st.columns(widths), ["word", "ground truth (IPA → ours)", "ours", "espeak-ng", ""]):
                col.caption(label)
            for w, ipa, v in zip(s["words"], s["ipa_words"], s["variants"]):
                c = st.columns(widths)
                c[0].markdown(f"**{w}**" + ("  ⚑" if len(v) > 1 else ""))
                c[1].code(f"{ipa}\n" + "  /  ".join(" ".join(x) for x in v), language=None)
                c[2].code(ours_of[w] + ("  ✓" if right(ours_of[w], v) else "  ✗"), language=None)
                if esp_of:
                    c[3].code(esp_of[w] + ("  ✓" if right(esp_of[w], v) else "  ✗"), language=None)
                if not right(ours_of[w], v):
                    c[4].write(diff_kind(ours_of[w].split(), v[0]))
                elif len(v) > 1:
                    c[4].write("⚑ alternative pronunciation exists")

        bases = sorted(r["ours"]["per_basis"])
        st.subheader("Per basis")
        st.dataframe([{"basis": b, "words": r["ours"]["per_basis"][b][1],
                       **{f"PER {s}": f"{r[s]['per_basis'][b][2] / max(r[s]['per_basis'][b][3], 1):.1%}" for s in systems},
                       **{f"accuracy {s}": f"{r[s]['per_basis'][b][0] / r[s]['per_basis'][b][1]:.1%}" for s in systems}}
                      for b in bases], width="stretch", hide_index=True)

        st.subheader("Errors by kind")
        kinds = sorted({k for s in systems for k in r[s]["kinds"]})
        st.dataframe([{"kind": k, **{s: r[s]["kinds"][k] for s in systems}} for k in kinds],
                     width="stretch", hide_index=True)

        st.subheader("Errors")
        who = st.radio("System", systems, horizontal=True)
        errors = r[who]["errors"]
        f1, f2 = st.columns(2)
        kind = f1.selectbox("Kind", ["all"] + kinds)
        query = f2.text_input("Search word", "")
        shown = [e for e in errors if (kind == "all" or e[4] == kind) and (not query or query in e[0])]
        table = [{"word": e[0], "basis": e[1], who: e[2], "ground truth": e[3], "kind": e[4], "edits": e[5]}
                 for e in shown]
        st.dataframe(table, width="stretch", hide_index=True, height=260)
        if table:
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=list(table[0]), dialect="excel-tab")
            writer.writeheader()
            writer.writerows(table)
            st.download_button("Download these errors (TSV)", buf.getvalue(), file_name=f"errors_{who}.tsv")
            word = st.selectbox("Hear a word", [e[0] for e in shown])
            e = next(x for x in shown if x[0] == word)
            for label, phonemes, symbols in [
                ("ground truth", e[3], ours_symbols(word, e[3].split())),
                (who, e[2], synth.phonemes_for(word, g2p="espeak")[1] if who == "espeak-ng"
                 else ours_symbols(word, e[2].split())),
            ]:
                c1, c2, c3 = st.columns([2, 3, 4])
                c1.markdown(f"**{label}**")
                c2.code(phonemes, language=None)
                play(symbols, c3)
        else:
            st.success(f"{who} matches every ground-truth word.")
