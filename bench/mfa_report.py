"""Read MFA alignments and find words where the audio prefers a rival pronunciation over ours.

For every aligned word token, the phones MFA placed inside it are matched against the dictionary
entries from bench/mfa_prepare.py (ours / rival_final / rival_medial / rival_rules). A word whose
tokens mostly pick a rival is a suspect for the owner's ear. Per-rule agreement shows how often each
schwa rule's decision on the word-final akshara was confirmed by the audio; "audio-retest" is the
line for words whose earlier audio decision was put up against the rules again. Speakers are the
corpus folders (aligned/<speaker>/<utt>.TextGrid), so evidence can require several voices.

Output (bench/out/mfa/):
  suspects.tsv    word  tokens  ours  rival  rival_kind  ours_phonemes  rival_phonemes  rule  utts
                  ours_speakers  rival_speakers
  rule_agreement.tsv   rule  tokens  ours  rival  agree%
  short_schwas.tsv     word  utt  start  dur   (ours kept a final ʌ but MFA gave it minimum length)
  misaligned_slr43.tsv words the SLR43 speakers pronounced as the rival (a skim list for the owner),
                       with the owner's recordings' count alongside

uv run bench/mfa_report.py
"""

import collections
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from g2p import analyze_word  # noqa: E402
from g2p.alignment import SILENCE, read_textgrid  # noqa: E402

OUT = ROOT / "bench" / "out" / "mfa"
MIN_PHONE = 0.031  # MFA's frame shift is 10 ms; a 3-frame phone is the shortest it can place

logging.getLogger("g2p.suffix").setLevel(logging.WARNING)


def final_rule(word: str) -> str:
    """Rule that decided the last stem akshara's schwa (or '-' when it has none)."""
    d = analyze_word(word).decisions
    return d[-1][1] or "-" if d else "-"


def main() -> None:
    variants: dict[str, dict[str, str]] = collections.defaultdict(dict)  # word -> phonemes -> kind
    with open(OUT / "variants.tsv", encoding="utf-8") as f:
        next(f)
        for line in f:
            word, kind, ph, *_ = line.rstrip("\n").split("\t")
            variants[word][ph] = kind

    picks: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    utts: dict[str, list[str]] = collections.defaultdict(list)
    speakers: dict[str, dict[str, set[str]]] = collections.defaultdict(lambda: collections.defaultdict(set))
    # per corpus (owner = the owner's recordings, slr43 = OpenSLR SLR43 speakers nep_XXXX): word -> choice -> n
    by_corpus: dict[str, dict[str, collections.Counter[str]]] = collections.defaultdict(
        lambda: collections.defaultdict(collections.Counter))
    new_utts: dict[str, list[str]] = collections.defaultdict(list)
    short: list[tuple[str, str, float, float]] = []
    grids = sorted((OUT / "aligned").rglob("*.TextGrid"))
    if not grids:
        sys.exit("no alignments: run mfa train/align first (see PROGRESS.md)")
    for tg in grids:
        tiers = read_textgrid(tg)
        words = [iv for iv in tiers.get("words", []) if iv[2] not in SILENCE]
        phones = [iv for iv in tiers.get("phones", []) if iv[2] not in SILENCE]
        for start, end, word in words:
            inside = [p for p in phones if p[0] >= start - 1e-4 and p[1] <= end + 1e-4]
            ph = " ".join(p[2] for p in inside)
            kind = variants.get(word, {}).get(ph, "unmatched")
            picks[word][kind] += 1
            speakers[word]["ours" if kind == "ours" else "rival"].add(tg.parent.name)
            corpus = "slr43" if tg.parent.name.startswith("nep_") else "owner"
            by_corpus[word][corpus]["ours" if kind == "ours" else "rival"] += 1
            if kind != "ours":
                utts[word].append(tg.stem)
                if corpus == "slr43":
                    new_utts[word].append(tg.stem)
            elif inside and inside[-1][2] == "ʌ" and inside[-1][1] - inside[-1][0] < MIN_PHONE:
                short.append((word, tg.stem, inside[-1][0], inside[-1][1] - inside[-1][0]))

    ours_ph = {w: next(p for p, k in v.items() if k == "ours") for w, v in variants.items()}
    rows, by_rule = [], collections.defaultdict(collections.Counter)
    for word, c in picks.items():
        rule = "audio-retest" if "rival_rules" in variants[word].values() else final_rule(word)
        rival = sum(n for k, n in c.items() if k.startswith("rival_"))
        by_rule[rule]["tokens"] += c.total()
        by_rule[rule]["ours"] += c["ours"]
        by_rule[rule]["rival"] += rival
        if rival:
            kind, _ = max(((k, n) for k, n in c.items() if k.startswith("rival_")), key=lambda kn: kn[1])
            rival_ph = next(p for p, k in variants[word].items() if k == kind)
            rows.append((word, c.total(), c["ours"], rival, kind, ours_ph[word], rival_ph, rule,
                         " ".join(utts[word][:5]), len(speakers[word]["ours"]), len(speakers[word]["rival"])))
    rows.sort(key=lambda r: (-(r[3] / r[1]), -r[3], r[0]))

    with open(OUT / "suspects.tsv", "w", encoding="utf-8") as f:
        f.write("word\ttokens\tours\trival\trival_kind\tours_phonemes\trival_phonemes\trule\tutts"
                "\tours_speakers\trival_speakers\n")
        for r in rows:
            f.write("\t".join(map(str, r)) + "\n")
    # Skim list: words the SLR43 speakers pronounced as the rival, strongest evidence first.
    new_rows = []
    for r in rows:
        w = r[0]
        s, o = by_corpus[w]["slr43"], by_corpus[w]["owner"]
        if s["rival"]:
            new_rows.append((w, r[5], r[6], s["rival"], s.total(), f"{s['rival'] / s.total():.0%}",
                             len({u.rsplit("_", 1)[0] for u in new_utts[w]}), f"{o['rival']}/{o.total()}",
                             r[4], r[7], " ".join(new_utts[w][:4])))
    new_rows.sort(key=lambda n: (-n[3], -n[3] / n[4], n[0]))
    with open(OUT / "misaligned_slr43.tsv", "w", encoding="utf-8") as f:
        f.write("word\tours\trival\tslr43_rival\tslr43_tokens\tslr43_share\tslr43_speakers"
                "\towner_rival/tokens\trival_kind\trule\tslr43_utts\n")
        for n in new_rows:
            f.write("\t".join(map(str, n)) + "\n")
    print(f"{len(new_rows)} words where SLR43 speakers chose the rival -> misaligned_slr43.tsv")

    with open(OUT / "rule_agreement.tsv", "w", encoding="utf-8") as f:
        f.write("rule\ttokens\tours\trival\tagree%\n")
        for rule, c in sorted(by_rule.items(), key=lambda rc: -rc[1]["tokens"]):
            tested = c["ours"] + c["rival"]
            pct = f"{100 * c['ours'] / tested:.1f}" if tested else "-"
            f.write(f"{rule}\t{c['tokens']}\t{c['ours']}\t{c['rival']}\t{pct}\n")
    with open(OUT / "short_schwas.tsv", "w", encoding="utf-8") as f:
        f.write("word\tutt\tstart\tdur\n")
        for w, u, s, d in short:
            f.write(f"{w}\t{u}\t{s:.2f}\t{d:.3f}\n")

    tokens = sum(c.total() for c in picks.values())
    ours = sum(c["ours"] for c in picks.values())
    unmatched = sum(c["unmatched"] for c in picks.values())
    n_speakers = len({tg.parent.name for tg in grids})
    print(f"{len(grids)} utterances from {n_speakers} speakers, {tokens} word tokens: ours {ours} ({100 * ours / tokens:.1f}%), "
          f"rival {tokens - ours - unmatched}, unmatched {unmatched}")
    print(f"{len(rows)} suspect words -> suspects.tsv; {len(short)} minimum-length final schwas")
    print(open(OUT / "rule_agreement.tsv", encoding="utf-8").read())


if __name__ == "__main__":
    main()
