"""build_issues never drops a violated rule: each one is raised as an issue or listed in an occurrence's `also`.

The case that dropped one: two surfaces disagree on a figure (agree_across_surfaces, raised on both messages) and one
of them is also wrong against the app's record (match_oracle). When the disagreement was first raised from the
other message, the second message's entry was skipped as "the same disagreement, raised from its other side", and
the match_oracle violation riding along in its `also` went with it. Whether it survived depended on which message
came first.
"""

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pytest  # noqa: E402

from semaudit.contract.schema import Rule, load_contract  # noqa: E402
from semaudit.decide.issues import build_issues  # noqa: E402
from semaudit.relate.rules import Entry  # noqa: E402
from semaudit.story.model import Event, Extraction, Story  # noqa: E402

T0 = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
C = load_contract(ROOT / "tests" / "fixtures" / "generic_contract").model_copy(update={"rules": [
    Rule(id="B1", kind="universal", text="The same figure reads the same everywhere.",
         check={"claims": ["price"], "must": "agree_across_surfaces"}),
    Rule(id="B2", kind="universal", text="A figure matches our own record.",
         check={"claims": ["price"], "must": "match_oracle", "oracle": "plan"}),
]})


def msg(i, surface, minutes):
    x = Extraction(message_kind="information", decision="none", action="none", strength="inform",
                   urgency_cue="none", explains_own_tradeoff=False, claims=[{"type": "price", "value": 12}])
    return Event(id=i, at=T0 + timedelta(minutes=minutes), kind="message", feature="core", surface=surface,
                 text=i, extraction=x)


def story_and_entries(email_first: bool):
    story = Story(id="ana", release="1.1", persona="ana", events=[msg("page", "pricing", 0), msg("mail", "email", 1)])
    b1_mail = Entry("B1", "mail", "violated", meta={"events": ["mail", "page"], "fact": "price"})
    b1_page = Entry("B1", "page", "violated", meta={"events": ["page", "mail"], "fact": "price"})
    b2_page = Entry("B2", "page", "violated", meta={"fact": "price"})
    entries = [b1_mail, b1_page, b2_page] if email_first else [b1_page, b2_page, b1_mail]
    return story, entries


def accounted(issues):
    """Every (rule, subject) the issues carry: as an occurrence's own entry, or in its `also`."""
    return {(e.rule, e.subject) for i in issues for o in i.occurrences for e in (o.entry, *o.also)}


@pytest.mark.parametrize("email_first", [True, False])
def test_a_second_rule_on_the_same_message_is_never_dropped(email_first):
    story, entries = story_and_entries(email_first)
    issues = build_issues("1.1", {"ana": (story, entries)}, C)
    assert [i.rule for i in issues] == ["B1"]                     # one disagreement, one issue
    assert ("B2", "page") in accounted(issues)                    # B2 is listed with it, whichever side came first
    every_violation = {(e.rule, e.subject) for e in entries}
    # the B1 entry on the other message is the same disagreement (same cited pair): it is the issue itself
    assert every_violation - accounted(issues) <= {("B1", "page"), ("B1", "mail")}


def test_the_result_does_not_depend_on_which_side_came_first():
    def shape(email_first):
        story, entries = story_and_entries(email_first)
        (i,) = build_issues("1.1", {"ana": (story, entries)}, C)
        return i.signature, sorted((a.rule, a.subject) for o in i.occurrences for a in o.also)
    assert shape(True) == shape(False) == (shape(True)[0], [("B2", "page")])
