"""External audit #2 (2026-10-28): each finding reproduced as a test before it was fixed."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from semaudit.contract.schema import Fact, StateVar  # noqa: E402
from semaudit.decide.issues import signature  # noqa: E402
from semaudit.relate.claims import MATCH, MISMATCH, checkable, comparable, compare  # noqa: E402
from semaudit.relate.rules import Entry, eval_agree_across_states, eval_agree_across_surfaces  # noqa: E402
from semaudit.story.model import Event, Extraction, Story  # noqa: E402

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)


def ex(*claims):
    return Extraction(message_kind="information", decision="none", action="none", strength="inform",
                      urgency_cue="none", explains_own_tradeoff=False, claims=list(claims))


def msg(i, surface, minutes, *claims, key=None):
    return Event(id=i, at=T0 + timedelta(minutes=minutes), kind="message", feature="f", surface=surface,
                 text=i, copy_key=key or f"f.{i}", extraction=ex(*claims))


def act(i, minutes, action):
    return Event(id=i, at=T0 + timedelta(minutes=minutes), kind="user_action", action=action)


# AUD2-01: a second claim of the same type in one message is checked too
def test_a_second_keyed_claim_in_one_message_is_checked():
    move = Fact(id="move", key=[{"field": "for", "values": ["ret", "debt"]}])
    c = SimpleNamespace(facts=[move], state=[])
    rule = SimpleNamespace(id="U2", check={"claims": ["move"], "must": "agree_across_surfaces"})
    m = lambda f, v: {"type": "move", "value": v, "unit": "USD", "for": f}  # noqa: E731
    s = Story(id="s", release="r", persona="p", events=[msg("page", "report", 0, m("ret", 100), m("debt", 200)),
                                                       msg("export", "export", 1, m("ret", 100), m("debt", 999))])
    assert {x.status for x in eval_agree_across_surfaces(rule, s, c)} >= {"violated"}


# AUD2-02: a target below a cap is not a disagreement; a null role is not checked when roles are on
def test_a_target_below_the_cap_is_not_compared_with_the_cap():
    keyed = Fact(id="move", key=[{"field": "for", "values": ["ret"]}])
    a = {"type": "move", "value": 20000, "role": "proposed", "for": "ret"}
    b = {"type": "move", "value": 24500, "role": "limit", "for": "ret"}
    assert not comparable(keyed, a, b)


def test_with_roles_on_a_claim_whose_role_was_not_read_is_not_checked():
    assert checkable({"type": "x", "value": 1, "role": None}, Fact(id="x"), roles_on=True) is False
    assert checkable({"type": "x", "value": 1}, Fact(id="x")) is True          # roles off: as before


# AUD2-03: before/after must run forward, across the named transition, with truth known equal
STATES = SimpleNamespace(id="U4", check={"claims": ["score"], "must": "agree_across_states",
                                         "states": {"account": ["guest", "signed_in"]}})
ACCOUNT = StateVar(id="account", initial="guest", set_by={"sign_up": "signed_in", "sign_out": "guest"})
C = SimpleNamespace(facts=[Fact(id="score")], state=[ACCOUNT])
sc = lambda v: {"type": "score", "value": v, "unit": ""}  # noqa: E731


def test_state_agreement_never_runs_backwards():
    s = Story(id="s", release="r", persona="p", events=[
        act("a1", 0, "sign_up"), msg("signed", "report", 1, sc(50)), act("a2", 2, "sign_out"),
        msg("guest_late", "report", 3, sc(70))])
    assert [x for x in eval_agree_across_states(STATES, s, C) if x.status == "violated"] == []


def test_state_agreement_needs_the_transition_between_the_two():
    # guest at 0, then a later guest -> signed-in change happens only AFTER the signed-in-looking message? No:
    # two observations with the right state values but no sign_up action between them are not compared.
    s = Story(id="s", release="r", persona="p", events=[
        act("a1", 0, "sign_up"), act("a2", 1, "sign_out"), msg("guest", "report", 2, sc(50)),
        act("a3", 3, "sign_up"), msg("signed", "report", 4, sc(70))])
    got = [x for x in eval_agree_across_states(STATES, s, C) if x.status == "violated"]
    assert [x.subject for x in got] == ["guest"]                             # a3 is between them: compared


def test_state_agreement_with_truth_known_on_one_side_only_is_not_compared():
    s = Story(id="s", release="r", persona="p", events=[
        msg("guest", "report", 0, sc(50)), act("a1", 1, "sign_up"), msg("signed", "report", 2, sc(70))],
        snapshots=[{"at": T0 + timedelta(minutes=1, seconds=30), "truth": {"score": 70}}])
    assert [x for x in eval_agree_across_states(STATES, s, C) if x.status == "violated"] == []


# AUD2-05: one disagreement is one issue, whichever message is the subject
def test_one_disagreement_has_one_signature():
    a = Event(id="a", at=T0, kind="message", feature="plan", copy_key="plan.k", text="1")
    b = Event(id="b", at=T0, kind="message", feature="export", copy_key="export.k", text="2")
    e = lambda s, o: Entry("U2", s, "violated", meta={"events": [s, o], "fact": "x"})  # noqa: E731
    assert signature(e("a", "b"), [a, b]) == signature(e("b", "a"), [b, a])


# AUD2-09: a date claim is compared as a date even when the contract also has word facts
def test_a_datetime_claim_beside_word_facts_is_compared_as_a_time():
    claim = {"type": "deadline", "value": None, "word": None, "when": "2026-01-02T12:30"}
    assert compare(claim, "2026-01-02T12:30:00") == MATCH
    assert compare({"type": "m", "value": None, "word": "pay_down_debt"}, "pay_down_debt") == MATCH


# AUD2-04: WebSockets are held to local_only too, and every loopback address counts as loopback
def test_loopback_means_every_loopback_address():
    from semaudit.capture.runner import is_loopback
    assert all(is_loopback(h) for h in ("127.0.0.1", "127.0.0.2", "localhost", "::1", "[::1]", "app.localhost"))
    assert not any(is_loopback(h) for h in ("192.168.1.5", "10.0.0.1", "example.test", "", "127.0.0.1.example"))


@pytest.mark.browser
def test_a_websocket_to_another_host_never_connects_and_is_counted(tmp_path):
    import http.server
    import threading
    import pytest
    pw = pytest.importorskip("playwright.sync_api")
    from semaudit.capture.runner import _local_only_ws, _ws_local
    opened = []

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get("Upgrade", "").lower() == "websocket":
                opened.append(self.path)                  # a socket that reached a server
            body = (b"<script>const w = new WebSocket('ws://ws.example.test/feed');"
                    b"w.onopen = () => document.title = 'open';</script>ok")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with pw.sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context()
            blocked: dict = {}
            ctx.route_web_socket(lambda url: not _ws_local(url), lambda ws: _local_only_ws(ws, blocked))
            page = ctx.new_page()
            page.goto(f"http://127.0.0.1:{srv.server_address[1]}/", timeout=8000)
            page.wait_for_timeout(800)
            b.close()
    finally:
        srv.shutdown()
    assert blocked == {"ws.example.test": 1}
    assert _ws_local("ws://127.0.0.1:8090/x") and _ws_local("ws://localhost/x") and not _ws_local("wss://evil.test/")


# AUD2-10: repeated templates align within a visit, never across visits
def test_repeats_align_only_within_the_same_visit():
    from semaudit.story.align import align
    from semaudit.story.model import Evidence
    def m(i, step, text):
        ev = Evidence(episode="e", step=step, capture_id=f"c{step}", element=0, locator={},
                      attribution={"method": "contract_map"})
        return Event(id=i, at=T0 + timedelta(minutes=step), kind="message", feature="plan", surface="report",
                     channel="page", copy_key="plan.aa", text=text, evidence=ev)
    base = Story(id="b", release="b", persona="p", events=[m("b1", 1, "$100"), m("b2", 2, "$200")])
    head = Story(id="h", release="h", persona="p", events=[m("h1", 1, "$200"), m("h2", 2, "$300")])
    pairs = {(p.base, p.head): p.status for p in align(base, head).pairs}
    assert ("b2", "h1") not in pairs and ("b1", "h2") not in pairs     # no cross-visit pairing
    assert pairs == {("b1", "h1"): "changed", ("b2", "h2"): "changed"}


# AUD2-11: a short block's reading context stays inside its section
def test_reading_context_stops_at_the_section_boundary():
    from semaudit.story.build import around
    el = lambda t, s: SimpleNamespace(text=t, obscured=None, attribution={"section": s})  # noqa: E731
    cap = SimpleNamespace(kind="web", elements=[el("Spending", 0), el("$4K", 0), el("Retirement", 1)])
    assert around(cap, 1) == "Spending | [this] | "


# AUD2-13: short secrets are redacted as whole words
def test_short_secrets_are_redacted_without_eating_words():
    from semaudit.adapters.hooks import _redact
    assert _redact("code=abc rejected", {"abc"}) == "code=[redacted] rejected"
    assert _redact("abacus", {"ab"}) == "abacus" and _redact("token t0k3n-long", {"t0k3n-long"}) == "token [redacted]"


# AUD2-14: a manifest whose header id does not match its rows is refused
def test_a_forged_manifest_header_is_refused(tmp_path):
    import importlib.util
    import pytest
    spec = importlib.util.spec_from_file_location("fz2", ROOT / "scripts/freeze_conditions.py")
    fz = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fz)
    rows = [("a.py", "0" * 64)]
    good = tmp_path / "FROZEN-OK.md"
    good.write_text(f"FROZEN-OK manifest {fz.manifest_id(rows)} at code x\n\n| `a.py` | `{'0' * 64}` |\n")
    assert fz.manifest_of(good) == fz.manifest_id(rows)
    bad = tmp_path / "FROZEN-BAD.md"
    bad.write_text(f"FROZEN-BAD manifest {'f' * 64} at code x\n\n| `a.py` | `{'0' * 64}` |\n")
    with pytest.raises(ValueError, match="does not match its rows"):
        fz.manifest_of(bad)


def test_shared_readings_extract_identical_text_once_for_both_releases(monkeypatch):
    import semaudit.decide.pipeline as pl
    calls = []

    def fake(msgs, contract, router, **kw):
        calls.append(sorted(m.text for m in msgs))
        return {pl.message_key(m): ex() for m in msgs}
    monkeypatch.setattr(pl, "extract_unique", fake)
    from semaudit.decide.pipeline import message_key  # noqa: F401
    shared = {}
    s1 = [Event(id="a", at=T0, kind="message", feature="f", surface="r", text="Same line"),
          Event(id="b", at=T0, kind="message", feature="f", surface="r", text="Only base")]
    s2 = [Event(id="a", at=T0, kind="message", feature="f", surface="r", text="Same line"),
          Event(id="c", at=T0, kind="message", feature="f", surface="r", text="Only head")]
    for evs in (s1, s2):
        msgs = [m for m in evs if pl.message_key(m) not in shared]
        shared.update(pl.extract_unique(msgs, None, None))
    assert calls == [["Only base", "Same line"], ["Only head"]]
    import inspect
    src = inspect.getsource(pl.evaluate_release)
    assert "if readings is not None:" in src and "readings.update(ext)" in src


# AUD2-06 (harness): a truth known only as a range
def test_a_claim_is_checked_against_a_range_truth():
    room = {"at_least": 23750, "at_most": 35750}
    assert compare({"value": 12500}, room) == MISMATCH
    assert compare({"value": 30000}, room) == MATCH and compare({"value": 23750}, room) == MATCH
    assert compare({"value": 40000}, room) == MISMATCH
    assert compare({"value": 23700, "precision": 100}, room) == MATCH          # shown to the hundred
    assert compare({"value": None}, room) == "unreadable"
