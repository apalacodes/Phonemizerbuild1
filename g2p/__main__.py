"""Command line (installed as `deephoneme`).

  deephoneme "नेपालमा घर छ"           -> n e p a l m a | gʱ ʌ r | tsʰ ʌ
  producer | deephoneme               one line of text in, one line of phonemes out (flushed per line)
  deephoneme --explain नेपालको        -> segmentation, schwa rule per akshara, phonemes
  deephoneme --serve 8000             HTTP: GET /phonemize?text=... or POST the text -> JSON
  deephoneme --log-new "..."          also append words the lexicon lacks to new_words.tsv (--log-file FILE)

uv run python -m g2p WORD...        (same as --explain)
"""

import argparse
import json
import logging
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import analyze_word, newwords, phonemize, phonemize_word
from .normalize import tokenize


def explain(text: str) -> None:
    for word in tokenize(text):
        aks, suffixes, decisions, phonemes, _ = analyze_word(word)
        rules = " ".join(f"{a.text}:{rid}{'+' if keep else '-'}" for a, (keep, rid) in zip(aks, decisions) if rid)
        parts = " | ".join(a.text for a in aks) + "".join(f" + {s}" for s in suffixes)
        print(f"{word}\t{parts}\t{rules}\t{' '.join(phonemes)}")


def main(argv: list[str]) -> None:
    """python -m g2p WORD...: per-word analysis."""
    explain(" ".join(argv))


def to_json(text: str) -> dict:
    words = tokenize(text)
    return {"text": text, "phonemes": phonemize(text),
            "words": [{"word": w, "phonemes": phonemize_word(w)} for w in words]}


class _Handler(BaseHTTPRequestHandler):
    def _reply(self, text: str | None) -> None:
        if text is None:
            self.send_error(400, "give text: GET /phonemize?text=... or POST the text as the body")
            return
        body = json.dumps(to_json(text), ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        self._reply(parse_qs(url.query).get("text", [None])[0] if url.path == "/phonemize" else None)

    def do_POST(self) -> None:  # noqa: N802
        n = int(self.headers.get("Content-Length", 0))
        self._reply(self.rfile.read(n).decode("utf-8") if n else None)

    def log_message(self, *args) -> None:
        pass


def serve(port: int, host: str = "127.0.0.1") -> None:
    print(f"deephoneme serving on http://{host}:{port}/phonemize?text=...", flush=True)
    ThreadingHTTPServer((host, port), _Handler).serve_forever()


def cli() -> None:
    ap = argparse.ArgumentParser(prog="deephoneme", description="Rule-based Nepali grapheme-to-phoneme converter.")
    ap.add_argument("text", nargs="*", help="Nepali text (default: read lines from stdin)")
    ap.add_argument("--explain", action="store_true", help="show segmentation and the schwa rule per akshara")
    ap.add_argument("--serve", type=int, metavar="PORT", help="run an HTTP server on localhost:PORT")
    ap.add_argument("--log-new", action="store_true",
                    help="append words the lexicon does not know to --log-file: a review queue")
    ap.add_argument("--log-file", default="new_words.tsv", metavar="FILE", help="default: new_words.tsv")
    args = ap.parse_args()
    if args.log_new:
        newwords.enable(args.log_file)
    if not args.explain:  # diagnostics (suffix splits, skipped characters) only with --explain
        logging.disable(logging.WARNING)
    if args.serve:
        serve(args.serve)
        return
    lines = [" ".join(args.text)] if args.text else (line.rstrip("\n") for line in sys.stdin)
    for line in lines:
        if args.explain:
            explain(line)
        else:
            print(phonemize(line), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
