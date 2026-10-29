"""Reader mode (no model): SRA checks the reader's citations, groups its findings and dates them across releases."""

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


def release(rel="2.4"):
    episodes, not_measured, stories = load_release(RUN, rel, C)
    return ReleaseEval(rel, episodes, {p: (s, []) for p, s in stories.items()}, not_measured)


def msgs(ev, persona):
    return [e for e in ev.results[persona][0].events if e.kind == "message" and len(e.text or "") > 20]


def finding(fid, rule, persona, cites, why, target_event):
    e = target_event
    return Finding.model_validate({
        "id": fid, "personas": [persona], "rule": rule, "severity": "critical", "confidence": "high", "why": why,
        "target": {"kind": "event", "feature": e.feature, "surface": e.surface, "message_key": e.id},
        "cited": [{"persona": persona, "event_id": eid, "quote": q} for eid, q in cites]})


@pytest.fixture(scope="module")
def ev():
    return release()


def persona_with_two(ev):
    return next(p for p in sorted(ev.results) if len(msgs(ev, p)) >= 2)


def test_a_quote_found_in_the_cited_message_is_evidence_and_confidence_is_capped_at_medium(ev):
    p = persona_with_two(ev)
    e = msgs(ev, p)[0]
    fact = FACTS[0]
    issues, refused = reader.build_reader_issues(
        [finding("F1", C.rules[0].id, p, [(e.id, e.text[:15])], f"{fact} is wrong", e)], ev, C)
    assert not refused and len(issues) == 1
    i = issues[0]
    assert i.personas == [p] and i.occurrences[0].events == [e.id]
    assert i.verification["steps"]["evidence_linked"]["result"] == "pass"
    assert i.confidence["level"] == "medium"                   # the model said high; no replay or second model
    assert i.severity["level"] == C.rules[0].severity_for(None)  # the owner's level, not the model's


def test_a_quote_in_no_captured_message_is_dropped_and_a_finding_left_without_evidence_is_not_raised(ev):
    p = persona_with_two(ev)
    e = msgs(ev, p)[0]
    issues, refused = reader.build_reader_issues(
        [finding("F1", C.rules[0].id, p, [(e.id, "text that was never shown to anyone")], "w", e)], ev, C)
    assert issues == [] and len(refused) == 1
    assert refused[0]["reason"].startswith("evidence check failed") and "not in any captured message" in \
        refused[0]["reason"]


def test_a_quote_found_only_in_another_message_is_re_pointed_and_marked(ev):
    p = persona_with_two(ev)
    a, b = msgs(ev, p)[:2]
    q = next(b.text[k:k + 25] for k in range(0, len(b.text) - 25) if b.text[k:k + 25] not in a.text)
    issues, _ = reader.build_reader_issues([finding("F1", C.rules[0].id, p, [(a.id, q)], "w", a)], ev, C)
    step = issues[0].verification["steps"]["evidence_linked"]
    assert issues[0].occurrences[0].events == [b.id]
    assert step["result"] == "fail" and "another message than cited" in step["detail"]


def test_findings_sharing_a_fact_and_a_message_are_one_issue_across_rules_and_a_different_fact_is_not(ev):
    p = persona_with_two(ev)
    a, b = msgs(ev, p)[:2]
    f1, f2 = FACTS[0], FACTS[1]
    r1, r2 = C.rules[0].id, C.rules[1].id
    fs = [finding("F1", r2, p, [(a.id, a.text[:15])], f"{f1} on this message", a),
          finding("F2", r1, p, [(b.id, b.text[:15]), (a.id, a.text[:15])], f"the {f1.replace('_', ' ')} differs", b),
          finding("F3", r1, p, [(a.id, a.text[:15])], f"{f2} on this message", a)]
    issues, _ = reader.build_reader_issues(fs, ev, C)
    by_fact = {i.signature[2]: i for i in issues}
    assert set(by_fact) == {f1, f2}
    merged = by_fact[f1]
    assert merged.rule == r1                                    # the contract's first rule of the group
    assert [x.rule for x in merged.occurrences[0].also] == [r2]


def changed(ev, persona, event_id, text):
    """A copy of the release in which one message of one persona shows other text (a fix, as captured)."""
    import copy
    out = copy.deepcopy(ev)
    e = next(x for x in out.results[persona][0].events if x.id == event_id)
    e.text = text
    return out


def issues_on(ev, p, items):
    return reader.build_reader_issues([finding(f"F{k}", C.rules[0].id, p, [(e.id, e.text[:15])], why, e)
                                       for k, (e, why) in enumerate(items)], ev, C)[0]


def test_a_base_issue_is_resolved_only_when_its_quoted_text_is_gone_from_that_message(ev):
    p = persona_with_two(ev)
    a, b = msgs(ev, p)[:2]
    base = issues_on(ev, p, [(a, f"{FACTS[0]} wrong"), (b, f"{FACTS[0]} wrong")])
    head_ev = changed(ev, p, b.id, "the corrected text")         # b was fixed; a still shows the same text
    resolved, unconfirmed = reader.reader_delta([], base, head_ev, ev)
    assert [i.signature[3] for i in resolved] == [b.id.split("#")[0]] and resolved[0].delta == "resolved"
    assert [i.signature[3] for i in unconfirmed] == [a.id.split("#")[0]]
    assert unconfirmed[0].delta == "unconfirmed" and "still shown" in unconfirmed[0].delta_basis


def test_a_base_issue_whose_message_still_has_a_head_issue_is_carried_not_resolved(ev):
    p = persona_with_two(ev)
    a = msgs(ev, p)[0]
    base = issues_on(ev, p, [(a, f"{FACTS[0]} wrong")])
    head = issues_on(ev, p, [(a, f"{FACTS[1]} wrong")])          # same message, the reading named another fact
    resolved, unconfirmed = reader.reader_delta(head, base, ev, ev)
    assert not resolved and not unconfirmed and head[0].delta == "pre_existing"


def test_a_head_issue_the_base_reading_missed_is_pre_existing_when_base_showed_the_same_text(ev):
    p = persona_with_two(ev)
    a = msgs(ev, p)[0]
    head = issues_on(ev, p, [(a, f"{FACTS[0]} wrong")])
    reader.reader_delta(head, [], ev, ev)
    assert head[0].delta == "pre_existing" and "did not report it" in head[0].delta_basis
    head = issues_on(ev, p, [(a, f"{FACTS[0]} wrong")])
    reader.reader_delta(head, [], ev, changed(ev, p, a.id, "older text"))
    assert head[0].delta == "new"


def test_fact_names_are_read_with_spaces_or_hyphens():
    f = Finding.model_validate({"id": "x", "personas": ["p"], "rule": "U1", "why": "The Line-amount shown is wrong",
                                "target": {"kind": "story"}, "cited": []})
    assert reader._fact(f, ["item_total", "line_amount"]) == "line_amount"
