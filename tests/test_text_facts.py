"""A text fact with no word vocabulary has only a number field in the extraction schema, so a number it holds (a ZIP
code, a "1" from "Qty: 1") is not the fact: it is never checked against the oracle or compared across surfaces.
Spree: 302 of 444 head issues were ship_to read as a number."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from semaudit.relate.claims import checkable, comparable  # noqa: E402

SHIP_TO = SimpleNamespace(id="ship_to", unit="text", key=[], truth_roles=("as_is",))
TOTAL = SimpleNamespace(id="order_total", unit="USD", key=[], truth_roles=("as_is",))


def test_a_number_never_states_a_text_fact():
    assert not checkable({"type": "ship_to", "value": 10011}, SHIP_TO)
    assert not comparable(SHIP_TO, {"type": "ship_to", "value": 10011}, {"type": "ship_to", "value": 1})


def test_a_word_still_states_a_text_fact():
    assert checkable({"type": "ship_to", "value": None, "word": "ny"}, SHIP_TO)


def test_money_facts_are_unchanged():
    assert checkable({"type": "order_total", "value": 48.59}, TOTAL)
    assert comparable(TOTAL, {"type": "order_total", "value": 48.59}, {"type": "order_total", "value": 0})


def test_a_rule_that_checks_only_wordless_text_facts_is_not_measured():
    from semaudit.relate.claims import unmeasurable_rules
    rule = SimpleNamespace(id="U9", check={"claims": ["ship_to"], "must": "match_oracle"})
    money = SimpleNamespace(id="U1", check={"claims": ["order_total", "ship_to"], "must": "match_oracle"})
    c = SimpleNamespace(facts=[SimpleNamespace(**vars(SHIP_TO), words=[]), SimpleNamespace(**vars(TOTAL), words=[])],
                        rules=[rule, money])
    assert [r["rule"] for r in unmeasurable_rules(c)] == ["U9"]


def test_spree_like_contract_review_is_incomplete_when_a_rule_cannot_fire():
    from semaudit.report.review import measurement
    rel = SimpleNamespace(complete=True, not_measured={})
    c = SimpleNamespace(facts=[SimpleNamespace(**vars(SHIP_TO), words=[])],
                        rules=[SimpleNamespace(id="U9", check={"claims": ["ship_to"]})])
    m = measurement(rel, rel, c)
    assert m["complete"] is False and m["rules_not_measured"][0]["rule"] == "U9"
