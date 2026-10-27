"""Offline check of the code layer: gold extractions + gold P2 labels -> exact expected vectors.

No model calls. If this fails, the bug is in the generators or rule evaluation, not the model.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.relate.compare import diff  # noqa: E402
from semaudit.relate.rules import evaluate  # noqa: E402
from semaudit.story.model import Extraction, Story  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "stories"
CONTRACT = load_contract(ROOT / "examples" / "northbound" / "contract")
GOLD = json.loads((FIX / "copy_gold.json").read_text())
NAMES = sorted(p.stem for p in FIX.glob("*.json") if p.stem != "copy_gold")


def load(name):
    raw = json.loads((FIX / f"{name}.json").read_text())
    story = Story(**raw["story"])
    for e in story.messages():
        e.extraction = Extraction(**GOLD[e.copy_key])
    return story, raw


def gold_interpreter(raw):
    p2 = next((e for e in raw["expected"] if e["rule"] == "P2"), None)

    def interpret(story, cand, contract):
        assert p2 is not None, f"unexpected P2 candidate {cand.subject} in {story.id}"
        return {"label": p2["label"], "reconciling_event_id": raw.get("gold_reconciler"), "rationale": "gold"}
    return interpret


@pytest.mark.parametrize("name", NAMES)
def test_code_layer_matches_expected(name):
    story, raw = load(name)
    result = diff(evaluate(story, CONTRACT, gold_interpreter(raw)), raw["expected"])
    assert result["match"], result


def test_fixture_count():
    assert len(NAMES) == 16


def test_late_reconciler_is_not_accepted():
    """A reconciling message after the traveller decided must not clear P2 (code-side timing check)."""
    story, raw = load("maya_r")
    for e in story.events:
        if e.id == "cg_inline":
            e.at = e.at.replace(minute=30)   # 10:30, after booking at 10:06
    entries = evaluate(story, CONTRACT, gold_interpreter(raw))
    p2 = [e for e in entries if e.rule == "P2"]
    assert p2 and p2[0].status == "violated" and p2[0].label == "unexplained_tradeoff"


# ---------- adversarial timing cases (external audit, 2026-10-26) ----------
from datetime import timedelta  # noqa: E402

from semaudit.contract.schema import load_contract as _load  # noqa: E402
from semaudit.relate.rules import p2_candidates, validity  # noqa: E402


def labeller(label, rid=None):
    return lambda story, cand, contract: {"label": label, "reconciling_event_id": rid or "", "rationale": "t"}


def test_reconciler_after_both_directives_expired_does_not_clear_p2():
    """The audit's repro: reconcile 2.5 h later, booking postponed. Both lives had ended, so P2 stays violated."""
    story, raw = load("maya_r")
    for e in story.events:
        if e.id == "cg_inline":
            e.at = e.at.replace(hour=12, minute=30)
        if e.id == "a_book":
            e.at = e.at.replace(hour=13, minute=0)
    entries = evaluate(story, CONTRACT, labeller("explained_tradeoff", "cg_inline"))
    p2 = [e for e in entries if e.rule == "P2"]
    assert p2 and p2[0].status == "violated" and p2[0].label == "unexplained_tradeoff", p2


def test_reconciler_while_both_live_clears_p2():
    story, raw = load("maya_r")
    entries = evaluate(story, CONTRACT, labeller("explained_tradeoff", "cg_inline"))
    assert next(e for e in entries if e.rule == "P2").status == "passed"


def test_departure_in_the_past_is_not_within_72h():
    story, raw = load("raj")
    story.trip["departure_at"] = (story.events[0].at - timedelta(hours=1)).isoformat()
    p1 = next(e for e in evaluate(story, CONTRACT, gold_interpreter(raw)) if e.rule == "P1")
    assert p1.status == "violated" and ("a", "not_met") in p1.conditions


def test_expired_exception_does_not_apply():
    c = CONTRACT.model_copy(deep=True)
    c.rule("P1").exceptions[0].approved["expires"] = "2026-11-01"      # the day before the story
    story, raw = load("raj")
    p1 = next(e for e in evaluate(story, c, gold_interpreter(raw)) if e.rule == "P1")
    assert p1.status == "violated" and ("expiry", "not_met") in p1.conditions


def test_exception_valid_through_its_expiry_date():
    c = CONTRACT.model_copy(deep=True)
    c.rule("P1").exceptions[0].approved["expires"] = "2026-11-02"      # the story's own day: still valid
    story, raw = load("raj")
    assert next(e for e in evaluate(story, c, gold_interpreter(raw)) if e.rule == "P1").status == "excepted"


def test_a_later_same_feature_directive_supersedes_the_earlier():
    story, _ = load("maya")
    card = next(e for e in story.events if e.id == "pw_card")
    email = next(e for e in story.events if e.id == "pw_email")
    lv = validity(card, story, CONTRACT)
    assert lv.end == email.at and lv.basis == "superseded"


def test_incompatible_and_tradeoff_pairs_are_judged_separately():
    """Kai's story plus an ordinary lock banner: book_now vs wait AND lock vs wait are two candidates."""
    story, raw = load("kai")
    extra = next(e for e in story.events if e.id == "fl_urgent").model_copy(deep=True)
    extra.id, extra.copy_key, extra.at = "fl_lock", "fl.banner", extra.at + timedelta(seconds=1)
    extra.extraction = Extraction(**GOLD["fl.banner"])
    story.events.append(extra)
    kinds = sorted(c.subject.rsplit(":", 1)[1] for c in p2_candidates(story, CONTRACT))
    assert kinds == ["incompatible", "tradeoff"]
