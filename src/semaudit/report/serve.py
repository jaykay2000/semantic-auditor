"""`semaudit serve`: the Release Story page on 127.0.0.1 with working owner-decision buttons.

The same page as the static one, plus forms that record decisions through semaudit.decide.memory (the same calls
as `semaudit decide` / `semaudit decide-release`), recorded as the name given with --by. Local only; after each
decision the static page beside the review is rebuilt too.
"""

from __future__ import annotations

import html
import mimetypes
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from semaudit.decide.memory import DecisionError, decide_issue, decide_release
from semaudit.report.page import build, render


def serve(review_path: Path, *, by: str, port: int = 8791) -> None:
    out_dir = build(review_path).parent

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = unquote(urlparse(self.path).path)
            if path in ("/", "/index.html"):
                self._send(200, render(review_path, interactive=True, by=by).encode())
                return
            f = (out_dir / path.lstrip("/")).resolve()
            if out_dir.resolve() not in f.parents or not f.is_file():
                self.send_error(404)
                return
            self._send(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream")

        def do_POST(self):
            form = {k: v[0] for k, v in parse_qs(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()).items()}
            try:
                if self.path == "/decide":
                    decide_issue(review_path, form.get("issue", ""), form.get("kind", ""), by=by,
                                 reason=form.get("reason"), expires=form.get("expires"))
                elif self.path == "/release":
                    decide_release(review_path, form.get("decision", ""), by=by, note=form.get("note") or None)
                else:
                    self.send_error(404)
                    return
            except DecisionError as e:
                self._send(400, f"<p>Not recorded: {html.escape(str(e))}</p><p><a href='/'>back</a></p>".encode())
                return
            build(review_path)
            self.send_response(303)
            self.send_header("Location", "/" + (form.get("back") or ""))
            self.end_headers()

        def log_message(self, *a):
            pass

    print(f"Release Story: http://127.0.0.1:{port}/  (decisions are recorded as {by!r})")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
