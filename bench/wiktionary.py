"""Compare espeak-ng and our G2P against Wiktionary's Nepali IPA.

Wiktionary's Nepali IPA comes from {{ne-IPA}}, generated from spelling by Module:ne-pron
unless an editor passes a respelling ({{ne-IPA|...}}). It is a reference, not ground truth.

Split (never tune rules on the test split):
  dev   words whose IPA is generated from spelling  -> use to find rule patterns
  test  words with editor-supplied {{ne-IPA|...}}   -> held out, report only

Inputs (downloaded once, cached in bench/ref/):
  kaikki-nepali.jsonl   https://kaikki.org/dictionary/Nepali/kaikki.org-dictionary-Nepali.jsonl
  ne_ipa_args.tsv       word -> {{ne-IPA}} arguments, fetched from the Wiktionary API
Outputs:
  bench/out/wiktionary_compare.tsv   one row per word

uv run bench/wiktionary.py      # espeak vs ours, dev and test
"""

import collections
import json
import logging
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import editdistance  # noqa: E402

from g2p import phonemize_word  # noqa: E402
from g2p.reference import (  # noqa: E402
    ARGS_TSV, KAIKKI, KAIKKI_URL, REF_DIR, diff_kind, espeak_ipa, espeak_to_ours, load_wiktionary, wikt_to_ours,
)

OUT = ROOT / "bench" / "out"
API = "https://en.wiktionary.org/w/api.php"
USER_AGENT = "nepali-g2p-bench/0.1 (research; one-off comparison)"

logging.getLogger("g2p.suffix").setLevel(logging.WARNING)


# ---------- data ----------

def fetch_template_args(words: list[str]) -> dict[str, str]:
    """word -> '|'-joined {{ne-IPA}} args ('' = auto-generated). Cached in ARGS_TSV."""
    cached = {}
    if ARGS_TSV.exists():
        for line in ARGS_TSV.read_text(encoding="utf-8").splitlines():
            w, _, a = line.partition("\t")
            cached[w] = a
    todo = [w for w in words if w not in cached]
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        q = urllib.parse.urlencode({
            "action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
            "format": "json", "formatversion": "2", "titles": "|".join(batch),
        })
        data = _api_get(q)
        for page in data["query"]["pages"]:
            text = page.get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("content", "")
            nepali = text[text.find("==Nepali=="):] if "==Nepali==" in text else ""
            nepali = re.split(r"\n==[^=]", nepali[2:], maxsplit=1)[0]
            args = re.findall(r"\{\{ne-IPA\|?([^}]*)\}\}", nepali)
            cached[unicodedata.normalize("NFC", page["title"])] = " ; ".join(a for a in args if a)
        _save_args(cached)
        time.sleep(2)
    _save_args(cached)
    return cached


def _save_args(cached: dict[str, str]) -> None:
    with open(ARGS_TSV, "w", encoding="utf-8") as f:
        for w in sorted(cached):
            f.write(f"{w}\t{cached[w]}\n")


def _api_get(query: str) -> dict:
    """GET the Wiktionary API, backing off on HTTP 429."""
    req = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": USER_AGENT})
    for attempt in range(6):
        try:
            return json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            wait = int(e.headers.get("Retry-After") or 0) or 10 * 2 ** attempt
            print(f"  rate limited, waiting {wait}s")
            time.sleep(wait)
    raise RuntimeError("Wiktionary API still rate-limiting; rerun later (progress is cached)")


# ---------- comparison ----------

def best_ref(system: list[str], refs: list[list[str]]) -> tuple[list[str], int]:
    return min(((r, editdistance.eval(system, r)) for r in refs), key=lambda x: x[1])


def score(words, refs, system) -> tuple[float, float, collections.Counter]:
    """(exact match rate, PER, diff kinds) of system(word) against the closest variant."""
    kinds, dist, length = collections.Counter(), 0, 0
    for w in words:
        out = system(w)
        ref, d = best_ref(out, refs[w])
        kinds[diff_kind(out, ref)] += 1
        dist += d
        length += len(ref)
    return kinds["match"] / len(words), dist / length, kinds


def main() -> None:
    if not KAIKKI.exists():
        REF_DIR.mkdir(parents=True, exist_ok=True)
        print(f"downloading {KAIKKI_URL}")
        urllib.request.urlretrieve(KAIKKI_URL, KAIKKI)
        load_wiktionary.cache_clear()
    wikt = load_wiktionary()
    words = sorted(wikt)
    try:
        template_args = fetch_template_args(words)
    except Exception as e:  # noqa: BLE001
        print(f"(could not fetch {{{{ne-IPA}}}} args: {e}; no held-out split)")
        template_args = {}
    refs = {w: [wikt_to_ours(v) for v in wikt[w]] for w in words}
    split = {
        "dev": [w for w in words if not template_args.get(w)],
        "test": [w for w in words if template_args.get(w)],
    }
    print(f"{len(words)} words: dev {len(split['dev'])} (generated IPA), "
          f"test {len(split['test'])} (hand-edited, held out)")

    espeak = {w: espeak_to_ours(espeak_ipa(w)) for w in words}
    systems = {
        "espeak": espeak.__getitem__,
        "ours": phonemize_word,
    }

    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    for part in ("dev", "test"):
        if not split[part]:
            continue
        print(f"\n[{part}] {len(split[part])} words{'':20}" + "".join(f"{name:>14}" for name in systems))
        for name, fn in systems.items():
            results[part, name] = score(split[part], refs, fn)
        print(f"{'  word exact match (any variant)':45}"
              + "".join(f"{results[part, n][0]:>14.1%}" for n in systems))
        print(f"{'  PER vs closest variant':45}" + "".join(f"{results[part, n][1]:>14.1%}" for n in systems))
        kinds = sorted({k for n in systems for k in results[part, n][2]} - {"match"})
        for k in kinds:
            print(f"    {k:41}" + "".join(f"{results[part, n][2][k]:>14}" for n in systems))

    with open(OUT / "wiktionary_compare.tsv", "w", encoding="utf-8") as f:
        f.write("word\tsplit\twiktionary\twikt_ours\tne_ipa_args\tespeak\tespeak_diff\tours\tours_diff\n")
        for w in words:
            row = [w, "test" if template_args.get(w) else "dev", " / ".join(wikt[w]),
                   " / ".join(" ".join(r) for r in refs[w]), template_args.get(w, "?")]
            for fn in systems.values():
                out = fn(w)
                row += [" ".join(out), diff_kind(out, best_ref(out, refs[w])[0])]
            f.write("\t".join(row) + "\n")
    print(f"\nper-word table: {OUT / 'wiktionary_compare.tsv'}")


if __name__ == "__main__":
    main()
