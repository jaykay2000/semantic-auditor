"""The one claim comparison (relate/claims.py), and the date/time defect the sealed W13b run exposed.

The sealed run's counts-only breakdown (custodian, 2026-10-27) measured 34 of 34 false alarms on one objective
rule, all on messages that stated the CORRECT date/time: the old comparison was `claim["value"] == truth`, and a
number can never equal a timestamp. The three claim shapes the extractor produced are rebuilt here from that
report's description only (no sealed file was read): value 0 with the time in `unit`, value 0 with the time
missing, and the correct epoch seconds. None of them may become a violation.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from semaudit.relate.claims import MATCH, MISMATCH, UNREADABLE, compare, shown  # noqa: E402
from semaudit.relate.rules import eval_match_oracle  # noqa: E402
from semaudit.story.model import Event, Extraction, Story  # noqa: E402
from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.extract.messages import _prompt, extraction_schema  # noqa: E402

NORTHBOUND = Path(__file__).resolve().parents[1] / "examples/northbound/contract"

TRUTH = "2026-11-03T14:05:00+01:00"


def test_numbers_compare_as_before():
    assert compare({"value": 42.0, "unit": "EUR"}, 42) == MATCH
    assert compare({"value": 41.99, "unit": "EUR"}, 42) == MISMATCH
    assert compare({"value": None, "unit": "EUR"}, 42) == UNREADABLE


def test_a_correct_time_matches_at_the_claims_own_precision():
    assert compare({"when": "2026-11-03T14:05"}, TRUTH) == MATCH                 # wall clock, no zone given
    assert compare({"when": "2026-11-03T14:05+01:00"}, TRUTH) == MATCH
    assert compare({"when": "2026-11-03T13:05Z"}, TRUTH) == MATCH                # same instant, other zone
    assert compare({"when": "2026-11-03"}, TRUTH) == MATCH                       # date only
    assert compare({"when": "2026-11-03T14:05"}, "2026-11-03T14:05:40+01:00") == MATCH   # states the minute
    assert compare({"when": "2026-11-03T14:05"}, datetime(2026, 11, 3, 14, 5)) == MATCH  # datetime truth


def test_a_wrong_time_is_a_mismatch():
    assert compare({"when": "2026-11-03T15:05"}, TRUTH) == MISMATCH
    assert compare({"when": "2026-11-04"}, TRUTH) == MISMATCH
    assert compare({"when": "2026-11-03T14:05+00:00"}, TRUTH) == MISMATCH       # an hour off as an instant


def test_the_three_sealed_failure_shapes_are_never_violations():
    shapes = [{"value": 0, "unit": "2026-11-03 14:05"},                             # time in the unit field
              {"value": 0, "unit": "Europe/Lisbon"},                                # time missing
              {"value": datetime.fromisoformat(TRUTH).timestamp(), "unit": "s"}]    # epoch seconds
    for c in shapes:
        assert compare(c, TRUTH) == UNREADABLE, c
    assert compare({"when": "tomorrow at 2"}, TRUTH) == UNREADABLE
    assert compare({"when": None}, TRUTH) == UNREADABLE


def _story(claims):
    x = Extraction(message_kind="information", decision="none", action="none", strength="inform",
                   urgency_cue="none", explains_own_tradeoff=False, claims=claims)
    at = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)
    return Story(id="s", release="r", persona="p", truth={"departs_at": TRUTH},
                 events=[Event(id="e1", at=at, kind="message", feature="f", text="Departs 3 Nov, 14:05",
                               extraction=x)])


def test_match_oracle_raises_only_a_real_mismatch():
    rule = SimpleNamespace(id="R1", check={"claims": ["departs_at"]})
    status = lambda c: [e.status for e in eval_match_oracle(rule, _story([{"type": "departs_at", **c}]))]  # noqa: E731
    assert status({"value": None, "unit": "", "when": "2026-11-03T14:05"}) == ["passed"]
    assert status({"value": None, "unit": "", "when": "2026-11-03T16:05"}) == ["violated"]
    assert status({"value": 0, "unit": "2026-11-03 14:05"}) == ["unreadable"]         # recorded, not raised


def test_shown_prefers_the_moment():
    assert shown({"value": None, "when": "2026-11-03T14:05"}) == "2026-11-03T14:05"
    assert shown({"value": 42.0}) == "42"
    assert shown({"value": None}) == "?"


def _claim_item(c):
    return extraction_schema(c)["properties"]["messages"]["items"]["properties"]["claims"]["items"]


def test_a_contract_without_a_datetime_fact_keeps_the_original_extraction():
    """Northbound has no date/time fact: its schema and prompt must be byte-identical to before, so accepted
    extractions (W6/W8) and cached answers stay valid."""
    c = load_contract(NORTHBOUND)
    assert set(_claim_item(c)["required"]) == {"type", "value", "unit"}
    assert "when" not in _prompt(c)


def test_a_datetime_fact_gets_a_when_field_and_instructions():
    c = load_contract(NORTHBOUND)
    f = c.facts[0].model_copy(update={"id": "departs_at", "unit": "datetime", "sources": []})
    c = c.model_copy(update={"facts": [*c.facts, f]})
    item = _claim_item(c)
    assert "when" in item["required"] and item["properties"]["value"]["type"] == ["number", "null"]
    assert "ISO 8601" in _prompt(c)


def test_a_measured_datetime_makes_a_fact_temporal_without_the_contract_saying_so():
    """The sealed contracts never declared unit: datetime. The measurement decides, not the authoring."""
    from semaudit.extract.messages import observed_temporal
    s = _story([]).model_copy(update={"truth": {}, "snapshots": [
        {"at": "2026-11-01T09:00:00+00:00", "truth": {"departs_at@f": TRUTH, "units_left": 2}}]})
    assert observed_temporal([s]) == {"departs_at"}
    c = load_contract(NORTHBOUND)
    f = c.facts[0].model_copy(update={"id": "departs_at", "unit": "local time", "sources": []})
    c = c.model_copy(update={"facts": [*c.facts, f]})
    assert set(_claim_item(c)["required"]) == {"type", "value", "unit"}            # undeclared, unmeasured
    item = extraction_schema(c, {"departs_at"})["properties"]["messages"]["items"]["properties"]["claims"]["items"]
    assert "when" in item["required"] and "ISO 8601" in _prompt(c, {"departs_at"})
    assert "when" not in _prompt(c, {"not_a_fact"})                                # only the contract's facts


def test_northbound_captures_measure_no_datetime_fact():
    import pytest
    from semaudit.bench import judge
    from semaudit.extract.messages import observed_temporal
    run = Path(__file__).resolve().parents[1] / "runs/e2e-2"
    if not (run / "episodes/2.4").exists():
        pytest.skip("needs runs/e2e-2, the recorded Northbound demo run (10 MB of captures, kept out of git); these tests check facts of that one run")
    assert observed_temporal(judge.stories_for(run, "2.4", load_contract(NORTHBOUND)).values()) == set()


# ---- displayed precision (a rounded figure matches what rounds to it)
def test_a_rounded_claim_matches_within_half_its_step():
    from semaudit.relate.claims import compare
    assert compare({"value": 1200000, "precision": 100000}, 1184000) == "match"
    assert compare({"value": 1200000, "precision": 100000}, 1260000) == "mismatch"
    assert compare({"value": 250000, "precision": 1000}, 250400) == "match"
    assert compare({"value": 250000, "precision": 1000}, 253000) == "mismatch"
    assert compare({"value": 1200000}, 1184000) == "mismatch"          # no precision recorded: exact, as before


def test_two_shown_figures_agree_at_the_coarser_step_from_either_side():
    from semaudit.relate.claims import compare, precision
    exact, rounded = {"value": 1184000, "precision": 1}, {"value": 1200000, "precision": 100000}
    assert compare(exact, rounded["value"], precision(rounded)) == "match"
    assert compare(rounded, exact["value"], precision(exact)) == "match"
    assert compare({"value": 24500, "precision": 1}, 32500, precision({"value": 32500, "precision": 1})) == "mismatch"


def test_precision_enters_the_schema_and_prompt_only_when_a_fact_asks_for_it():
    from semaudit.contract.schema import Fact
    from semaudit.extract.messages import _claim_schema, _prompt
    c = _contract_with([Fact(id="amount")])
    assert "precision" not in _claim_schema(c)["properties"] and "precision" not in _prompt(c)
    c = _contract_with([Fact(id="amount", match="displayed")])
    assert "precision" in _claim_schema(c)["required"] and "`precision`" in _prompt(c)


def _contract_with(facts):
    from semaudit.contract.schema import Contract
    return Contract(rules=[], decisions=[], features=[], rubric="r", facts=facts)


def test_seconds_the_message_states_are_compared_even_when_they_are_zero():
    """Audit E-03: precision is read from the text, not the value. "14:05:00" states the second."""
    truth = "2026-11-03T14:05:30+01:00"
    assert compare({"when": "2026-11-03T14:05"}, truth) == MATCH               # states the minute only
    assert compare({"when": "2026-11-03T14:05:00"}, truth) == MISMATCH         # states :00, truth is :30
    assert compare({"when": "2026-11-03T14:05:00+01:00"}, truth) == MISMATCH   # a zone's colon is not seconds
    assert compare({"when": "2026-11-03T14:05+01:00"}, truth) == MATCH
    assert compare({"when": "2026-11-03T14:05:30Z"}, "2026-11-03T14:05:30.4+00:00") == MATCH  # to the second
