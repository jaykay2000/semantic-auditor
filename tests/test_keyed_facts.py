"""Keyed (family) facts: a fact like "a dollar amount an action asks for" covers many different quantities. Two of
its claims are compared only when every key field names the same known value, so a $7,000 IRA move never reads
as disagreeing with a $24,500 401(k) move, while two surfaces quoting different amounts for the SAME move do."""
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from semaudit.contract.schema import Fact  # noqa: E402
from semaudit.extract.messages import _claim_schema, key_prompt  # noqa: E402
from semaudit.relate.claims import same_quantity  # noqa: E402
from semaudit.relate.rules import Entry, eval_agree_across_surfaces  # noqa: E402
from semaudit.story.model import Event, Extraction, Story  # noqa: E402
from semaudit.verify.steps import _step_agreement  # noqa: E402

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
MOVE = Fact(id="move_amount", unit="USD", key=[
    {"field": "action", "values": ["raise_retirement_saving", "pay_down_debt"], "describe": "the action it is for"},
    {"field": "per", "values": ["once", "month", "year"]}])
SCORE = Fact(id="score", unit="points")
CONTRACT = SimpleNamespace(facts=[MOVE, SCORE], state=[])
RULE = SimpleNamespace(id="U2", check={"claims": ["move_amount", "score"], "must": "agree_across_surfaces"})


def msg(i, surface, value, minutes, fact="move_amount", **key):
    x = Extraction(message_kind="information", decision="none", action="none", strength="inform",
                   urgency_cue="none", explains_own_tradeoff=False,
                   claims=[{"type": fact, "value": value, "unit": "USD", **key}])
    return Event(id=i, at=T0 + timedelta(minutes=minutes), kind="message", feature="f", surface=surface,
                 text=str(value), extraction=x)


def verdicts(*events):
    story = Story(id="s", release="r", persona="p", events=list(events))
    return {(x.subject, x.status) for x in eval_agree_across_surfaces(RULE, story, CONTRACT)}, story


RET = {"action": "raise_retirement_saving", "per": "year"}


def test_the_same_move_quoted_differently_on_two_surfaces_disagrees():
    got, story = verdicts(msg("page", "report", 24500, 0, **RET), msg("export", "export", 32500, 1, **RET))
    assert got == {("page", "violated"), ("export", "violated")}
    occ = SimpleNamespace(persona="p", entry=Entry("U2", "page", "violated", meta={"events": ["page", "export"]}))
    assert _step_agreement(SimpleNamespace(occurrences=[occ]), {"p": story}, {"move_amount"}, [],
                           {f.id: f for f in CONTRACT.facts})["result"] == "pass"


def test_different_moves_are_different_quantities():
    debt = {"action": "pay_down_debt", "per": "year"}
    got, story = verdicts(msg("page", "report", 24500, 0, **RET), msg("export", "export", 7000, 1, **debt))
    assert got == set()
    occ = SimpleNamespace(persona="p", entry=Entry("U2", "page", "violated", meta={"events": ["page", "export"]}))
    assert _step_agreement(SimpleNamespace(occurrences=[occ]), {"p": story}, {"move_amount"}, [],
                           {f.id: f for f in CONTRACT.facts})["result"] == "fail"   # the verifier agrees


def test_a_different_period_is_a_different_quantity():
    got, _ = verdicts(msg("page", "report", 2042, 0, action="raise_retirement_saving", per="month"),
                      msg("export", "export", 24500, 1, **RET))
    assert got == set()


def test_an_unknown_missing_or_invented_key_is_never_compared():
    for other in ({"action": "unknown", "per": "year"}, {"per": "year"}, {"action": "buy_a_boat", "per": "year"},
                  {"action": None, "per": "year"}):
        got, _ = verdicts(msg("page", "report", 24500, 0, **RET), msg("export", "export", 32500, 1, **other))
        assert got == set(), other
    for both in ({"action": "unknown", "per": "year"}, {"action": "buy_a_boat", "per": "year"}):  # equal, still unknown
        got, _ = verdicts(msg("page", "report", 24500, 0, **both), msg("export", "export", 32500, 1, **both))
        assert got == set(), both


def test_a_plain_fact_is_compared_as_before():
    got, _ = verdicts(msg("a", "report", 71, 0, fact="score"), msg("b", "export", 64, 1, fact="score"))
    assert got == {("a", "violated"), ("b", "violated")}
    assert same_quantity(None, {}, {}) and same_quantity(SCORE, {}, {})


def test_the_extractor_is_asked_for_each_key_field_and_only_when_some_fact_is_keyed():
    s = _claim_schema(SimpleNamespace(facts=[MOVE, SCORE]))
    assert s["properties"]["action"]["enum"] == ["pay_down_debt", "raise_retirement_saving", "unknown", None]
    assert s["properties"]["per"]["enum"] == ["month", "once", "unknown", "year", None]
    assert {"action", "per"} <= set(s["required"])
    p = key_prompt(SimpleNamespace(facts=[MOVE, SCORE]))
    assert "move_amount" in p and "`action` (the action it is for: one of raise_retirement_saving" in p
    plain = _claim_schema(SimpleNamespace(facts=[SCORE]))
    assert set(plain["properties"]) == {"type", "value", "unit"} and key_prompt(SimpleNamespace(facts=[SCORE])) == ""


def test_a_field_free_in_one_fact_is_free_text_everywhere():
    free = Fact(id="note_amount", key=[{"field": "action"}])
    s = _claim_schema(SimpleNamespace(facts=[MOVE, free]))
    assert s["properties"]["action"] == {"type": ["string", "null"]}


def test_a_free_text_key_compares_case_blind_and_never_on_unknown():
    free = Fact(id="move_amount", key=[{"field": "account"}])
    c = SimpleNamespace(facts=[free], state=[])

    def run(ka, kb):
        story = Story(id="s", release="r", persona="p", events=[msg("a", "report", 1, 0, account=ka),
                                                                  msg("b", "export", 2, 1, account=kb)])
        return {x.status for x in eval_agree_across_surfaces(RULE, story, c)}
    assert run("IRA", "ira") == {"violated"}
    assert run("unknown", "unknown") == set() and run("IRA", "401k") == set() and run("", "") == set()
    assert run("other", "other") == set()                        # a catch-all names no single quantity
