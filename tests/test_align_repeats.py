"""Audit A-04: a contract-mapped template that repeats in one capture has only an order index (#n) to tell its
copies apart. Inserting a copy shifts every index after it, so pairing by key would report copies as `changed`
that did not change. Repeats pair by identical text first; the rest pair in order and are fuzzy."""
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from semaudit.story.align import align  # noqa: E402
from semaudit.story.model import Event, Evidence, Story  # noqa: E402

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def m(i, key, text, method="contract_map"):
    ev = Evidence(episode="e", step=1, capture_id="c", element=0, locator={}, attribution={"method": method})
    return Event(id=i, at=T0, kind="message", feature="plan", surface="report", channel="page", copy_key=key,
                 text=text, evidence=ev)


def story(release, *events):
    return Story(id=release, release=release, persona="p", events=list(events))


def status(d):
    return {(p.base, p.head): p.status for p in d.pairs}, sorted(d.added), sorted(d.removed)


def test_an_inserted_copy_does_not_mark_the_others_changed():
    base = story("b", m("b1", "plan.aa", "Move $1,000 to savings"), m("b2", "plan.aa#2", "Move $2,000 to IRA"))
    head = story("h", m("h0", "plan.aa", "Move $500 to HSA"), m("h1", "plan.aa#2", "Move $1,000 to savings"),
                 m("h2", "plan.aa#3", "Move $2,000 to IRA"))
    pairs, added, removed = status(align(base, head))
    assert pairs == {("b1", "h1"): "unchanged", ("b2", "h2"): "unchanged"} and added == ["h0"] and removed == []


def test_a_repeat_whose_text_changed_pairs_fuzzy_never_changed():
    base = story("b", m("b1", "plan.aa", "Move $1,000 to savings"), m("b2", "plan.aa#2", "Move $2,000 to IRA"))
    head = story("h", m("h1", "plan.aa", "Move $1,000 to savings"), m("h2", "plan.aa#2", "Move $2,500 to IRA"))
    pairs, added, removed = status(align(base, head))
    assert pairs == {("b1", "h1"): "unchanged", ("b2", "h2"): "fuzzy"} and added == removed == []


def test_a_single_copy_still_pairs_by_key_and_reports_changed():
    base = story("b", m("b1", "plan.aa", "Move $1,000 to savings"))
    head = story("h", m("h1", "plan.aa", "Move $1,500 to savings"))
    assert status(align(base, head))[0] == {("b1", "h1"): "changed"}


def test_app_marked_keys_are_not_treated_as_index_only_repeats():
    base = story("b", m("b1", "k", "A $1", "dom_attr"), m("b2", "k", "A $2", "dom_attr"))
    head = story("h", m("h1", "k", "A $1", "dom_attr"), m("h2", "k", "A $3", "dom_attr"))
    assert status(align(base, head))[0] == {("b1", "h1"): "unchanged", ("b2", "h2"): "changed"}
