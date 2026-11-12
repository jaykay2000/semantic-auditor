"""Declared bases: another form in which the owner accepts a fact's true value being shown (relate/basis.py).

Found on Medusa v2.18.0 (2026-11-05): 129 issues, most of them correct figures in a second form the rules did not
know, such as a line price shown with VAT and after the promotion, or the admin page's tax and total before the
discount. The owner accepted those forms the same day. A basis lets the contract say so, without changing what
the extractor reads. A claim in no declared form must still be a violation, so the tests below check both
directions.
"""
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from semaudit.contract.schema import Fact, FactBasis, FactSource
from semaudit.relate import basis as B
from semaudit.relate.rules import eval_agree_across_surfaces, eval_match_charge, eval_match_oracle
from semaudit.story.build import snapshot
from semaudit.story.episode import OracleReading
from semaudit.story.model import Event, Extraction, Story

AT = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)
LINE = ["checkout", "order_page"]
PRICE = Fact(id="unit_price", sources=[FactSource(oracle="expected", field="unit_price")], bases=[
    FactBasis(id="with_vat", value="unit_price * (1 + tax_rate / 100)", surfaces=LINE, round=0.01),
    FactBasis(id="after_promotion_with_vat", value="unit_price * (1 - promo_percent / 100) * (1 + tax_rate / 100)",
              when="discount_total > 0", surfaces=LINE, round=0.01)])
RATE = Fact(id="tax_rate", sources=[FactSource(oracle="expected", field="tax_rate")])
PROMO = Fact(id="promo_percent", sources=[FactSource(oracle="expected", field="promo_percent")])
DISC = Fact(id="discount_total", sources=[FactSource(oracle="expected", field="discount_total")])
FACTS = [PRICE, RATE, PROMO, DISC]
CONTRACT = SimpleNamespace(facts=FACTS, features=[], state=[])


def _story(shown: list[tuple[str, float]], discount=0.0):
    readings = {"expected": OracleReading(status="ok", values={"unit_price": 10.0, "tax_rate": 25.0,
                                                               "promo_percent": 10, "discount_total": discount})}
    events = []
    for i, (surface, value) in enumerate(shown):
        x = Extraction(message_kind="information", decision="none", action="none", strength="inform",
                       urgency_cue="none", explains_own_tradeoff=False,
                       claims=[{"type": "unit_price", "value": value, "unit": "EUR"}])
        events.append(Event(id=f"e{i}", at=AT + timedelta(seconds=1 + i), kind="message", feature="core",
                            surface=surface, text=f"€{value}", extraction=x))
    return Story(id="s", release="r", persona="p", snapshots=[snapshot(AT, readings, CONTRACT)], events=events)


MATCH_RULE = SimpleNamespace(id="R8", check={"claims": ["unit_price"], "oracle": "expected"})


def _statuses(story):
    return [(e.status, e.meta.get("basis")) for e in eval_match_oracle(MATCH_RULE, story, CONTRACT)]


# ---------- the grammar ----------

def test_a_basis_reads_facts_with_plain_arithmetic():
    assert B.evaluate("p * (1 + r / 100)", {"p": 10, "r": 25}.get) == 12.5
    assert B.names("unit_price * (1 - promo_percent / 100)") == {"unit_price", "promo_percent"}


@pytest.mark.parametrize("expr", ["__import__('os')", "p.real", "p[0]", "p ** 2", "'x'", "lambda: 1", "True"])
def test_anything_outside_the_grammar_is_refused(expr):
    with pytest.raises((ValueError, SyntaxError)):
        B.names(expr)


def test_a_missing_input_makes_the_basis_unavailable_not_zero():
    fact = Fact(id="p", bases=[FactBasis(id="b", value="p * (1 + r / 100)")])
    assert B.values(fact, None, 10.0, {}.get) == []


# ---------- match_oracle ----------

def test_a_price_shown_with_vat_on_a_line_is_accepted_and_says_so():
    assert _statuses(_story([("checkout", 12.5)])) == [("passed", "with_vat")]


def test_the_same_price_on_a_surface_the_basis_does_not_name_is_still_a_violation():
    assert _statuses(_story([("product", 12.5)])) == [("violated", None)]


def test_a_form_that_matches_no_basis_is_still_a_violation():
    for wrong in (12.55, 13.0, 15.63, 11.25):         # nudged, a wrong rate, VAT twice, promotion without its `when`
        assert _statuses(_story([("checkout", wrong)])) == [("violated", None)], wrong


def test_a_basis_with_a_when_applies_only_when_it_holds():
    assert _statuses(_story([("checkout", 11.25)], discount=2.0)) == [("passed", "after_promotion_with_vat")]
    assert _statuses(_story([("checkout", 11.25)], discount=0.0)) == [("violated", None)]


def test_the_truth_itself_needs_no_basis():
    assert _statuses(_story([("checkout", 10.0)])) == [("passed", None)]


def test_the_note_names_the_basis():
    note = eval_match_oracle(MATCH_RULE, _story([("checkout", 12.5)]), CONTRACT)[0].note
    assert "12.5 as with_vat vs true unit_price (expected) 10.0" in note


# ---------- agree_across_surfaces ----------

AGREE = SimpleNamespace(id="R16", check={"claims": ["unit_price"]})


def test_two_surfaces_each_in_a_declared_form_agree():
    entries = eval_agree_across_surfaces(AGREE, _story([("product", 10.0), ("checkout", 12.5)]), CONTRACT)
    assert {e.status for e in entries} == {"passed"}


def test_two_surfaces_disagree_when_one_is_in_no_declared_form():
    entries = eval_agree_across_surfaces(AGREE, _story([("product", 10.0), ("checkout", 13.0)]), CONTRACT)
    assert {e.status for e in entries} == {"violated"}
    assert "13 on checkout" in next(e.note for e in entries if e.subject == "e0")   # the note shows what was shown


# ---------- match_charge ----------

def test_a_shown_charge_in_a_declared_form_matches_what_was_charged():
    rule = SimpleNamespace(id="R15", check={"claims": ["unit_price"], "charge": "unit_price"})
    assert [e.status for e in eval_match_charge(rule, _story([("order_page", 12.5)]), CONTRACT)] == ["passed"]
    assert [e.status for e in eval_match_charge(rule, _story([("order_page", 12.6)]), CONTRACT)] == ["violated"]


# ---------- the contract check ----------

def _problems(fact):
    from semaudit.contract import validate as V
    c = SimpleNamespace(features=[], decisions=[], surfaces=[SimpleNamespace(id="checkout")], oracles=[],
                        facts=[fact, RATE], state=[], personas=[], scenarios=[], rules=[], policy=None,
                        subject=SimpleNamespace(context=[], component_from=None, field=lambda _: None))
    return V.validate(c)


def test_the_contract_check_names_an_unknown_fact_a_bad_expression_and_an_unknown_surface():
    good = Fact(id="unit_price", bases=[FactBasis(id="v", value="unit_price * (1 + tax_rate / 100)",
                                                  surfaces=["checkout"])])
    assert _problems(good) == []
    out = _problems(Fact(id="unit_price", bases=[
        FactBasis(id="a", value="unit_price * vat"),
        FactBasis(id="b", value="unit_price ** 2"),
        FactBasis(id="c", value="tax_rate * 2"),
        FactBasis(id="d", value="unit_price", surfaces=["nowhere"])]))
    assert any("basis a: value reads unknown fact 'vat'" in p for p in out)
    assert any("basis b: value" in p and "not an allowed expression" in p for p in out)
    assert any("basis c: value does not read unit_price itself" in p for p in out)
    assert any("basis d: unknown surface 'nowhere'" in p for p in out)
