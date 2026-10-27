"""W9 (no model): severity, confidence and verification are independent; the policy reads all three."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.decide.issues import Issue, Occurrence, severity_of  # noqa: E402
from semaudit.relate.rules import Entry  # noqa: E402
from semaudit.verify.steps import confidence_of, verification_status  # noqa: E402

C = load_contract(ROOT / "examples" / "northbound" / "contract")
PASS = {"result": "pass", "detail": ""}
NOT_RUN = {"result": "not_run", "detail": ""}
FAIL = {"result": "fail", "detail": ""}
NA = {"result": "not_applicable", "detail": ""}


def issue(rule="P2", meta=None, conditions=()):
    e = Entry(rule, "s", "violated", label="unexplained_tradeoff", conditions=conditions, meta=meta or {})
    return Issue(id="I", signature=(), rule=rule, rule_kind=C.rule(rule).kind, layer="release",
                 label=e.label, occurrences=[Occurrence("maya", "x", ["a"], e, "before_decision")],
                 severity={}, why="")


def steps(**over):
    base = {"reproduced": PASS, "evidence_linked": PASS, "cross_model": PASS, "defended": PASS, "oracle_checked": NA}
    return {**base, **over}


def test_severity_moves_with_reach_alone():
    r = C.rule("P2")
    one = severity_of(r, 1, "before_decision", C)
    three = severity_of(r, 3, "before_decision", C)
    after = severity_of(r, 3, "after_decision", C)
    assert (one["level"], three["level"], after["level"]) == ("major", "critical", "major")
    i = issue()
    s = steps()
    assert confidence_of(i, s, C) == confidence_of(i, s, C) and verification_status(s)["status"] == "verified"


def test_confidence_moves_alone_with_unknown_validity():
    s = steps()
    known, unknown = issue(meta={"unknown_validity": False}), issue(meta={"unknown_validity": True})
    assert confidence_of(known, s, C)["level"] == "high"
    assert confidence_of(unknown, s, C)["level"] == "medium"
    assert verification_status(s)["status"] == "verified"                 # verification unchanged
    assert severity_of(C.rule("P2"), 3, "before_decision", C)["level"] == "critical"   # severity unchanged


def test_verification_moves_alone_when_reproduction_did_not_run():
    i = issue()
    full, partial = steps(), steps(reproduced=NOT_RUN)
    assert verification_status(full)["status"] == "verified"
    assert verification_status(partial)["status"] == "partially_verified"
    assert confidence_of(i, full, C) == confidence_of(i, partial, C)      # confidence does not read reproduction


def test_failed_verification_kinds():
    assert verification_status(steps(reproduced=FAIL))["reason"] == "not_reproducible"
    assert verification_status(steps(evidence_linked=FAIL))["reason"] == "evidence_unresolved"
    assert verification_status(steps(cross_model=FAIL, defended=FAIL))["reason"] == "disputed"
    v = verification_status(steps(cross_model=FAIL))
    assert v["status"] == "partially_verified" and "cross_model" in v["reason"]
    assert verification_status({k: NOT_RUN for k in steps()} | {"oracle_checked": NA})["status"] == "unverified"


def test_disagreement_or_successful_defense_makes_confidence_low():
    i = issue()
    assert confidence_of(i, steps(cross_model=FAIL), C)["level"] == "low"
    assert confidence_of(i, steps(defended=FAIL), C)["level"] == "low"
    assert confidence_of(i, steps(cross_model=NOT_RUN), C)["level"] == "medium"


def test_measured_vs_interpreted_evidence():
    from semaudit.verify.steps import evidence_kind
    assert evidence_kind(issue("U3"), C) == "measured"
    assert evidence_kind(issue("P2"), C) == "interpreted"
    assert evidence_kind(issue("P1", conditions=(("a", "not_met"),)), C) == "measured"
    assert evidence_kind(issue("P1", conditions=(("c", "not_met"),)), C) == "interpreted"


def test_policy_recommendation_follows_the_three_fields():
    p = C.policy
    rec = lambda s, c, v: p.evaluate([{"severity": s, "confidence": c, "verification": v}])[0].recommendation  # noqa
    assert rec("critical", "high", "verified") == "hold"
    assert rec("critical", "low", "verified") == "needs_owner_review"         # confidence alone moves it
    assert rec("critical", "high", "partially_verified") == "needs_owner_review"   # verification alone
    assert rec("major", "high", "verified") == "ship_with_notes"              # severity alone
