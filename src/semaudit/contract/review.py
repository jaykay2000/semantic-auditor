"""The contract review page: render the contract for the owner, and record approvals.

`render` produces one self-contained HTML page. `serve` runs it on localhost with working Approve
buttons that write approvals.yaml; without the server the page is read-only.
"""

from __future__ import annotations

import html
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .approve import approve, items, load_approvals, status_of, summary
from .schema import Condition, Contract, Rule, load_contract
from .validate import validate

_env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"),
                   autoescape=select_autoescape(["html", "j2"]), trim_blocks=True, lstrip_blocks=True)


def describe_condition(c: Condition) -> str:
    if c.kind == "judged":
        return f"the message {c.field.replace('_', ' ')} (judged by the model, re-checked by the verifier)"
    if c.test == "time_until":
        return f"{c.context_field.replace('_', ' ')} − message shown between 0 and {c.hours:g} h, on exact timestamps"
    if c.test == "claim_matches_oracle":
        return f"the {c.claim.replace('_', ' ')} claim matches the {c.oracle} oracle"
    return f"{c.test}"


def evaluated_by(r: Rule) -> str:
    must = r.check.get("must")
    if must == "match_oracle":
        return f"code: {', '.join(r.check['claims'])} claims vs the {r.check['oracle']} oracle"
    if must == "match_charge":
        return f"code: displayed {', '.join(r.check['claims'])} vs the amount charged, per transaction"
    if must == "precondition_holds_at_shown_time":
        return "code: each recommended action's precondition, at the moment it is shown"
    if "message_kind" in r.applies_to:
        state = ", ".join(f"{k} = {v}" for k, v in (r.applies_to.get("state") or {}).items())
        return f"model classifies the message as {r.applies_to['message_kind']}{' while ' + state if state else ''}; the verifier re-checks"
    if r.kind == "conditional":
        return (f"applies to directives on {r.applies_to.get('decision')} with strength "
                f"{' or '.join(r.applies_to.get('strength', []))}; forbidden unless an exception's conditions all hold")
    if r.kind == "coherence":
        return "code pairs live directives on the same decision; the model judges whether they are reconciled or explained"
    if r.kind == "load":
        n = r.count
        return f"code: count {' and '.join(n.get('channels', []))} in any {n.get('window_hours')} h; at most {n.get('max')}"
    return "—"


def render(c: Contract, approvals: dict, interactive: bool = False, problems: list[str] | None = None) -> str:
    its = items(c)
    status = {i.key: status_of(i, approvals) for i in its}
    return _env.get_template("review.html.j2").render(
        c=c, status=status, approvals=approvals, counts=summary(c, approvals), interactive=interactive,
        problems=problems or [], describe=describe_condition, evaluated_by=evaluated_by,
        unapproved=[k for k, s in status.items() if s != "approved"])


def write(directory: Path, out: Path) -> Path:
    c = load_contract(directory)
    out.write_text(render(c, load_approvals(directory), problems=validate(c)))
    return out


def serve(directory: Path, port: int = 8790, by: str = "owner") -> None:
    class Handler(BaseHTTPRequestHandler):
        def _page(self, code: int = 200):
            c = load_contract(directory)
            body = render(c, load_approvals(directory), interactive=True, problems=validate(c)).encode()
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._page()

        def do_POST(self):
            if self.path != "/approve":
                self.send_error(404)
                return
            form = parse_qs(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode())
            keys = form.get("key", [])
            try:
                approve(directory, load_contract(directory), keys, by=by)
            except KeyError as e:
                self.send_error(400, html.escape(str(e)))
                return
            self.send_response(303)
            self.send_header("Location", "/#" + (keys[0].replace(":", "-") if len(keys) == 1 else "top"))
            self.end_headers()

        def log_message(self, *a):
            pass

    print(f"contract review: http://127.0.0.1:{port}/  (approvals are recorded as {by!r})")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
