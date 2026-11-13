"""Two surface declarations a contract makes about how its pages and emails are captured (Spree escape test,
2026-11-12, where both caused false alarms):

* `shown_before_action`: the surface is captured as its step's page first appears, before the step's action takes
  effect (a checkout form the shopper is about to fill). Its messages are read in the state BEFORE that action, so
  the address step's "total before tax and delivery" is compared with the cart, not with the delivery step.
* `format_of`: the surface is another format of the same message (an email's text part beside its HTML part). It
  is still read for claims, but it is never counted as a separate contact by a load rule.

Both go through story building (story_from_episode), so the tests fail if the wiring from the contract is lost."""
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from semaudit.contract.schema import Surface, load_contract  # noqa: E402
from semaudit.contract.validate import validate  # noqa: E402
from semaudit.relate.rules import eval_agree_across_surfaces, eval_load, same_state  # noqa: E402
from semaudit.story.build import story_from_episode  # noqa: E402
from semaudit.story.episode import Capture, Element, Episode, StepRecord  # noqa: E402
from semaudit.story.model import Extraction  # noqa: E402

BASE = load_contract(ROOT / "examples" / "northbound" / "contract")
DAY0 = datetime(2026, 11, 2, tzinfo=UTC)


def contract(**changes):
    """The northbound contract with surface fields changed ({surface_id: {field: value}}) and a text part of the
    inbox email added as its own surface."""
    surfaces = [s.model_copy(update=changes.get(s.id, {})) for s in BASE.surfaces]
    surfaces.append(Surface(id="inbox_text", kind="email", locator="message_id", **changes.get("inbox_text", {})))
    return BASE.model_copy(update={"surfaces": surfaces})


def cap(cid, kind, surface, minute, key):
    attrs = {"data-message-key": key} if kind == "web" else {"X-Message-Key": key}
    return Capture(id=cid, kind=kind, surface=surface, at=DAY0 + timedelta(hours=10, minutes=minute),
                   elements=[Element(locator={}, text=f"text of {key}", attrs=attrs)])


def episode(steps):
    return Episode(release="2.4", persona="maya", scenario="S-book-flexible", app_build="t", started_wall="t",
                   day0=DAY0, clock_measured=False,
                   steps=[StepRecord(seq=i, at=DAY0 + timedelta(hours=10, minutes=m), do=do, status="done",
                                     captures=caps) for i, (m, do, caps) in enumerate(steps, 1)])


# ---------------------------------------------------------------- shown_before_action

def _booking_story(c):
    # the fare page is captured at the `book` step before booking takes effect; the confirmation after it
    return story_from_episode(episode([
        (3, "open_fare", [cap("c1", "web", "fare_detail", 3, "fare.price")]),
        (6, "book", [cap("c2", "web", "fare_detail", 6, "fare.price.again"),
                     cap("c3", "web", "confirmation", 6, "conf.total")]),
    ]), c)


def test_a_surface_shown_before_its_action_is_read_in_the_state_before_it():
    s = _booking_story(contract(fare_detail={"shown_before_action": True}))
    by = {e.copy_key: e for e in s.messages()}
    assert by["fare.price.again"].before_action and not by["conf.total"].before_action
    assert s.shown_state(by["fare.price.again"], BASE.state)["booking_status"] == "not_booked"
    assert s.shown_state(by["conf.total"], BASE.state)["booking_status"] == "booked"
    # so it is compared with the earlier page in the same (pre-booking) state, not with the confirmation
    assert same_state(s, BASE.state, by["fare.price.again"], by["fare.price"])
    assert not same_state(s, BASE.state, by["fare.price.again"], by["conf.total"])


def test_without_the_declaration_a_message_is_read_after_its_steps_action_as_before():
    s = _booking_story(BASE)
    by = {e.copy_key: e for e in s.messages()}
    assert not by["fare.price.again"].before_action
    assert s.shown_state(by["fare.price.again"], BASE.state)["booking_status"] == "booked"
    assert same_state(s, BASE.state, by["fare.price.again"], by["conf.total"])


def _claim(e, value):
    e.extraction = Extraction(message_kind="information", decision="none", action="none", strength="inform",
                              urgency_cue="none", explains_own_tradeoff=False,
                              claims=[{"type": "order_total", "value": value, "unit": "USD"}])


def test_a_real_disagreement_in_the_state_before_the_action_is_still_caught():
    c = contract(fare_detail={"shown_before_action": True})
    s = _booking_story(c)
    by = {e.copy_key: e for e in s.messages()}
    rule = SimpleNamespace(id="U2", check={"claims": ["order_total"], "must": "agree_across_surfaces"})
    # the earlier page on another surface would have to be compared: put the first price on the search results
    by["fare.price"].surface = "search_results"
    _claim(by["fare.price"], 120.0)
    _claim(by["fare.price.again"], 135.0)          # disagrees with the page before it, in the same state
    _claim(by["conf.total"], 135.0)                # after booking: a different state, never compared with them
    got = {(e.subject, e.status) for e in eval_agree_across_surfaces(rule, s, c)}
    assert ("fare.price.again", "violated") in got and ("fare.price", "violated") in got
    assert ("conf.total", "violated") not in got


# ---------------------------------------------------------------- format_of

LOAD = SimpleNamespace(id="L1", count={"channels": ["email"], "max": 1, "window_hours": 1})


def _inbox_story(c, *extra):
    return story_from_episode(episode([
        (1, "check_inbox", [cap("e1", "email", "inbox", 1, "order.confirmation"),
                            cap("e2", "email", "inbox_text", 1, "order.confirmation"), *extra]),
    ]), c)


def test_an_email_in_two_formats_is_one_contact():
    s = _inbox_story(contract(inbox_text={"format_of": "inbox"}))
    assert [e.alternate_format for e in s.messages()] == [False, True]
    assert [x.status for x in eval_load(LOAD, s)] == ["passed"]


def test_without_the_declaration_the_two_formats_count_as_two_contacts():
    s = _inbox_story(contract())
    assert [x.status for x in eval_load(LOAD, s)] == ["violated"]


def test_a_second_email_is_still_a_duplicate():
    s = _inbox_story(contract(inbox_text={"format_of": "inbox"}),
                     cap("e3", "email", "inbox", 1, "order.confirmation.again"))
    got = eval_load(LOAD, s)
    assert [x.status for x in got] == ["violated"] and got[0].meta["count"] == 2


def test_the_text_format_is_still_read_for_claims():
    s = _inbox_story(contract(inbox_text={"format_of": "inbox"}))
    assert {e.surface for e in s.messages()} == {"inbox", "inbox_text"}


# ---------------------------------------------------------------- validation

def test_the_declarations_are_validated():
    def problems(**changes):
        return [p for p in validate(contract(**changes)) if p not in validate(BASE)]
    assert problems(inbox_text={"format_of": "inbox"}) == []
    assert problems(fare_detail={"shown_before_action": True}) == []
    assert problems(inbox_text={"format_of": "nowhere"}) == ["surface inbox_text: format_of names unknown surface 'nowhere'"]
    assert problems(inbox_text={"format_of": "inbox_text"}) == ["surface inbox_text: format_of names itself"]
    assert problems(inbox_text={"format_of": "confirmation"}) == \
        ["surface inbox_text: format_of 'confirmation' is a web surface, not email"]
    assert problems(inbox={"shown_before_action": True}) == \
        ["surface inbox: shown_before_action needs reached_by (the step whose action it precedes)"]
