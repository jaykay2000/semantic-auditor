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
