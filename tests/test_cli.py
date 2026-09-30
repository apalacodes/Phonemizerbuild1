"""deephoneme command line and HTTP server (g2p/__main__.py)."""

import json
import logging
import threading
import unicodedata
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import deephoneme
from g2p.__main__ import _Handler, to_json


def test_facade_matches_g2p():
    assert deephoneme.phonemize("नेपालमा घर छ") == "n e p a l m a | gʱ ʌ r | tsʰ ʌ"


def test_log_new_does_not_swallow_the_text(tmp_path, monkeypatch, capsys):
    from g2p import newwords
    from g2p.__main__ import cli
    log = tmp_path / "new.tsv"
    monkeypatch.setattr("sys.argv", ["deephoneme", "--log-new", "--log-file", str(log), "झिल्मिलाउँदोपना घर"])
    try:
        cli()
    finally:
        newwords.disable()
        logging.disable(logging.NOTSET)  # cli() silences diagnostics globally
    out = unicodedata.normalize("NFD", capsys.readouterr().out.strip())
    assert out == unicodedata.normalize("NFD", "dzʱ i l m i l a ũ d̪ o p ʌ n a | gʱ ʌ r")
    assert "झिल्मिलाउँदोपना" in log.read_text(encoding="utf-8")


def test_to_json():
    out = to_json("घर छ")
    assert out["phonemes"] == "gʱ ʌ r | tsʰ ʌ"
    assert out["words"] == [{"word": "घर", "phonemes": ["gʱ", "ʌ", "r"]},
                            {"word": "छ", "phonemes": ["tsʰ", "ʌ"]}]


def test_http_get_and_post():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urllib.request.urlopen(f"{base}/phonemize?text={urllib.parse.quote('कमल')}") as r:
            assert json.load(r)["phonemes"] == "k ʌ m ʌ l"
        req = urllib.request.Request(f"{base}/phonemize", data="समय".encode(), method="POST")
        with urllib.request.urlopen(req) as r:
            assert json.load(r)["phonemes"] == "s ʌ m ʌ j"
    finally:
        server.shutdown()
