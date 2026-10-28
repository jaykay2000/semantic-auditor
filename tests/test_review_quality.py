"""Three causes of false alarms found on a real contract-mapped app (R1 run, 2026-10-28), fixed generically:
roles (a target or a change is not the current figure), reading context for a bare figure, and an agreement
issue identified by what disagrees with what."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from semaudit.contract.schema import Fact  # noqa: E402
from semaudit.decide.issues import signature  # noqa: E402
from semaudit.extract.messages import ROLE_PROMPT, _claim_schema, _prompt, message_key  # noqa: E402
from semaudit.relate.rules import Entry, eval_agree_across_surfaces, eval_match_oracle  # noqa: E402
from semaudit.story.build import around  # noqa: E402
from semaudit.story.model import Event, Extraction, Story  # noqa: E402

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
SAVED = Fact(id="monthly_saved", unit="USD")
ON = SimpleNamespace(facts=[SAVED], state=[], app=SimpleNamespace(claim_roles=True))
RULE = SimpleNamespace(id="U2", check={"claims": ["monthly_saved"], "must": "agree_across_surfaces"})


def msg(i, surface, value, minutes, role, key=None):
    x = Extraction(message_kind="information", decision="none", action="none", strength="inform",
                   urgency_cue="none", explains_own_tradeoff=False,
                   claims=[{"type": "monthly_saved", "value": value, "unit": "USD", "role": role}])
    return Event(id=i, at=T0 + timedelta(minutes=minutes), kind="message", feature="f", surface=surface,
                 text=str(value), extraction=x, copy_key=key or f"f.{i}")


def agree(*events):
    story = Story(id="s", release="r", persona="p", events=list(events))
    return {(x.subject, x.status) for x in eval_agree_across_surfaces(RULE, story, ON)}


# ---- roles
def test_a_target_is_not_compared_with_the_current_figure():
    assert agree(msg("now", "report", 1200, 0, "as_is"), msg("goal", "export", 1875, 1, "proposed")) == set()
    assert agree(msg("a", "report", 1200, 0, "as_is"), msg("b", "export", 1500, 1, "as_is")) == \
        {("a", "violated"), ("b", "violated")}
    assert agree(msg("a", "report", 1875, 0, "proposed"), msg("b", "export", 1900, 1, "proposed")) == \
        {("a", "violated"), ("b", "violated")}                              # two targets for one thing still disagree
    assert agree(msg("a", "report", 7500, 0, "proposed"), msg("b", "export", 8600, 1, "limit")) == \
        {("a", "violated"), ("b", "violated")}                              # a target vs the cap it is set at
    assert agree(msg("a", "report", 12500, 0, "change"), msg("b", "export", 35750, 1, "limit")) == set()


def test_only_a_current_figure_is_checked_against_the_oracle():
    story = Story(id="s", release="r", persona="p", truth={"monthly_saved": 1200},
                  events=[msg("now", "report", 1200, 0, "as_is"), msg("goal", "report", 1875, 1, "proposed"),
                          msg("gap", "report", 675, 2, "change"), msg("old", "report", 999, 3, None)])
    rule = SimpleNamespace(id="U1", check={"claims": ["monthly_saved"], "must": "match_oracle"})
    assert {(x.subject, x.status) for x in eval_match_oracle(rule, story)} == \
        {("now", "passed"), ("old", "violated")}                          # no role (roles off): checked, as before


def test_roles_are_asked_for_only_when_the_contract_turns_them_on():
    assert _claim_schema(ON)["properties"]["role"]["enum"] == ["as_is", "proposed", "change", "limit", None]
    off = SimpleNamespace(facts=[SAVED], app=SimpleNamespace(claim_roles=False))
    assert "role" not in _claim_schema(off)["properties"] and ROLE_PROMPT not in _prompt(off)
    assert ROLE_PROMPT in _prompt(ON)


# ---- reading context
def el(text, obscured=None):
    return SimpleNamespace(text=text, obscured=obscured)


def test_a_bare_figure_is_read_with_its_label_and_neighbour():
    cap = SimpleNamespace(kind="web", elements=[el("Your plan"), el("Net worth"), el("$860K"), el("hidden", "blur"),
                                                 el("Vs plan +2 years")])
    assert around(cap, 2) == "Net worth | [this] | Vs plan +2 years"           # obscured text is skipped
    assert around(cap, 0) == " | [this] | Net worth"
    long = SimpleNamespace(kind="web", elements=[el("Label"), el("Raise monthly savings to $1,875 this year")])
    assert around(long, 1) is None                                             # a sentence carries its own meaning
    assert around(SimpleNamespace(kind="text", elements=[el("a"), el("$1")]), 1) is None


def test_the_same_figure_under_different_labels_is_extracted_separately():
    a = {"feature": "f", "channel": "page", "text": "$860K", "around": "Net worth | [this] | Vs plan"}
    b = {**a, "around": "Freedom target | [this] | age 65"}
    assert message_key(a) != message_key(b) and message_key({**a, "around": None})[3] == ""


# ---- issue identity
def test_a_different_disagreement_on_the_same_block_is_a_different_issue():
    page = Event(id="p", at=T0, kind="message", feature="plan", copy_key="plan.k1", text="$24,500")
    exp1 = Event(id="x1", at=T0, kind="message", feature="export", copy_key="export.rest", text="$32,500")
    exp2 = Event(id="x2", at=T0, kind="message", feature="export", copy_key="export.first", text="$12,500")
    e = lambda: Entry("U2", "p", "violated", meta={"events": ["p", "x"], "fact": "move_amount"})  # noqa: E731
    assert signature(e(), [page, exp1]) != signature(e(), [page, exp2])
    assert signature(e(), [page, exp1]) == signature(e(), [page, exp1])
    plain = Entry("U1", "p", "violated")
    assert signature(plain, [page]) == ("U1", "plan", "plan.k1", ())             # other rules: unchanged
