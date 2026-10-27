"""W13b (no model): the judge baselines get the auditor's evidence and nothing of its judgement."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.bench import judge  # noqa: E402
from semaudit.contract.schema import load_contract  # noqa: E402

C = load_contract(ROOT / "examples/northbound/contract")
RUN = ROOT / "runs/e2e-2"
pytestmark = pytest.mark.skipif(not (RUN / "episodes/2.4").exists(), reason="needs runs/e2e-2 (local)")


class FakeRouter:
    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def complete(self, role, messages, **kw):
        self.calls.append((role, messages, kw))
        return type("R", (), {"parsed": {"findings": self.answer}, "cost_usd": 0.01})()


GOOD = {"personas": ["kai"], "rule": "P2", "label": "conflict", "severity": "critical", "confidence": "high",
        "target": {"kind": "relation", "features": ["fare_lock", "price_watch"], "decision": "when_to_book",
                   "feature": None, "surface": None, "message_key": None},
        "why": "w", "cited": [{"persona": "kai", "event_id": "fl.banner.urgent", "quote": "x"}]}
BAD = {**GOOD, "target": {**GOOD["target"], "features": ["fare_lock"]}}     # a relation needs two features


def test_input_carries_evidence_but_no_auditor_judgement_and_no_persona_roles():
    stories = judge.stories_for(RUN, "2.4", C)
    r = FakeRouter([])
    judge.judge_one(stories, C, r, release="2.4")
    (role, msgs, kw), = r.calls
    text = msgs[1]["content"]
    assert role == "interpreter" and kw["schema"] is judge.SCHEMA
    for leaked in ("urgency_cue", "explains_own_tradeoff\": true", "\"strength\": \"urge\"", "candidates",
                   "\"hero\"", "\"negative\"", "\"boundary\""):
        assert leaked not in text, leaked
    payload = json.loads(text)
    assert {s["persona"] for s in payload["stories"]} == set(stories)
    assert any(e.get("text") for s in payload["stories"] for e in s["events"])
    assert any(s["oracle_readings"] for s in payload["stories"])
    assert {r_["id"] for r_ in payload["contract"]["rules"]} == {r_.id for r_ in C.rules}


def test_malformed_findings_are_dropped_and_listed_never_repaired():
    fs, dropped = judge.judge_one(judge.stories_for(RUN, "2.4", C), C, FakeRouter([GOOD, BAD]), release="2.4")
    assert len(fs.findings) == 1 and len(dropped) == 1 and fs.system == "B-judge-1"
    assert fs.findings[0].target.key() == ("relation", "fare_lock", "price_watch", "when_to_book")


def test_multi_pass_runs_one_pass_per_persona_then_critique_and_consolidation():
    stories = judge.stories_for(RUN, "2.4", C)
    r = FakeRouter([GOOD])
    fs, _ = judge.judge_multi(stories, C, r, release="2.4")
    assert fs.calls == len(stories) + 2 == len(r.calls)
    systems = [m[0]["content"] for _, m, _ in r.calls]
    assert all(judge.prompt("judge_persona") == s for s in systems[:len(stories)])
    assert systems[-2:] == [judge.prompt("judge_critique"), judge.prompt("judge_consolidate")]
    assert fs.cost_usd == pytest.approx(0.01 * (len(stories) + 2))


def test_every_prompt_carries_the_common_instructions():
    for name in ("judge_one", "judge_persona", "judge_critique", "judge_consolidate"):
        p = judge.prompt(name)
        assert "{{COMMON}}" not in p and "An exception to one rule never excuses" in p
