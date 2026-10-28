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
