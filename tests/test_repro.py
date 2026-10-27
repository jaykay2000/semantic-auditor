"""Audit P0: a replay must check something, against the right release, and re-derive the finding."""

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.decide.issues import Issue, Occurrence  # noqa: E402
from semaudit.decide.repro import evidence_check, finding_check  # noqa: E402
from semaudit.relate.rules import Entry  # noqa: E402
from semaudit.story.model import Event, Story  # noqa: E402

AT = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)
ROW = {"id": "pw_after", "kind": "message", "at": AT.isoformat(), "feature": "price_watch",
       "message_key": "pw.email.after", "text": "Keep waiting to book."}


def story(*events):
    return Story(id="s", release="2.4", persona="maya", events=list(events))


MSG = Event(id="pw_after", at=AT, kind="message", feature="price_watch", copy_key="pw.email.after",
            text="Keep waiting to book.")
ISSUE = {"occurrences": [{"persona": "maya", "events": ["pw_after"]}]}


def test_a_resolved_issue_is_checked_against_base_events():
    # the event exists only in base (that is why the issue is resolved): head events do not record it
    review = {"personas": [{"id": "maya", "events": [], "base_events": [ROW]}]}
    ok = evidence_check(ISSUE, review, "base_events", {"maya": story(MSG)})
    assert ok.ok and ok.lines == ["✓ maya 12:00:00 price_watch: \"Keep waiting to book.\""]
    # the old bug: looking in head events skipped the event and reported success; now it fails loudly
    wrong = evidence_check(ISSUE, review, "events", {"maya": story(MSG)})
    assert not wrong.ok and "does not record this cited event" in wrong.lines[0]


def test_a_replay_that_checked_nothing_fails():
    review = {"personas": [{"id": "maya", "events": [ROW]}]}
    c = evidence_check({"occurrences": []}, review, "events", {})
    assert not c.ok and c.lines == ["✗ no cited event was checked"]


def test_every_occurrence_must_come_back():
    review = {"personas": [{"id": "maya", "events": [ROW]}, {"id": "lena", "events": [ROW]}]}
    two = {"occurrences": ISSUE["occurrences"] + [{"persona": "lena", "events": ["pw_after"]}]}
    c = evidence_check(two, review, "events", {"maya": story(MSG)})
    assert not c.ok and "✗ lena: not re-captured" in c.lines
    moved = MSG.model_copy(update={"at": AT.replace(minute=1)})
    assert not evidence_check(ISSUE, review, "events", {"maya": story(moved)}).ok      # time must match exactly
    reworded = MSG.model_copy(update={"text": "Keep waiting."})
    assert not evidence_check(ISSUE, review, "events", {"maya": story(reworded)}).ok


def issue(personas, sev="minor"):
    occ = [Occurrence(p, "s", ["pw_after"], Entry("U3", "pw_after", "violated"), "after_decision") for p in personas]
    return Issue(id="I-x", signature=("U3", "price_watch", "pw.email.after", ()), rule="U3", rule_kind="universal",
                 layer="release", label=None, occurrences=occ, severity={"level": sev}, why="")


RECORDED = {"signature": ["U3", "price_watch", "pw.email.after", []], "rule": "U3", "severity": {"level": "minor"}}


def test_the_finding_must_re_derive_with_the_same_rule_severity_and_reach():
    assert finding_check(RECORDED, [issue(["maya", "lena"])], ["maya", "lena"], expect_present=True, label="f").ok
    assert not finding_check(RECORDED, [], ["maya"], expect_present=True, label="f").ok
    assert not finding_check(RECORDED, [issue(["maya"], "major")], ["maya"], expect_present=True, label="f").ok
    c = finding_check(RECORDED, [issue(["maya"])], ["maya", "lena"], expect_present=True, label="f")
    assert not c.ok and "✗ not re-derived for lena" in c.lines


def test_a_resolved_finding_must_be_absent_from_fresh_head():
    assert finding_check(RECORDED, [], ["maya"], expect_present=False, label="h").ok
    still = finding_check(RECORDED, [issue(["maya"])], ["maya"], expect_present=False, label="h")
    assert not still.ok and "still present" in still.lines[0]
