"""The agent over HTTP, for the website's "ask the data" box.

    POST /api/ask   {"question": "Is the Arctic warming?"}
    ->              {"answer", "answered", "checked", "model", "sources", "notes", "steps"}

answer() is the whole logic. api/ask.py (the Vercel function) and serve() (the local
development server) are thin shells around it. The model key, if any, stays on the
server; the browser never sees it.
"""

from __future__ import annotations

import json
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from .. import config
from . import harness, tools

MAX_QUESTION = 300        # characters
MAX_BODY = 4000           # bytes
PER_MINUTE = 12           # questions per visitor per minute (per server instance, best effort)
_seen: dict = {}


def _allowed(who: str, now: float | None = None) -> bool:
    now = now or time.time()
    recent = [t for t in _seen.get(who, []) if now - t < 60]
    ok = len(recent) < PER_MINUTE
    _seen[who] = recent + [now] if ok else recent
    if len(_seen) > 5000:
        _seen.clear()
    return ok


def answer(body: bytes, site: tools.Site, who: str = "", model=None) -> tuple:
    """(HTTP status, JSON-ready dict) for one request body. Never raises."""
    if len(body) > MAX_BODY:
        return 413, {"error": "That question is too long."}
    try:
        question = json.loads(body or b"{}").get("question", "")
    except (ValueError, AttributeError):
        return 400, {"error": "Send JSON like {\"question\": \"Is the Arctic warming?\"}."}
    if not isinstance(question, str) or not question.strip():
        return 400, {"error": "Ask a question."}
    if len(question) > MAX_QUESTION:
        return 413, {"error": f"Please keep the question under {MAX_QUESTION} characters."}
    if who and not _allowed(who):
        return 429, {"error": "Too many questions at once. Wait a minute and try again."}
    try:
        return 200, harness.run(question, model, site, max_steps=6).to_dict()
    except Exception as exc:                                      # a bug must not take the page down
        return 500, {"error": f"Something went wrong on our side ({type(exc).__name__})."}


def status(site: tools.Site) -> dict:
    """What the ask box should say about itself. Never includes a key."""
    try:
        label = harness.pick(None, site).label
    except harness.ModelError as exc:
        label = f"rules (no language model: {exc})"
    return {"ok": True, "model": label, "tools": tools.NAMES}


def serve(port: int = 8000) -> None:
    """Local development: the static site plus /api/ask, on one port."""
    site = tools.Site()
    root = str(config.ROOT / "web")

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=root, **k)

        def _json(self, code, obj):
            out = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("content-length", str(len(out)))
            self.send_header("cache-control", "no-store")
            self.end_headers()
            self.wfile.write(out)

        def do_GET(self):
            if self.path.split("?")[0] == "/api/ask":
                return self._json(200, status(site))
            return super().do_GET()

        def do_POST(self):
            if self.path.split("?")[0] != "/api/ask":
                return self._json(404, {"error": "Not found"})
            body = self.rfile.read(min(int(self.headers.get("content-length") or 0), MAX_BODY + 1))
            self._json(*answer(body, site, self.client_address[0]))

        def log_message(self, *a):
            pass

    print(f"Lapse is at http://localhost:{port}  (ask box: {status(site)['model']})")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
