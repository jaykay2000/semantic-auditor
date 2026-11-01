"""Imported checks (semaudit.imported): every safeguard of the converter, the re-check and the memory.

Each test names the safeguard it pins. scripts/mutate_imported_checks.py removes each safeguard in turn and shows
the test that pins it going red (docs/evidence/imported-checks/).
"""

import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.contract.approve import approve_check, load_approvals  # noqa: E402
from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.decide import memory  # noqa: E402
from semaudit.imported import convert as cv  # noqa: E402
from semaudit.imported import recheck as rc  # noqa: E402
from semaudit.imported.record import ImportedCheck, Source, load_spec  # noqa: E402
from semaudit.story.episode import Episode, StepRecord  # noqa: E402
from semaudit.story.model import Event, Story  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "imported_contract"
C = load_contract(FIX)
SPEC = load_spec(FIX)
VERBS = cv.adapter_verbs(C, FIX)
CAT = cv.load_catalogs(SPEC, FIX)

REPRO = "open the desk, pick 2 × Desk Lamp, enter voucher SAVE5, submit. How checked: receipt total compared to record."
SRC = Source(ref="T#00", claim="receipt does not add up", where="North branch, member t@example.test",
             shown="Lines $10.00 and $5.00 then Total $12.50", should_be="the total should equal the sum of the lines", reproduce=REPRO, rule="R1")
GOOD = {
    "clauses": [
        {"text": "open the desk, ", "kind": "action", "steps": [0], "sets": [], "unmapped_reason": "",
         "missing_verb": "", "why": ""},
        {"text": "pick 2 × Desk Lamp, ", "kind": "action", "steps": [1], "sets": ["picks"], "unmapped_reason": "",
         "missing_verb": "", "why": ""},
        {"text": "enter voucher SAVE5, ", "kind": "action", "steps": [2], "sets": ["voucher"],
         "unmapped_reason": "", "missing_verb": "", "why": ""},
        {"text": "submit.", "kind": "action", "steps": [3], "sets": [], "unmapped_reason": "", "missing_verb": "",
         "why": ""},
        {"text": "How checked: receipt total compared to record.", "kind": "observation", "steps": [], "sets": [],
         "unmapped_reason": "", "missing_verb": "", "why": ""},
    ],
    "steps": [{"do": "open_desk", "clause": 0}, {"do": "pick_item", "clause": 1}, {"do": "enter_voucher", "clause": 2},
              {"do": "submit", "clause": 3}],
    "persona": [{"field": "picks", "value": "", "values": ["lamp||2"], "clause": 1},
                {"field": "voucher", "value": "SAVE5", "values": [], "clause": 2},
                {"field": "branch", "value": "North", "values": [], "clause": -2}],
    "invariant": {"rule": "R1", "surface": "receipt_page", "missing_surface": "",
                  "statement": "the components the receipt shows reconcile with the total it shows and match the record"},
}


def gate(d, src=SRC):
    return cv.gate(d, src, SPEC, C, VERBS, CAT)


def g():
    return copy.deepcopy(GOOD)


# ---------- the gate ----------

def test_good_draft_passes_and_converts():
    assert gate(g()) == []
    status, conv = cv.classify(g(), SPEC, C, VERBS)
    assert status == "converted" and conv.implied_steps == ["choose_speed"]


def test_prerequisite_is_inserted_only_when_implied_ok():
    """safeguard: prerequisites. choose_speed (implied_ok) is inserted before submit; nothing else is."""
    persona, scenario, _ = cv.build("t-1", g(), SPEC, C)
    assert [s["do"] for s in scenario["steps"]] == ["open_desk", "pick_item", "enter_voucher", "choose_speed",
                                                    "submit"]
    d = g()
    d["steps"] = [{"do": "submit", "clause": 3}]
    d["clauses"] = [dict(c, steps=[0] if i == 3 else [], kind=c["kind"] if i in (3, 4) else "context")
                    for i, c in enumerate(d["clauses"])]
    _, conv = cv.classify(d, SPEC, C, VERBS)
    assert any("submit needs pick_item" in r for r in conv.reasons) and conv.status == "partially_converted"


def test_coverage_refuses_a_dropped_instruction():
    """safeguard: coverage. A clause left out of the draft is an instruction skipped silently."""
    d = g()
    del d["clauses"][2]
    d["steps"] = [s for s in d["steps"] if s["do"] != "enter_voucher"]
    d["clauses"][2]["steps"] = [2]
    d["steps"][2]["clause"] = 2
    assert any("leave out part of the reproduce text" in e and "voucher" in e for e in gate(d))


def test_coverage_refuses_a_rewritten_clause():
    d = g()
    d["clauses"][1]["text"] = "pick two desk lamps, "
    assert any("not a verbatim piece" in e for e in gate(d))


def test_unknown_verb_is_refused():
    """safeguard: verbs. A verb the adapter lacks is never in a scenario."""
    d = g()
    d["steps"][2]["do"] = "teleport"
    assert any("'teleport' is not a verb the adapter has" in e for e in gate(d))


def test_fabricated_mapping_is_refused():
    """safeguard: verb cues. 'signed in' cannot be carried out by pick_item (the dev run found this fabrication)."""
    d = g()
    d["clauses"][0]["text"] = "open the desk, "
    d["clauses"][1]["text"] = "pick 2 × Desk Lamp, "
    src = SRC.model_copy(update={"reproduce": REPRO.replace("open the desk", "signed in, open the desk")})
    d["clauses"].insert(0, {"text": "signed in, ", "kind": "action", "steps": [1], "sets": [], "unmapped_reason": "",
                            "missing_verb": "", "why": ""})
    for c in d["clauses"][1:]:
        c["steps"] = [k + 1 for k in c["steps"]] if c["kind"] == "action" else []
    d["clauses"][1]["steps"] = [0]
    d["steps"] = [{"do": "open_desk", "clause": 1}, {"do": "pick_item", "clause": 0},
                  {"do": "pick_item", "clause": 2}, {"do": "enter_voucher", "clause": 3}, {"do": "submit", "clause": 4}]
    d["clauses"][2]["steps"] = [2]
    d["clauses"][3]["steps"] = [3]
    d["clauses"][4]["steps"] = [4]
    for p in d["persona"]:
        if p["clause"] >= 0:
            p["clause"] += 1
    errs = gate(d, src)
    assert any("step 1 (pick_item) cites clause 0" in e and "do not describe pick_item" in e for e in errs), errs


def test_missing_verb_that_exists_is_refused():
    """safeguard: an action marked unmapped for want of a verb the adapter has is refused (it should map)."""
    d = g()
    d["clauses"][3].update(steps=[], unmapped_reason="no_verb", missing_verb="submit")
    d["steps"] = d["steps"][:3]
    assert any("says verb 'submit' is missing" in e for e in gate(d))


def test_action_clause_must_map_or_be_unmapped():
    d = g()
    d["clauses"][3]["steps"] = []
    d["steps"] = d["steps"][:3]
    assert any("has no steps and no unmapped reason" in e for e in gate(d))


def test_material_field_needs_a_source():
    """safeguard: persona. A material field from no clause must equal its declared default."""
    d = g()
    d["persona"].append({"field": "speed", "value": "Fast", "values": [], "clause": -1})
    assert any("material field 'speed'" in e for e in gate(d))


def test_catalog_is_enforced():
    """safeguard: list fields. An item the store does not have, or an option it lacks, is refused."""
    d = g()
    d["persona"][0]["values"] = ["sofa||1"]
    assert any("'sofa' is not in the catalog" in e for e in gate(d))
    d["persona"][0]["values"] = ["lamp|Green|1"]
    assert any("'Green' is not an option" in e for e in gate(d))


def test_invariant_may_not_copy_the_quote():
    """safeguard: the invariant is a property, not the old figures."""
    d = g()
    d["invariant"]["statement"] = "the total must not read 12.50"
    assert any("copies figures from the quote" in e for e in gate(d))


def test_invariant_surface_must_be_reached():
    d = g()
    d["invariant"]["surface"] = "receipt_mail"
    assert any("reached by read_receipt_mail, which no step does" in e for e in gate(d))
    d["steps"].append({"do": "read_receipt_mail", "clause": -1})
    assert gate(d) == []


def test_suspect_observation_is_partially_converted():
    """safeguard: an 'observation' that reads like an action (signed in) is not trusted: partially_converted."""
    d = g()
    d["clauses"][4]["text"] = "How checked: signed in as member and compared to record."
    status, conv = cv.classify(d, SPEC, C, VERBS)
    assert status == "partially_converted" and any("reads like an action" in r for r in conv.reasons)


def test_missing_verb_is_an_adapter_gap():
    """safeguard: classification. An action no verb does is adapter_gap, never a replay."""
    d = g()
    d["clauses"][2].update(steps=[], unmapped_reason="no_verb", missing_verb="sign_in")
    d["steps"] = [s for s in d["steps"] if s["do"] != "enter_voucher"]
    d["steps"][2]["clause"] = 3
    d["clauses"][3]["steps"] = [2]
    status, conv = cv.classify(d, SPEC, C, VERBS)
    assert status == "adapter_gap" and conv.gaps == ["sign_in"]


def test_unreachable_surface_is_an_adapter_gap():
    d = g()
    d["invariant"].update(surface="", missing_surface="the member's history page")
    assert gate(d) == []
    status, conv = cv.classify(d, SPEC, C, VERBS)
    assert status == "adapter_gap" and conv.gaps[0].startswith("surface:")


class FakeRouter:
    def __init__(self, replies):
        self.replies = list(replies)

    def complete(self, role, msgs, **kw):
        class R:
            pass
        r = R()
        r.parsed, r.cached, r.cost_usd, r.model = self.replies.pop(0), False, 0.01, "fake"
        return r


def test_a_draft_that_keeps_failing_is_not_converted():
    """safeguard: fail closed. Two failing drafts -> not_converted, with no persona or scenario to replay."""
    bad = g()
    bad["steps"][0]["do"] = "teleport"
    chk = cv.convert("T-00", SRC, C, FIX, SPEC, FakeRouter([bad, bad]))
    assert chk.conversion.status == "not_converted" and chk.scenario == {} and chk.persona == {}
    assert chk.conversion.gate_rounds == 2


def test_a_redraft_that_fixes_the_gate_converts():
    bad = g()
    bad["steps"][0]["do"] = "teleport"
    chk = cv.convert("T-00", SRC, C, FIX, SPEC, FakeRouter([bad, g()]))
    assert chk.conversion.status == "converted" and chk.conversion.gate_rounds == 2
    assert chk.persona["context"]["email"] == "ic-t-00@example.test"
    assert chk.invariant.rule == "A1" and chk.source.shown == SRC.shown


# ---------- the re-check ----------

D0 = datetime(2026, 11, 2, 10, tzinfo=timezone.utc)


def _check():
    return cv.convert("T-00", SRC, C, FIX, SPEC, FakeRouter([g()]))


def _story(text="Lines $10.00 $5.00 Total $15.00", surface="receipt_page"):
    return Story(id="s", release="r1", persona="ic_t-00", context={"branch": "North"}, events=[
        Event(id="m1", at=D0, kind="message", feature="core", surface=surface, channel="page", text=text)])


def test_judge_never_sees_the_original_quote():
    """safeguard: the invariant is judged, not the quote's presence."""
    chk = _check()
    body = rc.judge_payload(chk, C, _story().messages(), {"record": {"total": 15.0}}, {"branch": "North"})
    blob = json.dumps(body)
    for leak in (SRC.shown, SRC.claim, SRC.should_be, "12.50"):
        assert leak not in blob


def _ep(note=None):
    return Episode(release="r1", persona="ic_t-00", scenario="IC-T-00", app_build="x", started_wall="w", day0=D0,
                   clock_measured=False,
                   steps=[StepRecord(seq=1, at=D0, do="enter_voucher", status="done", note=note)])


def test_replay_fails_when_the_app_refused_a_step():
    """safeguard: a step the app refused (a voucher not accepted) is not a successful replay."""
    rs = rc.replay_status(_ep("the app did not accept 'SAVE5'"), _check(), C, SPEC)
    assert rs["status"] == "failed" and any("did not do what the finding needs" in r for r in rs["reasons"])


def test_replay_fails_without_the_surface():
    rs = rc.replay_status(_ep(), _check(), C, SPEC)
    assert rs["status"] == "failed" and any("no message was captured on receipt_page" in r for r in rs["reasons"])


def _recheck(monkeypatch, outcomes, story=None, record=None, cited=None):
    chk = _check()
    monkeypatch.setattr(rc, "replay_status", lambda *a, **k: {"status": "succeeded", "reasons": [], "notes": []})
    monkeypatch.setattr(rc, "_story", lambda *a, **k: story or _story())
    monkeypatch.setattr(rc, "record_at", lambda *a, **k: record or {"record": {"total": 15.0}})
    replies = iter(outcomes)

    def fake(router, body, *, seed, fresh=False):
        return {"outcome": next(replies), "why": "", "cited": cited if cited is not None else
                [{"event_id": "m1", "quote": "Total $15.00"}], "record": [{"field": "total", "value": "15.00"}],
                "seed": seed, "model": "fake", "cached": False, "cost_usd": 0.001}
    monkeypatch.setattr(rc, "judge", fake)
    return rc.recheck(chk, _ep(), C, SPEC, None, judgments=3, approved=False)


def test_four_statuses_are_separate(monkeypatch):
    r = _recheck(monkeypatch, ["pass", "pass", "fail"])
    assert r["replay"]["status"] == "succeeded"
    assert r["assertion"]["outcome"] == "pass" and r["assertion"]["votes"] == {"pass": 2, "fail": 1}
    assert r["semantic_confidence"] == {"level": "medium", "agreement": "2/3", "judgments": 3}
    assert r["evidence"]["status"] == "verified"


def test_no_majority_is_not_measurable(monkeypatch):
    """safeguard: judgments that disagree three ways do not produce a pass or a fail."""
    r = _recheck(monkeypatch, ["pass", "fail", "not_measurable"])
    assert r["assertion"]["outcome"] == "not_measurable" and r["semantic_confidence"]["level"] == "low"


def test_quote_not_in_the_capture_is_unverified(monkeypatch):
    """safeguard: evidence. A quote the capture does not hold is refused."""
    r = _recheck(monkeypatch, ["pass"] * 3, cited=[{"event_id": "m1", "quote": "Total $99.00 due"}])
    assert r["evidence"]["status"] == "unverified"


def test_quote_on_another_surface_is_not_evidence(monkeypatch):
    r = _recheck(monkeypatch, ["pass"] * 3, story=_story(surface="desk_page"))
    assert r["evidence"]["status"] == "unverified"


def test_record_value_must_match(monkeypatch):
    """safeguard: evidence. A record value the judgment misread makes the evidence partial, not verified."""
    r = _recheck(monkeypatch, ["pass"] * 3, record={"record": {"total": 12.5}})
    assert r["evidence"]["status"] == "partially_verified"


def test_failed_replay_is_never_judged(monkeypatch):
    chk = _check()
    called = []
    monkeypatch.setattr(rc, "judge", lambda *a, **k: called.append(1))
    r = rc.recheck(chk, None, C, SPEC, None, approved=False)
    assert r["replay"]["status"] == "failed" and r["assertion"]["outcome"] == "not_measurable" and not called


# ---------- approval and memory ----------

def test_replay_refuses_an_unapproved_check(tmp_path):
    """safeguard: owner approval. A check runs only when approved at its current content."""
    chk = _check()
    with pytest.raises(PermissionError):
        rc.replay([chk], FIX, "r1", runs_dir=tmp_path, run_id="x", approvals={})
    approve_check(tmp_path, chk.id, chk.digest(), by="owner")
    assert rc.is_approved(chk, load_approvals(tmp_path))
    changed = chk.model_copy(update={"invariant": chk.invariant.model_copy(update={"statement": "other"})})
    assert not rc.is_approved(changed, load_approvals(tmp_path))


def _r(replay="succeeded", outcome="pass", evidence="verified", release="r1"):
    return {"release": release, "replay": {"status": replay, "reasons": ["x"]}, "assertion": {"outcome": outcome},
            "evidence": {"status": evidence}}


def test_check_status_vocabulary():
    assert memory.check_status(_r(outcome="fail"), _r())[0] == "fix_confirmed"
    assert memory.check_status(_r(outcome="fail"), _r(outcome="fail"))[0] == "still_open"
    assert memory.check_status(_r(), _r(outcome="fail"))[0] == "regressed"
    assert memory.check_status(_r(), _r())[0] == "not_reproduced"


def test_fix_needs_verified_evidence_not_an_absence():
    """safeguard: a head pass without verified evidence does not confirm a fix."""
    assert memory.check_status(_r(outcome="fail"), _r(evidence="partially_verified"))[0] == "not_confirmed"
    assert memory.check_status(_r(outcome="fail"), _r(replay="failed"))[0] == "not_confirmed"


def test_memory_keeps_checks_beside_issues(tmp_path):
    """safeguard: saving the memory never drops the check decisions and outcomes."""
    memory.decide_check(tmp_path, "T-00", "abc", "fix", by="owner")
    data = memory.load(tmp_path)
    data["issues"].append({"id": "D-001"})
    memory.save(tmp_path, data)
    o = memory.record_check_outcome(tmp_path, "T-00", "abc", _r(outcome="fail"), _r(release="r2"), run="run1")
    assert o["status"] == "fix_confirmed" and o["decision"] == "fix" and o["decision_applies"]
    kinds = [x["kind"] for x in memory.load(tmp_path)["checks"]]
    assert kinds == ["check_decision", "check_outcome"] and memory.load(tmp_path)["issues"] == [{"id": "D-001"}]


def test_check_record_round_trips(tmp_path):
    chk = _check()
    p = chk.write(tmp_path)
    assert ImportedCheck.read(p).digest() == chk.digest()


def test_bare_label_is_not_counted_against_the_evidence(monkeypatch):
    """A label with no figure is uninformative, not false: the figures' quotes still verify."""
    story = Story(id="s", release="r1", persona="ic_t-00", context={}, events=[
        Event(id="m1", at=D0, kind="message", feature="core", surface="receipt_page", channel="page",
              text="Total $15.00"),
        Event(id="m2", at=D0, kind="message", feature="core", surface="receipt_page", channel="page", text="Total")])
    r = _recheck(monkeypatch, ["pass"] * 3, story=story,
                 cited=[{"event_id": "m1", "quote": "Total $15.00"}, {"event_id": "m2", "quote": "Total"}])
    assert r["evidence"]["status"] == "verified"
    r = _recheck(monkeypatch, ["pass"] * 3, story=story,
                 cited=[{"event_id": "m1", "quote": "Total $15.00"}, {"event_id": "m2", "quote": "Total $16.00"}])
    assert r["evidence"]["status"] == "partially_verified"


def test_record_value_comparison():
    assert rc._same(89.99, ": 89.99") and rc._same(89.99, "$89.99") and rc._same(5.0, "5.00")
    assert not rc._same(89.99, "^1^") and not rc._same(89.99, "[  ]") and not rc._same(89.99, "89.99 or 90")
    assert rc._same("unfulfilled", "'Unfulfilled'") and not rc._same("paid", "unpaid")


def test_unreadable_judgment_is_a_not_measurable_vote():
    """A runaway reply (not JSON after retries) is recorded, never a crash, never a pass or a fail."""
    from semaudit.models.router import UnreadableReply

    class Runaway:
        def complete(self, *a, **k):
            raise UnreadableReply("finish_reason=length")
    j = rc.judge(Runaway(), {}, seed=1)
    assert j["outcome"] == "not_measurable" and j["unreadable"] and j["cited"] == []
