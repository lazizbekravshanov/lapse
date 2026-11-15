"""Vercel server function behind the website's "ask the data" box.

It runs the same harness as `python -m lapse agent`: read-only tools over the published
NASA results, and a check that rejects any number no tool produced. Set GEMINI_API_KEY
(or another key, see pipeline/lapse/agent/models.py) in the Vercel project to have a
model write the sentences. Without a key it answers by rule.
"""

import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pipeline"))

import json  # noqa: E402

from lapse.agent import tools, web  # noqa: E402

SITE = tools.Site()


class handler(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        out = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(out)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(out)

    def do_GET(self):
        self._json(200, web.status(SITE))

    def do_POST(self):
        body = self.rfile.read(min(int(self.headers.get("content-length") or 0), web.MAX_BODY + 1))
        who = (self.headers.get("x-forwarded-for") or "").split(",")[0].strip()
        self._json(*web.answer(body, SITE, who))
