"""Reader mode (no model): SRA checks the reader's citations, groups its findings and dates them across releases.

Stories are the Northbound e2e-2 captures with a few message texts set by the test, so every case is exact."""

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.bench.findings import Finding  # noqa: E402
from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.decide import reader  # noqa: E402
from semaudit.decide.pipeline import ReleaseEval, load_release  # noqa: E402

C = load_contract(ROOT / "examples/northbound/contract")
RUN = ROOT / "runs/e2e-2"
pytestmark = pytest.mark.skipif(not (RUN / "episodes/2.4").exists(), reason="needs runs/e2e-2 (local)")
FACTS = [f.id for f in C.facts]
F1, F2 = FACTS[0], FACTS[1]
R1, R2 = C.rules[0].id, C.rules[1].id

A_TEXT = "Your total shipping is $0.00 today"
B_TEXT = "Standard delivery costs $5.00 for this order"
C_TEXT = "Order total $42.00 including delivery"


@pytest.fixture(scope="module")
def base_ev():
    episodes, not_measured, stories = load_release(RUN, "2.4", C)
    return ReleaseEval("2.4", episodes, {p: (s, []) for p, s in stories.items()}, not_measured)


@pytest.fixture(scope="module")
def p(base_ev):
    return next(x for x in sorted(base_ev.results) if len(msgs(base_ev, x)) >= 3)


def msgs(ev, persona):
    return [e for e in ev.results[persona][0].events if e.kind == "message"]


def setup(ev, persona, texts: dict[int, tuple[str, str] | str]) -> ReleaseEval:
    """A copy of the release where message k of the persona shows texts[k] (text, or (new id, text))."""
    out = copy.deepcopy(ev)
    ms = msgs(out, persona)
    for e in ms:                                  # every other message: text the tests never quote
        e.text = "unrelated words here"
    for k, v in texts.items():
        if isinstance(v, tuple):
            ms[k].id, ms[k].text = v
        else:
            ms[k].text = v
    return out


def m(ev, persona, k):
    return msgs(ev, persona)[k]


def finding(fid, rule, persona, cites, why, target):
    return Finding.model_validate({
        "id": fid, "personas": [persona], "rule": rule, "severity": "critical", "confidence": "high", "why": why,
        "target": {"kind": "event", "feature": target.feature, "surface": target.surface, "message_key": target.id},
        "cited": [{"persona": persona, "event_id": e.id, "quote": q} for e, q in cites]})


@pytest.fixture
def ev(base_ev, p):
    return setup(base_ev, p, {0: A_TEXT, 1: B_TEXT, 2: C_TEXT})


# ---- evidence ----

def test_a_quote_in_the_cited_message_is_evidence_and_confidence_is_capped_at_medium(ev, p):
    a = m(ev, p, 0)
    issues, refused = reader.build_reader_issues([finding("F1", R1, p, [(a, "$0.00")], f"{F1} wrong", a)], ev, C)
    assert not refused and len(issues) == 1
    i = issues[0]
    assert i.personas == [p] and i.occurrences[0].events == [a.id] and i.occurrences[0].entry.meta["quotes"] == ["$0.00"]
    assert i.verification["steps"]["evidence_linked"]["result"] == "pass"
    assert i.confidence["level"] == "medium"                   # the model said high; no replay or second model
    assert i.severity["level"] == C.rules[0].severity_for(None)  # the owner's level, not the model's


def test_a_quote_in_no_message_is_refused_and_a_finding_left_without_evidence_is_not_raised(ev, p):
    a = m(ev, p, 0)
    issues, refused = reader.build_reader_issues(
        [finding("F1", R1, p, [(a, "text never shown to anyone at all")], "w", a)], ev, C)
    assert issues == [] and len(refused) == 1 and refused[0]["reason"].startswith("evidence check failed")


def test_a_quote_with_no_figure_and_one_word_is_refused_even_in_the_cited_message(ev, p):
    a = m(ev, p, 0)
    issues, refused = reader.build_reader_issues([finding("F1", R1, p, [(a, "shipping")], "w", a)], ev, C)
    assert issues == [] and "states no figure" in refused[0]["reason"]


def test_a_specific_quote_in_one_other_message_is_re_pointed_and_lowers_confidence(ev, p):
    a, b = m(ev, p, 0), m(ev, p, 1)
    issues, _ = reader.build_reader_issues(
        [finding("F1", R1, p, [(a, "delivery costs $5.00")], f"{F1} wrong", a)], ev, C)
    step = issues[0].verification["steps"]["evidence_linked"]
    assert issues[0].occurrences[0].events == [b.id]
    assert step["result"] == "fail" and "another message than cited" in step["detail"]
    assert issues[0].confidence["level"] == "low"


def test_a_bare_figure_not_in_the_cited_message_is_not_re_pointed(ev, p):
    a = m(ev, p, 0)
    issues, refused = reader.build_reader_issues([finding("F1", R1, p, [(a, "$5.00")], "w", a)], ev, C)
    assert issues == [] and "not in the cited message" in refused[0]["reason"]


# ---- grouping ----

def test_same_fact_and_message_is_one_issue_across_rules_and_the_other_side_is_compared_not_evidence(ev, p):
    a, b, c = m(ev, p, 0), m(ev, p, 1), m(ev, p, 2)
    fs = [finding("F1", R1, p, [(a, "$0.00")], f"{F1} on this message", a),
          # another rule: the same figure differs between a and b; b is the other side of the comparison
          finding("F2", R2, p, [(b, "$5.00"), (a, "$0.00")], f"the {F1.replace('_', ' ')} differs", b),
          finding("F3", R1, p, [(c, "$42.00")], f"{F2} on this message", c)]
    issues, _ = reader.build_reader_issues(fs, ev, C)
    by_fact = {i.signature[2]: i for i in issues}
    assert set(by_fact) == {F1, F2}
    merged = by_fact[F1]
    assert merged.rule == R1 and [x.rule for x in merged.occurrences[0].also] == [R2]
    assert merged.occurrences[0].events == [a.id]               # b is not evidence that a is wrong
    assert [x["event"] for x in merged.occurrences[0].entry.meta["compared_with"]] == [b.id]


def test_fact_names_are_read_with_spaces_or_hyphens():
    f = Finding.model_validate({"id": "x", "personas": ["p"], "rule": "U1", "why": "The Line-amount shown is wrong",
                                "target": {"kind": "story"}, "cited": []})
    assert reader._fact(f, ["item_total", "line_amount"]) == "line_amount"


# ---- release delta ----

def issue(ev, p, k, quote, fact, fid="F"):
    e = m(ev, p, k)
    return reader.build_reader_issues([finding(fid, R1, p, [(e, quote)], f"{fact} wrong" if fact else "wrong", e)],
                                      ev, C)[0][0]


def test_resolved_needs_the_message_still_shown_without_the_quoted_text(base_ev, p, ev):
    base = [issue(ev, p, 1, "$5.00", F1)]
    head_ev = setup(base_ev, p, {0: A_TEXT, 1: "Standard delivery costs $0.00 for this order", 2: C_TEXT})
    resolved, unconfirmed = reader.reader_delta([], base, head_ev, ev)
    assert [b.delta for b in resolved] == ["resolved"] and not unconfirmed


def test_a_reworded_message_is_unconfirmed_not_resolved(base_ev, p, ev):
    base = [issue(ev, p, 1, "$5.00", F1)]
    head_ev = setup(base_ev, p, {0: A_TEXT, 1: ("reworded.key", "Delivery is $9.99"), 2: C_TEXT})
    resolved, unconfirmed = reader.reader_delta([], base, head_ev, ev)
    assert not resolved and unconfirmed[0].delta == "unconfirmed" and "reworded or removed" in unconfirmed[0].delta_basis


def test_a_quote_still_shown_anywhere_in_head_is_unconfirmed(base_ev, p, ev):
    base = [issue(ev, p, 0, "total shipping is $0.00", F1)]
    head_ev = setup(base_ev, p, {0: "Your total shipping is $5.00 today",
                                 2: "Note: your total shipping is $0.00 today"})
    resolved, unconfirmed = reader.reader_delta([], base, head_ev, ev)
    assert not resolved and "still shown" in unconfirmed[0].delta_basis


def test_a_different_named_fact_on_the_same_message_does_not_match_and_no_base_issue_is_lost(ev, p):
    base = [issue(ev, p, 0, "$0.00", F1, "B1"), issue(ev, p, 0, "$0.00", F2, "B2")]
    head = [issue(ev, p, 0, "$0.00", F2, "H1")]
    resolved, unconfirmed = reader.reader_delta(head, base, ev, ev)
    assert head[0].delta == "pre_existing" and base[1].id in head[0].delta_basis and base[0].id not in head[0].delta_basis
    assert [b.id for b in unconfirmed] == [base[0].id]           # quote still shown: carried, not lost or resolved
    assert not resolved


def test_an_unnamed_fact_matches_a_named_one_on_the_same_message(ev, p):
    base = [issue(ev, p, 0, "$0.00", None, "B1")]
    head = [issue(ev, p, 0, "$0.00", F1, "H1")]
    resolved, unconfirmed = reader.reader_delta(head, base, ev, ev)
    assert head[0].delta == "pre_existing" and not resolved and not unconfirmed


def test_a_head_issue_the_base_reading_missed_is_pre_existing_only_if_base_showed_the_same_text(base_ev, p, ev):
    head = [issue(ev, p, 0, "$0.00", F1)]
    reader.reader_delta(head, [], ev, ev)
    assert head[0].delta == "pre_existing" and "did not report it" in head[0].delta_basis
    head = [issue(ev, p, 0, "$0.00", F1)]
    reader.reader_delta(head, [], ev, setup(base_ev, p, {0: "Your total shipping is $5.00 today"}))
    assert head[0].delta == "new"


# ---- second audit ----

def test_refusals_are_counted_per_finding_even_when_ids_repeat_across_chunks(ev, p):
    a, b = m(ev, p, 0), m(ev, p, 1)
    good = finding("B-judge-1-001", R1, p, [(a, "$0.00")], f"{F1} wrong", a)            # chunk 1
    bad = finding("B-judge-1-001", R1, p, [(b, "never shown anywhere at all")], f"{F2} wrong", b)  # chunk 2
    issues, refused = reader.build_reader_issues([good, bad], ev, C)
    (i,) = issues
    assert i.verification["steps"]["evidence_linked"]["result"] == "pass" and i.confidence["level"] == "medium"
    assert len(refused) == 1


def test_a_bare_figure_shown_elsewhere_does_not_block_resolution(base_ev, p, ev):
    base = [issue(ev, p, 1, "$5.00", F1)]
    head_ev = setup(base_ev, p, {1: "Standard delivery costs $0.00 for this order", 2: "Order total $5.00"})
    resolved, unconfirmed = reader.reader_delta([], base, head_ev, ev)
    assert [b.delta for b in resolved] == ["resolved"] and not unconfirmed


def test_a_two_sided_rule_needs_both_messages_evidenced(ev, p):
    c2 = copy.deepcopy(C)
    c2.rule(R2).check = {**(c2.rule(R2).check or {}), "must": "agree_across_surfaces"}
    a, b = m(ev, p, 0), m(ev, p, 1)
    one = finding("F1", R2, p, [(a, "$0.00"), (b, "text never shown anywhere")], f"{F1} differs", a)
    both = finding("F2", R2, p, [(a, "$0.00"), (b, "$5.00")], f"{F1} differs", a)
    assert reader.build_reader_issues([one], ev, c2)[0] == []
    (i,), _ = reader.build_reader_issues([both], ev, c2)
    assert sorted(i.occurrences[0].events) == sorted([a.id, b.id])
