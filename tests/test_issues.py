"""W9 (no model): severity, confidence and verification are independent; the policy reads all three."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pytest  # noqa: E402

from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.decide.issues import Issue, Occurrence, severity_of  # noqa: E402
from semaudit.relate.rules import Entry  # noqa: E402
from semaudit.verify.steps import confidence_of, verification_status  # noqa: E402

C = load_contract(ROOT / "examples" / "northbound" / "contract")
PASS = {"result": "pass", "detail": ""}
NOT_RUN = {"result": "not_run", "detail": ""}
FAIL = {"result": "fail", "detail": ""}
NA = {"result": "not_applicable", "detail": ""}


def issue(rule="P2", meta=None, conditions=()):
    e = Entry(rule, "s", "violated", label="unexplained_tradeoff", conditions=conditions, meta=meta or {})
    return Issue(id="I", signature=(), rule=rule, rule_kind=C.rule(rule).kind, layer="release",
                 label=e.label, occurrences=[Occurrence("maya", "x", ["a"], e, "before_decision")],
                 severity={}, why="")


def steps(**over):
    base = {"reproduced": PASS, "evidence_linked": PASS, "cross_model": PASS, "defended": PASS, "oracle_checked": NA}
    return {**base, **over}


def occ(persona, timing):
    return Occurrence(persona, "x", ["a"], Entry("P2", "s", "violated"), timing)


def test_severity_is_the_rules_own_level_and_moves_only_with_it():
    r = C.rule("P2")
    one = severity_of(r, [occ("maya", "before_decision")])
    many = severity_of(r, [occ(p, "before_decision") for p in ("maya", "lena", "kai", "raj")])
    assert one["level"] == many["level"] == r.severity == "critical"    # test-persona count never moves it
    assert many["factors"]["tested_personas"] == 4
    minor = r.model_copy(update={"severity": "minor"})                  # the owner changes the rule
    assert severity_of(minor, [occ("maya", "before_decision")])["level"] == "minor"
    i = issue()
    s = steps()
    assert confidence_of(i, s, C) == confidence_of(i, s, C) and verification_status(s)["status"] == "verified"


def test_a_coherence_rule_sets_its_level_per_label():
    r = C.rule("P2")
    def lab(label):
        return severity_of(r, [Occurrence("maya", "x", ["a"], Entry("P2", "s", "violated", label=label),
                                          "before_decision")])
    assert lab("conflict")["level"] == "critical"                       # owner ruling Oct 27
    assert lab("unexplained_tradeoff")["level"] == "major"
    assert lab("unexplained_tradeoff")["factors"]["set_by"] == "severity_by_label"
    assert severity_of(r.model_copy(update={"severity_by_label": {}}), [occ("maya", "before_decision")])["level"] \
        == r.severity                                                   # without the map, the rule's own level


def test_only_a_coherence_rule_may_set_a_level_per_label():
    with pytest.raises(ValueError, match="only for coherence rules"):
        C.rule("P1").model_validate({**C.rule("P1").model_dump(), "severity_by_label": {"conflict": "minor"}})


def test_before_decision_count_uses_only_qualifying_occurrences():
    f = severity_of(C.rule("P2"), [occ("maya", "before_decision"), occ("lena", "after_decision")])["factors"]
    assert (f["tested_personas"], f["tested_personas_before_decision"], f["tested_personas_after_decision"]) == (2, 1, 1)


def test_confidence_moves_alone_with_unknown_validity():
    s = steps()
    known, unknown = issue(meta={"unknown_validity": False}), issue(meta={"unknown_validity": True})
    assert confidence_of(known, s, C)["level"] == "high"
    assert confidence_of(unknown, s, C)["level"] == "medium"
    assert verification_status(s)["status"] == "verified"                 # verification unchanged
    assert severity_of(C.rule("P2"), [occ("maya", "before_decision")])["level"] == "critical"   # severity unchanged


def test_verification_moves_alone_when_reproduction_did_not_run():
    i = issue()
    full, partial = steps(), steps(reproduced=NOT_RUN)
    assert verification_status(full)["status"] == "verified"
    assert verification_status(partial)["status"] == "partially_verified"
    assert confidence_of(i, full, C) == confidence_of(i, partial, C)      # confidence does not read reproduction


def test_failed_verification_kinds():
    assert verification_status(steps(reproduced=FAIL))["reason"] == "not_reproducible"
    assert verification_status(steps(evidence_linked=FAIL))["reason"] == "evidence_unresolved"
    assert verification_status(steps(cross_model=FAIL, defended=FAIL))["reason"] == "disputed"
    v = verification_status(steps(cross_model=FAIL))
    assert v["status"] == "partially_verified" and "cross_model" in v["reason"]
    assert verification_status({k: NOT_RUN for k in steps()} | {"oracle_checked": NA})["status"] == "unverified"


def test_disagreement_or_successful_defense_makes_confidence_low():
    i = issue()
    assert confidence_of(i, steps(cross_model=FAIL), C)["level"] == "low"
    assert confidence_of(i, steps(defended=FAIL), C)["level"] == "low"
    assert confidence_of(i, steps(cross_model=NOT_RUN), C)["level"] == "medium"


def test_measured_vs_interpreted_evidence():
    from semaudit.verify.steps import evidence_kind
    assert evidence_kind(issue("U3"), C) == "measured"
    assert evidence_kind(issue("P2"), C) == "interpreted"
    assert evidence_kind(issue("P1", conditions=(("a", "not_met"),)), C) == "measured"
    assert evidence_kind(issue("P1", conditions=(("c", "not_met"),)), C) == "interpreted"


def test_policy_recommendation_follows_the_three_fields():
    p = C.policy
    rec = lambda s, c, v: p.evaluate([{"severity": s, "confidence": c, "verification": v}])[0].recommendation  # noqa
    assert rec("critical", "high", "verified") == "hold"
    assert rec("critical", "low", "verified") == "needs_owner_review"         # confidence alone moves it
    assert rec("critical", "high", "partially_verified") == "needs_owner_review"   # verification alone
    assert rec("major", "high", "verified") == "ship_with_notes"              # severity alone


def test_same_family_corroboration_is_capped_at_medium():
    i, s = issue(), steps()
    assert confidence_of(i, s, C)["level"] == "high"
    capped = confidence_of(i, s, C, reduced_independence=True)
    assert capped["level"] == "medium" and any("capped at medium" in b for b in capped["basis"])
    assert confidence_of(i, steps(defended=FAIL), C, reduced_independence=True)["level"] == "low"


class _FailingRouter:
    roles = {"extractor": {"model": "m-a-1"}, "cross_checker_extract": {"model": "m-a-2"}}

    def complete(self, *a, **k):
        from semaudit.models.router import ModelError
        raise ModelError("budget exhausted: spent $1.0000 of $1.0")


def test_a_model_failure_during_verification_is_not_a_verified_issue(tmp_path):
    """Budget exhaustion or an API error mid-verification must surface (review exits 2), never pass."""
    import pytest

    from semaudit.models.router import ModelError
    from semaudit.story.model import Story
    from semaudit.verify.steps import verify
    i = issue()
    i.occurrences[0].entry.meta["pairs"] = []
    with pytest.raises(ModelError):
        verify(i, {"maya": Story(id="x", release="2.4", persona="maya", events=[])}, {}, tmp_path, C,
               _FailingRouter(), repro=None)
    assert i.verification == {}                    # nothing was recorded as verified


# ---------- the defense is adjudicated against what was measured ----------
from datetime import UTC, datetime  # noqa: E402

from semaudit.story.model import Event, Extraction, Story  # noqa: E402
from semaudit.verify.steps import adjudicate  # noqa: E402

_AT = datetime(2026, 11, 2, 10, 3, tzinfo=UTC)
_URGE = Extraction(message_kind="directive", decision="when_to_book", action="book_now", strength="urge",
                   urgency_cue="seats", explains_own_tradeoff=True, claims=[])


def _p1_issue(conditions):
    e = Entry("P1", "fl", "violated", conditions=conditions)
    return Issue(id="I", signature=(), rule="P1", rule_kind="conditional", layer="release", label=None,
                 occurrences=[Occurrence("hana", "x", ["fl"], e, "before_decision")], severity={}, why="")


def _defense(ground, **kw):
    d = {"strongest_defense": "x", "ground": ground, "exception_conditions_met": [], "disputed_readings": [],
         "reconciling_event_id": "", "addresses_actions": [], "defense_succeeds": True}
    return d | kw


_STORY = Story(id="s", release="2.4", persona="hana", events=[
    Event(id="fl", at=_AT, kind="message", feature="fare_lock", text="Book now", extraction=_URGE)])


def test_a_defense_claiming_a_measured_condition_is_overruled():
    i = _p1_issue((("a", "not_met"), ("b", "met"), ("c", "met"), ("scope", "met"), ("expiry", "met")))
    stands, why = adjudicate(_defense("exception_applies", exception_conditions_met=["a", "b", "c"]),
                             i, i.occurrences[0], _STORY, C, None)
    assert not stands and "a met; measured not_met" in why


def test_a_disputed_reading_stands_only_where_the_models_disagree():
    i = _p1_issue(())
    soften = _defense("extraction_wrong", disputed_readings=[{"event_id": "fl", "field": "strength", "value": "suggest"}])
    agree = {"fl": _URGE}
    assert not adjudicate(soften, i, i.occurrences[0], _STORY, C, agree)[0]               # both read 'urge'
    split = {"fl": _URGE.model_copy(update={"strength": "suggest"})}
    assert adjudicate(soften, i, i.occurrences[0], _STORY, C, split)[0]                    # the models disagree
    restate = _defense("extraction_wrong", disputed_readings=[{"event_id": "fl", "field": "strength", "value": "urge"}])
    assert not adjudicate(restate, i, i.occurrences[0], _STORY, C, agree)[0]


def test_no_ground_or_no_success_means_the_issue_holds():
    i = _p1_issue(())
    assert not adjudicate(_defense("none"), i, i.occurrences[0], _STORY, C, None)[0]
    assert not adjudicate(_defense("timing", defense_succeeds=False), i, i.occurrences[0], _STORY, C, None)[0]
    # P1 with only measured conditions is applied by code: a scope argument is overruled ...
    assert not adjudicate(_defense("rule_does_not_apply"), i, i.occurrences[0], _STORY, C, None)[0]
    # ... while a judgement-based rule (P2's label) leaves a scope argument standing
    p2 = issue()
    assert adjudicate(_defense("rule_does_not_apply"), p2, p2.occurrences[0], _STORY, C, None)[0]


def test_a_scope_argument_against_a_code_applied_rule_is_overruled():
    e = Entry("P3", "story", "violated")
    i = Issue(id="I", signature=(), rule="P3", rule_kind="load", layer="release", label=None,
              occurrences=[Occurrence("family", "x", ["a"], e, "after_decision")], severity={}, why="")
    stands, why = adjudicate(_defense("rule_does_not_apply"), i, i.occurrences[0], _STORY, C, None)
    assert not stands and "applied by code" in why


def test_the_policy_names_the_issues_that_made_its_row_fire():
    p = C.policy
    xs = [{"severity": "major", "confidence": "medium", "verification": "verified"},
          {"severity": "critical", "confidence": "medium", "verification": "verified"},
          {"severity": "critical", "confidence": "low", "verification": "partially_verified"}]
    row, idx = p.evaluate(xs)
    assert row.recommendation == "hold" and p.fired_by(row, xs) == [1]     # only the verified critical one holds it
    row, _ = p.evaluate(xs[2:])
    assert row.recommendation == "needs_owner_review" and p.fired_by(row, xs[2:]) == [0]
    row, _ = p.evaluate(xs[:1])
    assert row.otherwise and p.fired_by(row, xs[:1]) == []                 # a catch-all names no issue


class _Roles:
    def __init__(self, **models):
        from semaudit.models.router import DEFAULT_ROLES
        self.roles = {r: dict(spec) for r, spec in DEFAULT_ROLES.items()}
        for role, model in models.items():
            self.roles[role]["model"] = model


def test_model_family_ignores_the_provider_prefix_and_fails_closed():
    from semaudit.verify.steps import model_family, one_family
    assert model_family({"model": "meta-models/muse-spark-open-1026"}) == model_family({"model": "muse-spark-1.3"})
    assert model_family({"model": "some-new-model"}) is None
    assert one_family(_Roles())                                                   # today: all Muse Spark
    open_ = "meta-models/muse-spark-open-1026"                                    # Muse Spark Open is the same family
    assert one_family(_Roles(cross_checker_extract=open_, cross_checker_interpret=open_, defender=open_))
    other = "claude-sonnet-5-5"
    assert one_family(_Roles(cross_checker_extract=other))                        # interpretation still same family
    assert one_family(_Roles(cross_checker_extract=other, cross_checker_interpret=other,
                             defender="unknown-model"))                           # unrecognised: not independent
    assert not one_family(_Roles(cross_checker_extract=other, cross_checker_interpret=other, defender=other))


# ---------- a figure's fact can be disputed (Spree 6.0.4, 2026-11-12) ----------
# The admin order page showed "$955.79" (the payment) just above the "Taxes" heading; the reader typed it as
# tax_total, so tax "$955.79" disagreed with "$70.80" everywhere else. The defender said so, but the only fields it
# could dispute were a message's kind/decision/action/strength, so the false alarm stood. A "claim" dispute now
# stands where the other model does not read the issue's fact on that message and the defense says it is not that
# fact either. They need not agree on what it is instead: in the measured run the other model read the payment as
# order_total and the defender as payment_amount.

def _read(*claims):
    return Extraction(message_kind="information", decision="none", action="none", strength="inform",
                      urgency_cue="none", explains_own_tradeoff=False,
                      claims=[{"type": t, "value": v, "unit": "USD"} for t, v in claims])


_PAY = Story(id="s", release="after", persona="lena", events=[
    Event(id="admin#2", at=_AT, kind="message", feature="admin", text="$955.79", extraction=_read(("tax_total", 955.79)))])


def _fact_issue(fact="tax_total"):
    e = Entry("U1", "admin#2", "violated", meta={"fact": fact})
    return Issue(id="I", signature=(), rule="U1", rule_kind="universal", layer="release", label=None,
                 occurrences=[Occurrence("lena", "x", ["admin#2"], e, "after_decision")], severity={}, why="")


def _claim_defense(value, event_id="admin#2"):
    return _defense("extraction_wrong", disputed_readings=[{"event_id": event_id, "field": "claim", "value": value}])


def test_a_figure_dispute_stands_when_the_other_model_reads_the_figure_as_what_the_defense_says():
    i = _fact_issue()
    other = {"admin#2": _read(("payment_amount", 955.79))}
    stands, why = adjudicate(_claim_defense("payment_amount"), i, i.occurrences[0], _PAY, C, other)
    assert stands and "tax_total vs payment_amount" in why


def test_a_figure_dispute_is_overruled_when_both_models_share_the_misreading():
    i = _fact_issue()
    same = {"admin#2": _read(("tax_total", 955.79))}
    assert not adjudicate(_claim_defense("payment_amount"), i, i.occurrences[0], _PAY, C, same)[0]
    # the other model also reads the issue's fact on the message (beside another): still a shared reading
    both = {"admin#2": _read(("tax_total", 955.79), ("payment_amount", 955.79))}
    assert not adjudicate(_claim_defense("payment_amount"), i, i.occurrences[0], _PAY, C, both)[0]


def test_a_figure_dispute_stands_when_neither_other_reading_is_the_issues_fact_whatever_each_calls_it():
    i = _fact_issue()
    other = {"admin#2": _read(("order_total", 955.79))}           # the Spree run: Claude said order_total ...
    stands, why = adjudicate(_claim_defense("payment_amount"), i, i.occurrences[0], _PAY, C, other)
    assert stands and "tax_total vs order_total" in why and "(payment_amount)" in why   # ... the defender payment
    assert adjudicate(_claim_defense("order_total"), i, i.occurrences[0], _PAY, C, other)[0]
    # "none": no figure at all, by either side
    assert adjudicate(_claim_defense("none"), i, i.occurrences[0], _PAY, C, {"admin#2": _read()})[0]
    assert adjudicate(_claim_defense("none"), i, i.occurrences[0], _PAY, C, other)[0]
    # the defense must name something: an empty value is not a side
    assert not adjudicate(_claim_defense(" "), i, i.occurrences[0], _PAY, C, other)[0]


def test_a_figure_dispute_without_a_second_reading_or_restating_the_reading_is_overruled():
    i = _fact_issue()
    other = {"admin#2": _read(("payment_amount", 955.79))}
    assert not adjudicate(_claim_defense("payment_amount"), i, i.occurrences[0], _PAY, C, None)[0]
    assert not adjudicate(_claim_defense("tax_total"), i, i.occurrences[0], _PAY, C, other)[0]
    assert not adjudicate(_claim_defense("payment_amount", "nowhere"), i, i.occurrences[0], _PAY, C, other)[0]
    # the dispute must be about the issue's own fact: this message's reading never stated order_total
    j = _fact_issue("order_total")
    assert not adjudicate(_claim_defense("payment_amount"), j, j.occurrences[0], _PAY, C, other)[0]


def test_the_defender_is_shown_the_figures_read_and_may_dispute_them():
    from semaudit.verify import steps as S
    assert "claim" in S.DEFENSE_SCHEMA["properties"]["disputed_readings"]["items"]["properties"]["field"]["enum"]
    sent = {}

    class _R:
        roles = {}

        def complete(self, role, messages, **kw):
            import json as _json
            sent["payload"] = _json.loads(messages[1]["content"])
            from types import SimpleNamespace
            return SimpleNamespace(parsed=_claim_defense("payment_amount"))
    i = _fact_issue()
    i.occurrences[0].entry.meta["events"] = ["admin#2"]
    ok, why = S._defend_one(i, i.occurrences[0], _PAY, C, _R(), fresh=False,
                            cross={"admin#2": _read(("payment_amount", 955.79))})
    assert sent["payload"]["cited_messages"][0]["reading"]["claims"][0]["type"] == "tax_total"
    assert not ok and "the defense takes the other side" in why          # the defense stands: the issue does not hold


def test_a_figure_dispute_that_stands_with_a_second_model_disagreeing_fails_the_issue():
    v = verification_status({"reproduced": {"result": "pass"}, "evidence_linked": {"result": "pass"},
                             "cross_model": {"result": "fail"}, "defended": {"result": "fail"},
                             "oracle_checked": {"result": "pass"}})
    assert (v["status"], v["reason"]) == ("failed", "disputed")


def test_the_cross_check_re_derives_a_figure_issue_only_for_the_same_fact(monkeypatch):
    # Spree 6.0.4: the other model read the payment "$955.79" as item_total; that broke U2 for item_total on the
    # same message, which the cross-check counted as re-deriving the tax_total issue
    from semaudit.relate import rules as R
    from semaudit.verify import steps as S
    i = _fact_issue()
    i.occurrences[0].entry.meta["events"] = ["admin#2"]
    monkeypatch.setattr(S, "extract_unique", lambda cited, *a, **k: {S.message_key(e): _read(("item_total", 955.79))
                                                                     for e in cited})
    monkeypatch.setattr(S, "model_interpreter", lambda *a, **k: None)
    found = {}
    monkeypatch.setattr(R, "evaluate", lambda story, contract, interp: [Entry("U1", "admin#2", "violated",
                                                                              meta={"fact": found["fact"]})])
    found["fact"] = "item_total"
    ok, why = S._cross_one(i, i.occurrences[0], _PAY, C, None, fresh=False)
    assert not ok and "does not produce this violation" in why
    found["fact"] = "tax_total"
    assert S._cross_one(i, i.occurrences[0], _PAY, C, None, fresh=False)[0]
