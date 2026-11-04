"""A match_oracle rule is checked against the oracle it names (`check.oracle`), not the fact's first source.

Found on Medusa v2.17.2 (2026-11-04): `tax_total` read from the order, the cart and an expected-value oracle, in
that order. The rule "VAT is charged at the configured rate" named the expected value, but the claim was compared
with the first source that read, the store's own cart. The page and the cart were wrong in the same way, so the
rule passed on the release that undercharged VAT for every shopper. The validator already required the named
oracle to exist; nothing evaluated with it.
"""
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from semaudit.contract.schema import Fact, FactSource
from semaudit.relate.rules import eval_match_oracle
from semaudit.story.build import snapshot
from semaudit.story.episode import OracleReading
from semaudit.story.model import Event, Extraction, Story

AT = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)
TAX = Fact(id="tax_total", sources=[FactSource(oracle="cart", field="tax_total"),
                                    FactSource(oracle="expected", field="tax_total")])


def _reading(values):
    return OracleReading(status="ok", values=values)


def _story(shown, readings):
    contract = SimpleNamespace(facts=[TAX], features=[])
    x = Extraction(message_kind="information", decision="none", action="none", strength="inform",
                   urgency_cue="none", explains_own_tradeoff=False,
                   claims=[{"type": "tax_total", "value": shown, "unit": "EUR"}])
    return Story(id="s", release="r", persona="p", snapshots=[snapshot(AT, readings, contract)],
                 events=[Event(id="e1", at=AT + timedelta(seconds=1), kind="message", feature="core",
                               text=f"Taxes €{shown}", extraction=x)])


def _status(rule, story):
    return [e.status for e in eval_match_oracle(rule, story, SimpleNamespace(facts=[TAX]))]


def test_a_rule_naming_the_expected_value_catches_a_page_that_agrees_with_a_wrong_record():
    s = _story(2.5, {"cart": _reading({"tax_total": 2.5}), "expected": _reading({"tax_total": 5.0})})
    vs_expected = SimpleNamespace(id="R10", check={"claims": ["tax_total"], "oracle": "expected"})
    vs_record = SimpleNamespace(id="R1", check={"claims": ["tax_total"], "oracle": "cart"})
    assert _status(vs_expected, s) == ["violated"]
    assert _status(vs_record, s) == ["passed"]
    note = eval_match_oracle(vs_expected, s, SimpleNamespace(facts=[TAX]))[0].note
    assert "(expected) 5.0" in note


def test_a_rule_naming_no_oracle_keeps_the_first_source():
    s = _story(2.5, {"cart": _reading({"tax_total": 2.5}), "expected": _reading({"tax_total": 5.0})})
    assert _status(SimpleNamespace(id="R", check={"claims": ["tax_total"]}), s) == ["passed"]


def test_a_named_oracle_that_did_not_read_is_unverifiable_not_a_pass_from_another_source():
    s = _story(2.5, {"cart": _reading({"tax_total": 2.5})})
    rule = SimpleNamespace(id="R10", check={"claims": ["tax_total"], "oracle": "expected"})
    assert _status(rule, s) == []


def test_a_list_of_named_oracles_fails_when_either_disagrees():
    s = _story(2.5, {"cart": _reading({"tax_total": 2.5}), "expected": _reading({"tax_total": 5.0})})
    rule = SimpleNamespace(id="R", check={"claims": ["tax_total"], "oracle": ["cart", "expected"]})
    assert _status(rule, s) == ["violated"]


def test_the_plain_truth_is_unchanged_so_extraction_and_reports_see_the_same_state():
    snap = snapshot(AT, {"cart": _reading({"tax_total": 2.5}), "expected": _reading({"tax_total": 5.0})},
                    SimpleNamespace(facts=[TAX], features=[]))
    assert snap["truth"] == {"tax_total": 2.5}
    assert snap["by_oracle"] == {"tax_total": {"cart": 2.5, "expected": 5.0}}
