"""W13b (no model): the benchmark matcher and adjudication sheet score what the protocol says, and nothing else.

Every test perturbs a known-correct case and asserts the score moves the right way, so a matcher that silently
accepts everything (or nothing) fails here.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.bench.adjudicate import build, kappa  # noqa: E402
from semaudit.bench.findings import Cited, Finding, Findings, Target, Truth, TruthItem, from_review  # noqa: E402
from semaudit.bench.match import evidence_index, jaccard, score  # noqa: E402

REVIEW = json.loads((ROOT / "runs/e2e-2/review-2.3-2.4.json").read_text()) \
    if (ROOT / "runs/e2e-2/review-2.3-2.4.json").exists() else None
DEV = Truth.model_validate(json.loads((ROOT / "bench/dev/northbound-2.4.truth.json").read_text()))

REL = Target(kind="relation", features=["price_watch", "fare_lock"], decision="when_to_book")
EV = Target(kind="event", feature="fare_lock", surface="fare_detail", message_key="fl.banner.urgent")


def truth(*items):
    return Truth(release="t", items=list(items))


def found(*fs):
    return Findings(system="x", release="t", findings=list(fs))


def T(id, personas, rule, target, label=None, kind="issue", pattern=None):
    return TruthItem(id=id, kind=kind, personas=personas, rule=rule, target=target, label=label, pattern=pattern)


def F(id, personas, rule, target, label=None, **kw):
    return Finding(id=id, personas=personas, rule=rule, target=target, label=label, **kw)


def test_relation_target_is_unordered():
    assert Target(kind="relation", features=["b", "a"], decision="d").key() == \
        Target(kind="relation", features=["a", "b"], decision="d").key()
    with pytest.raises(ValueError):
        Target(kind="relation", features=["a", "a"], decision="d")


def test_exact_match_and_each_truth_unit_matched_once():
    s = score(found(F("f1", ["kai"], "P2", REL, "conflict"), F("f2", ["kai"], "P2", REL, "conflict")),
              truth(T("t1", ["kai"], "P2", REL, "conflict")))
    assert (s["tp"], s["fp"], s["fn"]) == (1, 1, 0)


def test_wrong_label_is_a_different_answer():
    s = score(found(F("f", ["kai"], "P2", REL, "unexplained_tradeoff")), truth(T("t", ["kai"], "P2", REL, "conflict")))
    assert (s["tp"], s["fn"]) == (0, 1)
    assert s["label_confusion"] == {"conflict->unexplained_tradeoff": 1}


@pytest.mark.parametrize("change", ["persona", "rule", "target"])
def test_each_identity_field_must_agree(change):
    f = dict(personas=["kai"], rule="P1", target=EV)
    f[{"persona": "personas", "rule": "rule", "target": "target"}[change]] = \
        {"persona": ["omar"], "rule": "U1",
         "target": Target(kind="event", feature="fare_lock", surface="fare_detail", message_key="fl.banner")}[change]
    s = score(found(F("f", **f)), truth(T("t", ["kai"], "P1", EV)))
    assert s["tp"] == 0 and s["fp"] == 1


def test_grouping_is_neutral():
    grouped = score(found(F("g", ["a", "b", "c"], "P1", EV)), truth(*[T(p, [p], "P1", EV) for p in "abc"]))
    split = score(found(*[F(p, [p], "P1", EV) for p in "abc"]), truth(T("t", ["a", "b", "c"], "P1", EV)))
    assert (grouped["tp"], grouped["fp"], grouped["fn"]) == (split["tp"], split["fp"], split["fn"]) == (3, 0, 0)


def test_hitting_a_negative_control_is_a_false_positive_on_its_pattern():
    s = score(found(F("f", ["lena"], "P2", REL, "unexplained_tradeoff")),
              truth(T("nc", ["lena"], "P2", REL, "explained_tradeoff", kind="negative_control",
                      pattern="explained_tradeoff")))
    assert s["fp"] == 1 and s["negative_controls"]["explained_tradeoff"]["false_positives"] == 1
    assert s["unmatched"] == []                       # not double-counted as an unseeded candidate


def test_raising_everything_fails_the_negative_controls():
    t = truth(T("t", ["kai"], "P1", EV), T("nc", ["raj"], "P1", EV, kind="negative_control", pattern="exception"))
    s = score(found(F("f", ["kai", "raj"], "P1", EV)), t)
    assert s["recall"] == 1.0 and s["precision"] == 0.5 and s["negative_controls"]["exception"]["fp_rate"] == 1.0


def test_personas_outside_a_truth_are_not_scored():
    t = Truth(release="t", items=[T("t", ["kai"], "P1", EV)], personas=["kai"])
    s = score(found(F("f", ["kai", "family"], "P1", EV)), t)
    assert (s["tp"], s["fp"]) == (1, 0)


def test_evidence_support_requires_a_verbatim_quote_of_a_real_event():
    ev = {("kai", "e1"): "Only 2 seats left at this price."}
    good = F("g", ["kai"], "P1", EV, cited=[Cited(persona="kai", event_id="e1", quote="Only 2 seats left")])
    para = F("p", ["kai"], "P1", EV, cited=[Cited(persona="kai", event_id="e1", quote="only two seats remain")])
    ghost = F("h", ["kai"], "P1", EV, cited=[Cited(persona="kai", event_id="e9", quote="")])
    none = F("n", ["kai"], "P1", EV)
    empty = F("e", ["kai"], "P1", EV, cited=[Cited(persona="kai", event_id="e1", quote="")])
    ev[("omar", "e1")] = "Only 2 seats left at this price."
    half = F("g2", ["kai", "omar"], "P1", EV, cited=[Cited(persona="kai", event_id="e1", quote="Only 2 seats left")])
    ev[("kai", "a1")] = None                                    # a user action: no text, need only exist
    action = F("a", ["kai"], "P1", EV, cited=[Cited(persona="kai", event_id="a1", quote="")])
    s = score(found(good, para, ghost, none, empty, half, action), truth(), evidence=ev)
    assert s["evidence_support"]["unsupported"] == ["p", "h", "n", "e", "g2"]


def test_jaccard_of_identical_and_disjoint_runs():
    a = found(F("f", ["kai"], "P1", EV))
    b = found(F("f", ["omar"], "P1", EV))
    a.fresh = b.fresh = True
    assert jaccard([a, a, a]) == 1.0 and jaccard([a, b]) == 0.0


def test_stability_refuses_cached_runs():
    a = found(F("f", ["kai"], "P1", EV))
    a.fresh = False
    with pytest.raises(ValueError):
        jaccard([a, a])


@pytest.mark.skipif(REVIEW is None, reason="needs runs/e2e-2 (local)")
def test_the_auditor_review_converts_and_reports_also_violated_rules():
    fs = from_review(REVIEW)
    omar = [f for f in fs.findings if f.personas == ["omar"]]
    assert {(f.rule, f.secondary) for f in omar} == {("U1", False), ("P1", True)}
    s = score(fs, DEV, evidence=evidence_index(REVIEW))
    assert s["recall"] == 1.0 and s["fp"] == 0          # dev fixture: the auditor was tuned here


@pytest.mark.skipif(REVIEW is None, reason="needs runs/e2e-2 (local)")
def test_dropping_a_finding_lowers_recall_and_names_it():
    fs = from_review(REVIEW)
    fs.findings = [f for f in fs.findings if f.rule != "U4"]
    s = score(fs, DEV)
    assert s["fn"] == 2 and s["recall"] < 1.0            # U4 reached maya and maya_r (family is out of scope)


EVENTS = {"kai": [{"id": "pw.email.forecast", "at": "10:01", "kind": "message", "feature": "price_watch",
                   "surface": "inbox", "message_key": "pw.email.forecast", "text": "We suggest waiting."},
                  {"id": "fl.banner.urgent", "at": "10:03", "kind": "message", "feature": "fare_lock",
                   "surface": "fare_detail", "message_key": "fl.banner.urgent", "text": "Only 2 seats left. Book now."}]}


def test_sheet_hides_systems_merges_duplicates_and_shows_evidence():
    a = Findings(system="semaudit-full", release="t", findings=[
        F("a1", ["kai"], "P2", REL, "conflict", cited=[Cited(persona="kai", event_id="pw.email.forecast", quote="x")])])
    b = Findings(system="B-judge-1", release="t", findings=[
        F("b1", ["kai"], "P2", REL, "conflict", cited=[Cited(persona="kai", event_id="fl.banner.urgent", quote="x")]),
        F("b2", ["kai"], "U1", EV)])
    sheet, key = build([a, b], truth(T("s", ["kai"], "P2", REL, "conflict")), {"P2": "reconcile"}, seed=7,
                       events=EVENTS, objective_rules={"U1"})
    assert len(sheet) == 1                                  # merged; objective U1 not adjudicated
    text = json.dumps(sheet)
    assert "semaudit" not in text and "B-judge" not in text and "a1" not in text
    assert "We suggest waiting." in sheet[0]["evidence"] and "Book now." in sheet[0]["evidence"]
    assert {s["system"] for s in key[0]["sources"]} == {"semaudit-full", "B-judge-1", "seeded"}


def test_evidence_does_not_depend_on_which_system_came_first():
    a = Findings(system="A", release="t", findings=[
        F("a", ["kai"], "P2", REL, "conflict", cited=[Cited(persona="kai", event_id="pw.email.forecast", quote="x")])])
    b = Findings(system="B", release="t", findings=[
        F("b", ["kai"], "P2", REL, "conflict", cited=[Cited(persona="kai", event_id="fl.banner.urgent", quote="x")])])
    one = build([a, b], truth(), {}, seed=1, events=EVENTS, objective_rules=set())[0]
    two = build([b, a], truth(), {}, seed=1, events=EVENTS, objective_rules=set())[0]
    assert one == two


def test_a_seeded_item_no_system_raised_still_carries_evidence():
    sheet, _ = build([], truth(T("s", ["kai"], "P1", EV)), {}, seed=1, events=EVENTS, objective_rules=set())
    assert sheet[0]["evidence"] == "10:03 fare_lock: Only 2 seats left. Book now."


def test_sheet_order_is_seeded_and_stable():
    fs = Findings(system="x", release="t", findings=[F(str(n), [f"p{n}"], "P1", EV) for n in range(8)])
    one = build([fs], truth(), {}, seed=3, events={}, objective_rules=set())[0]
    assert one == build([fs], truth(), {}, seed=3, events={}, objective_rules=set())[0]
    assert one != build([fs], truth(), {}, seed=4, events={}, objective_rules=set())[0]


def test_verdicts_move_the_truth_and_every_system_is_rescored_against_it():
    from semaudit.bench.adjudicate import apply_verdicts
    seeded = T("s", ["kai", "omar"], "P1", EV)
    t = truth(seeded)
    auditor = found(F("a", ["kai", "omar"], "P1", EV))
    baseline = found(F("b", ["kai"], "P1", EV), F("x", ["lena"], "U4", EV))
    sheet, key = build([auditor, baseline], t, {}, seed=2, events={}, objective_rules=set())
    row = {(k["persona"], k["rule"]): k["row"] for k in key}
    verdicts = {row[("omar", "P1")]: {"verdict": "not_real"}, row[("lena", "U4")]: {"verdict": "real"},
                row[("kai", "P1")]: {"verdict": "real"}}
    adj, log = apply_verdicts(t, key, verdicts, adjudicator="owner")
    assert log["removed"] == [["s", "omar"]] and log["added"][0][1:] == ["lena", "U4"]
    before, after = score(auditor, t), score(auditor, adj)
    assert (before["fn"], after["fn"]) == (0, 1) and after["fp"] == 1   # omar no longer real; missed lena
    b_after = score(baseline, adj)
    assert (b_after["tp"], b_after["fp"]) == (2, 0)                    # its unseeded find now counts for it


def test_blank_and_unsure_rows_change_nothing():
    from semaudit.bench.adjudicate import apply_verdicts
    t = truth(T("s", ["kai"], "P1", EV))
    sheet, key = build([found(F("x", ["lena"], "U4", EV))], t, {}, seed=2, events={}, objective_rules=set())
    adj, log = apply_verdicts(t, key, {key[0]["row"]: {"verdict": "unsure"}}, adjudicator="owner")
    assert adj.items == t.items and log["unsure"] and log["blank"]


def test_kappa():
    assert kappa(["real", "not_real"] * 5, ["real", "not_real"] * 5) == 1.0
    assert kappa(["real"] * 4 + ["not_real"] * 4, ["real", "not_real"] * 4) == 0.0
    assert kappa(["", "real"], ["real", ""]) is None


def test_an_item_made_of_several_events_matches_a_finding_about_any_one():
    shown = Target(kind="event", feature="fare_lock", surface="fare_detail", message_key="fl.banner")
    charged = Target(kind="event", feature="fare_lock", surface="checkout", message_key="fl.checkout.lock")
    t = Truth(release="t", items=[TruthItem(id="t", kind="issue", personas=["sam"], rule="U2", target=shown,
                                            also_targets=[charged])])
    assert score(found(F("f", ["sam"], "U2", charged)), t)["tp"] == 1
    other = Target(kind="event", feature="fare_lock", surface="checkout", message_key="fl.other")
    assert score(found(F("f", ["sam"], "U2", other)), t)["tp"] == 0


def test_event_identity_includes_the_surface():
    elsewhere = Target(kind="event", feature="fare_lock", surface="checkout", message_key="fl.banner.urgent")
    assert score(found(F("f", ["kai"], "P1", elsewhere)), truth(T("t", ["kai"], "P1", EV)))["tp"] == 0


def test_a_malformed_finding_counts_as_a_false_positive():
    fs = found(F("f", ["kai"], "P1", EV))
    fs.dropped = ["x-002: a relation target names two different features and a decision"]
    s = score(fs, truth(T("t", ["kai"], "P1", EV)))
    assert (s["tp"], s["fp"], s["precision"]) == (1, 1, 0.5) and len(s["malformed"]) == 1


def test_intervals_report_raw_counts_and_widen_for_small_samples():
    from semaudit.bench.match import wilson
    small, large = wilson(0, 6), wilson(0, 600)
    assert small["k"] == 0 and small["n"] == 6 and small["ci95"][1] > 0.35 > large["ci95"][1]
    assert wilson(0, 0)["value"] is None


def test_attribution_scores_delta_and_responsible_features():
    t = Truth(release="t", items=[TruthItem(id="t", kind="issue", personas=["kai"], rule="P1", target=EV,
                                            delta="new", features=["fare_lock"])])
    right = F("f", ["kai"], "P1", EV, delta="new", features=["fare_lock"])
    wrong = F("f", ["kai"], "P1", EV, delta="existing", features=["price_watch"])
    silent = F("f", ["kai"], "P1", EV)
    assert score(found(right), t)["attribution"]["delta_accuracy"]["value"] == 1.0
    a = score(found(wrong), t)["attribution"]
    assert a["delta_accuracy"]["value"] == 0.0 and a["features_correct"]["value"] == 0.0
    assert score(found(silent), t)["attribution"]["reported"] == 0
