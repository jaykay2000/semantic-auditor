"""Audit P0: 'could not measure' must never become Ship or Resolved. No model, no browser."""

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.decide.issues import Issue, Occurrence, apply_delta  # noqa: E402
from semaudit.decide.pipeline import evaluate_release, measurement_problems  # noqa: E402
from semaudit.relate.rules import Entry  # noqa: E402
from semaudit.report.review import outcome_of  # noqa: E402
from semaudit.story.episode import Episode, OracleReading, StepRecord  # noqa: E402

CONTRACT = ROOT / "examples" / "northbound" / "contract"
C = load_contract(CONTRACT)
D0 = datetime(2026, 11, 2, tzinfo=timezone.utc)
OK = OracleReading(status="ok", values={"x": 1})
LOST = OracleReading(status="not_measured", error="HTTP 500")


def episode(persona="maya", scenario="S-book-flexible", initial=OK, state=OK, status="done"):
    return Episode(release="2.4", persona=persona, scenario=scenario, app_build="t", started_wall="t", day0=D0,
                   clock_measured=True, initial_state={"inventory": initial},
                   steps=[StepRecord(seq=1, at=D0, do="search", status=status, state={"inventory": state})])


def test_an_unread_oracle_makes_the_episode_unmeasured():
    assert measurement_problems(episode()) == []
    assert any("oracle inventory after step 1" in p for p in measurement_problems(episode(state=LOST)))
    assert any("oracle inventory before the scenario" in p for p in measurement_problems(episode(initial=LOST)))
    assert measurement_problems(episode(state=OracleReading(status="not_applicable"))) == []


def test_a_scheduled_persona_with_no_episode_is_not_measured(tmp_path):
    (tmp_path / "episodes" / "2.4").mkdir(parents=True)
    ep = episode()
    ep.write(tmp_path / "episodes" / "2.4" / "maya__S-book-flexible.json")
    ev = evaluate_release(tmp_path, "2.4", C, router=None)
    assert not ev.complete
    assert "no 2.4 episode for scenario" in ev.not_measured["raj"][0] and "raj" not in ev.results


def issue(sig, personas):
    occ = [Occurrence(p, "s", ["e"], Entry("U3", "e", "violated"), "after_decision") for p in personas]
    return Issue(id=f"I-{sig}", signature=(sig,), rule="U3", rule_kind="universal", layer="release", label=None,
                 occurrences=occ, severity={}, why="")


def test_absence_in_an_unmeasured_head_is_not_a_fix():
    base = [issue("a", ["maya", "lena"]), issue("b", ["kai"])]
    resolved, unconfirmed = apply_delta([], base, measured_base={"maya", "lena", "kai"},
                                        measured_head={"maya", "kai"})          # lena's head capture broke
    assert [i.id for i in resolved] == ["I-b"]
    assert [i.id for i in unconfirmed] == ["I-a"] and unconfirmed[0].delta == "not_measured_in_head"
    assert "lena" in unconfirmed[0].delta_basis


def test_a_broken_head_capture_cannot_produce_ship():
    approved = {"complete": True, "pending": []}
    assert outcome_of("ship", measured=False, approval=approved)["recommendation"] == "not_measurable"
    assert outcome_of("ship", measured=True, approval=approved) == {"status": "decided", "recommendation": "ship",
                                                                     "reason": ""}


def test_an_unapproved_contract_gives_only_a_provisional_answer():
    pending = {"complete": False, "pending": ["rule:P2"]}
    out = outcome_of("hold", measured=True, approval=pending)
    assert out["status"] == "provisional" and out["recommendation"] == "provisional"
    assert out["policy_would_say"] == "hold" and "1 contract item" in out["reason"]
    assert outcome_of("ship", measured=False, approval=pending)["status"] == "not_measurable"   # worse wins
