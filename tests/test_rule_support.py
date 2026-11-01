"""What the rule engine can evaluate, and what happens to a rule it cannot (relate/rules.py::engine_support).

An owner writes rules in their own words; a contract may name a check verb the engine has no code for. Such a rule
must never be passed over in silence: the engine skips it explicitly, the review reports it as not measured (so the
outcome cannot be ship), the contract review page says so, and reader mode, where the model judges every rule's
text, still gives the rule to the model. Built generically: no app vocabulary in the core."""
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from semaudit.bench import judge  # noqa: E402
from semaudit.contract.approve import hashed_content  # noqa: E402
from semaudit.contract.review import evaluated_by  # noqa: E402
from semaudit.contract.schema import Condition, ExceptionRule, Rule, load_contract  # noqa: E402
from semaudit.contract.validate import validate  # noqa: E402
from semaudit.decide import reader  # noqa: E402
from semaudit.relate.rules import engine_support, evaluate, unevaluable_rules  # noqa: E402
from semaudit.report.review import measurement, outcome_of  # noqa: E402
from semaudit.story.model import Event, Extraction, Story  # noqa: E402

NB = load_contract(ROOT / "examples/northbound/contract")
T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def rule(id="X1", kind="universal", **kw) -> Rule:
    return Rule(id=id, kind=kind, text=f"rule {id} as the owner wrote it", **kw)


SUMS = rule("X3", check={"must": "sums_to_own_total", "identities": ["a + b == total"]})
LIMIT = rule("X8", kind="load", count={"channels": ["email"], "min": 1, "max": 1, "window_hours": 1})


def with_rules(*rules):
    return NB.model_copy(update={"rules": list(rules)})


# ---- engine_support: one answer per rule shape ----

def test_every_rule_of_the_northbound_contract_runs_in_full():
    assert {r.id: engine_support(r) for r in NB.rules} == {r.id: (True, None) for r in NB.rules}


def test_a_verb_the_engine_has_no_code_for_does_not_run_and_says_so():
    assert engine_support(SUMS) == (False, "check verb 'sums_to_own_total' is not built in the rule engine")


def test_a_check_with_several_verbs_does_not_run():
    runs, gap = engine_support(rule(check={"must": ["match_oracle", "match_persona"], "claims": ["x"]}))
    assert not runs and "2 verbs (match_oracle, match_persona)" in gap


def test_a_known_verb_without_the_keys_it_reads_does_not_run():
    runs, gap = engine_support(rule(check={"must": "match_oracle", "oracle": "order"}))
    assert not runs and "needs claims" in gap
    runs, gap = engine_support(rule(check={"must": "match_charge", "claims": ["x"]}))
    assert not runs and "needs charge" in gap


def test_a_rule_with_no_verb_runs_only_as_a_message_kind_rule():
    assert engine_support(rule(applies_to={"message_kind": "retrospective"})) == (True, None)
    assert engine_support(rule())[0] is False


def test_a_conditional_rule_needs_a_decision_and_conditions_the_engine_can_test():
    p1 = next(r for r in NB.rules if r.kind == "conditional")
    assert engine_support(p1) == (True, None)
    assert engine_support(rule(kind="conditional", applies_to={"claims": ["order_total"]}))[0] is False
    unknown_test = p1.model_copy(deep=True)
    unknown_test.exceptions[0].conditions.append(Condition(id="z", kind="data", test="summary_adds_up",
                                                           params={"rule": "X3"}))
    runs, gap = engine_support(unknown_test)
    assert not runs and "data test 'summary_adds_up' is not built" in gap
    unknown_field = p1.model_copy(deep=True)
    unknown_field.exceptions[0].conditions.append(Condition(id="z", kind="judged", field="labels_missing_parts"))
    runs, gap = engine_support(unknown_field)
    assert not runs and "judged field 'labels_missing_parts'" in gap


def test_a_load_rule_with_a_minimum_runs_for_its_maximum_and_reports_the_minimum():
    runs, gap = engine_support(LIMIT)
    assert runs and gap.startswith("partly:") and "min" in gap
    assert engine_support(rule(kind="load", count={"channels": ["email"], "window_hours": 1}))[0] is False


# ---- evaluate: an unsupported rule is skipped, every other rule still runs ----

def _story() -> Story:
    x = Extraction(message_kind="information", decision="none", action="none", strength="inform",
                   urgency_cue="none", explains_own_tradeoff=False,
                   claims=[{"type": "total", "value": 10.0, "unit": "USD"}])
    page = Event(id="m1", at=T0, kind="message", feature="core", surface="page", text="Total $10.00", extraction=x)
    mail = Event(id="m2", at=T0, kind="message", feature="core", surface="email", text="Total $12.00",
                 extraction=x.model_copy(update={"claims": [{"type": "total", "value": 12.0, "unit": "USD"}]}))
    return Story(id="s", release="r", persona="p", events=[page, mail])


def test_evaluate_skips_an_unsupported_rule_and_still_runs_the_others():
    agree = rule("X2", check={"must": "agree_across_surfaces", "claims": ["total"]})
    c = with_rules(SUMS, agree, rule("X9", kind="conditional", applies_to={"claims": ["total"]}))
    entries = evaluate(_story(), c, interpret=None)
    assert {e.rule for e in entries} == {"X2"}
    assert {e.status for e in entries} == {"violated"}          # the supported rule still finds the disagreement


# ---- the review: not measured, never a pass ----

def test_rules_mode_lists_every_rule_it_does_not_fully_evaluate_in_contract_order():
    rel = SimpleNamespace(complete=True, not_measured={})
    c = with_rules(LIMIT, rule("X1", check={"must": "match_oracle", "claims": ["total"], "oracle": "o"}), SUMS)
    m = measurement(rel, rel, c)
    assert m["complete"] is False
    assert [x["rule"] for x in m["rules_not_measured"]] == ["X8", "X3"]
    assert m["rules_not_measured"][0]["reason"].startswith("partly:")
    assert m["rules_not_measured"][1]["reason"].startswith("not evaluated: check verb")
    assert unevaluable_rules(c) == m["rules_not_measured"]


def test_reader_mode_measures_every_rule_because_the_model_judges_each_rules_text():
    rel = SimpleNamespace(complete=True, not_measured={})
    m = measurement(rel, rel, with_rules(SUMS, LIMIT), reader=True)
    assert m == {"complete": True, "base": {}, "head": {}}


def test_the_outcome_names_unevaluated_rules_and_keeps_the_persona_reason_unchanged():
    approved = {"complete": True, "pending": []}
    out = outcome_of("ship", {"complete": False, "base": {}, "head": {},
                              "rules_not_measured": [{"rule": "X3", "reason": "r"}]}, approved)
    assert out["recommendation"] == "not_measurable"
    assert out["reason"] == "1 rule(s) are not fully evaluated in this mode; see measurement"
    persons = outcome_of("ship", {"complete": False, "base": {}, "head": {"p": ["step 2 failed"]}}, approved)
    bare = outcome_of("ship", False, approved)
    # stored reviews carry this exact text, and verify-report re-derives it: it must not move
    assert persons["reason"] == bare["reason"] == "some personas or surfaces could not be measured; see measurement"


# ---- reader mode: the model sees every rule ----

def test_the_reader_is_given_every_rule_including_ones_the_engine_cannot_check():
    sent = judge.render_contract(with_rules(SUMS, LIMIT))["rules"]
    assert [r["id"] for r in sent] == ["X3", "X8"]
    assert sent[0]["text"] == SUMS.text and sent[0]["check"]["must"] == "sums_to_own_total"


def test_a_reader_issue_under_an_unbuilt_figure_rule_is_factual_like_the_built_ones():
    assert reader._layer(SUMS) == "factual"
    assert reader._layer(rule(check={"must": "match_oracle", "claims": ["x"]})) == "factual"
    assert reader._layer(rule(check={"must": "precondition_holds_at_shown_time"})) == "release"
    assert reader._layer(rule(kind="conditional", applies_to={"claims": ["x"]})) == "release"


# ---- the contract: loads, validates and reads the way the owner wrote it ----

def test_a_rule_may_name_two_oracles_and_each_must_exist():
    o = NB.oracles[0].id
    ok = with_rules(rule(check={"must": "rate_applied", "oracle": [o, o]}))
    bad = with_rules(rule(check={"must": "rate_applied", "oracle": [o, "nowhere"]}))
    assert not [p for p in validate(ok) if "oracle" in p]
    assert [p for p in validate(bad) if "nowhere" in p] == ["rule X1 check: unknown oracle 'nowhere'"]


def test_a_conditions_params_are_kept_and_an_empty_one_leaves_its_hash_unchanged():
    plain = Condition(id="a", kind="data", test="time_until", context_field="d", hours=24)
    assert "params" not in hashed_content(plain)            # approvals pinned before the field existed still hold
    assert hashed_content(plain) == {"id": "a", "kind": "data", "test": "time_until", "field": None, "hours": 24.0,
                                     "context_field": "d", "claim": None, "oracle": None}
    with_args = Condition(id="b", kind="data", test="state_unset", params={"state": ["address"], "any": True})
    assert hashed_content(with_args)["params"] == {"state": ["address"], "any": True}
    ex = ExceptionRule(id="E", conditions=[with_args])
    assert ex.model_dump(mode="json")["conditions"][0]["params"] == {"state": ["address"], "any": True}


def test_the_contract_review_page_says_when_the_engine_does_not_check_a_rule():
    assert evaluated_by(SUMS).startswith("not checked by the rule engine (check verb 'sums_to_own_total'")
    assert "Reader mode judges the rule's text" in evaluated_by(SUMS)
    assert "partly" in evaluated_by(LIMIT)
    agree = rule(check={"must": "agree_across_surfaces", "claims": ["total"]})
    assert evaluated_by(agree) == "code: each total claim reads the same on every surface, in the same state"
