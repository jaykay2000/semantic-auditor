"""Word-valued claims (a first move named by its action id) and agree_across_states (the same figure before and
after a state change such as signing up). Both generic: no app vocabulary in the core."""
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from semaudit.contract.schema import Fact, StateVar  # noqa: E402
from semaudit.extract.messages import _claim_schema, word_prompt  # noqa: E402
from semaudit.relate.claims import MATCH, MISMATCH, UNREADABLE, compare, shown, stated  # noqa: E402
from semaudit.relate.rules import Entry, eval_agree_across_states, eval_agree_across_surfaces  # noqa: E402
from semaudit.story.model import Event, Extraction, Story  # noqa: E402
from semaudit.verify.steps import _step_states  # noqa: E402

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
FIRST = Fact(id="first_move", unit="action_id", words=["pay_down_debt", "raise_retirement_saving", "deploy_idle_cash"])
SCORE = Fact(id="score", unit="points")
ACCOUNT = StateVar(id="account", initial="guest", set_by={"sign_up": "signed_in"})
PLAN = StateVar(id="plan", kind="step_param", param="hold", values=["held", "released"], default="released")
C = SimpleNamespace(facts=[FIRST, SCORE], state=[ACCOUNT, PLAN], rule=lambda i: STATES)
SURF = SimpleNamespace(id="U3", check={"claims": ["first_move"], "must": "agree_across_surfaces"})
STATES = SimpleNamespace(id="U4", check={"claims": ["first_move", "score"], "must": "agree_across_states",
                                         "states": {"account": ["guest", "signed_in"]}})


def msg(i, surface, minutes, fact="first_move", **c):
    x = Extraction(message_kind="information", decision="none", action="none", strength="inform",
                   urgency_cue="none", explains_own_tradeoff=False, claims=[{"type": fact, "unit": "", **c}])
    return Event(id=i, at=T0 + timedelta(minutes=minutes), kind="message", feature="f", surface=surface,
                 text=i, copy_key=f"f.{i}", extraction=x)


def act(i, minutes, action, **params):
    return Event(id=i, at=T0 + timedelta(minutes=minutes), kind="user_action", action=action, params=params)


def test_words_compare_exactly_and_unknown_is_unreadable():
    c = lambda w: {"type": "first_move", "value": None, "word": w}  # noqa: E731
    assert compare(c("Pay_Down_Debt"), "pay_down_debt") == MATCH
    assert compare(c("pay_down_debt"), "raise_retirement_saving") == MISMATCH
    assert compare(c("unknown"), "pay_down_debt") == UNREADABLE and compare(c("other"), "pay_down_debt") == UNREADABLE
    assert stated(c("unknown")) is None and stated(c("deploy_idle_cash")) == "deploy_idle_cash"
    assert shown(c("deploy_idle_cash")) == "deploy_idle_cash"
    assert compare({"value": 42.0}, 42) == MATCH                                      # numbers unchanged


def test_two_surfaces_naming_different_first_moves_disagree():
    story = Story(id="s", release="r", persona="p", events=[
        msg("dash", "dashboard", 0, value=None, word="deploy_idle_cash"),
        msg("pdf", "pdf_report", 1, value=None, word="raise_retirement_saving"),
        msg("export", "ai_export", 2, value=None, word="raise_retirement_saving")])
    got = {(x.subject, x.status) for x in eval_agree_across_surfaces(SURF, story, C)}
    assert got == {("dash", "violated"), ("pdf", "violated"), ("export", "violated")}


def test_the_schema_and_prompt_carry_words_only_when_a_fact_is_word_valued():
    s = _claim_schema(C)
    assert s["properties"]["word"]["enum"][-1] is None and "unknown" in s["properties"]["word"]["enum"]
    assert s["properties"]["value"] == {"type": ["number", "null"]} and "word" in s["required"]
    assert "first_move: one of pay_down_debt" in word_prompt(C)
    assert "word" not in _claim_schema(SimpleNamespace(facts=[SCORE]))["properties"]
    assert word_prompt(SimpleNamespace(facts=[SCORE])) == ""


def journey(*after):
    return Story(id="s", release="r", persona="p", events=[
        act("a1", 0, "open", hold="released"),
        msg("guest_first", "guest_report", 1, value=None, word="raise_retirement_saving"),
        msg("guest_score", "guest_report", 1, fact="score", value=55),
        act("a2", 2, "sign_up", hold="released"), *after])


def test_a_first_move_that_changes_at_sign_up_is_a_violation():
    story = journey(msg("auth_first", "signed_in_report", 3, value=None, word="deploy_idle_cash"),
                    msg("auth_score", "signed_in_report", 3, fact="score", value=55))
    got = {(x.subject, x.status, x.meta.get("fact")) for x in eval_agree_across_states(STATES, story, C)}
    assert got == {("guest_first", "violated", "first_move"), ("guest_score", "passed", None)}
    occ = SimpleNamespace(persona="p", entry=Entry("U4", "guest_first", "violated",
                                                   meta={"events": ["guest_first", "auth_first"]}))
    assert _step_states(SimpleNamespace(rule="U4", occurrences=[occ]), {"p": story}, C)["result"] == "pass"


def test_only_the_named_change_separates_them():
    # the plan state differs too (held after sign-up): not the change the rule is about, so not compared
    story = journey(act("a3", 3, "open", hold="held"),
                    msg("auth_first", "signed_in_report", 4, value=None, word="deploy_idle_cash"))
    assert eval_agree_across_states(STATES, story, C) == []
    # the same state on both sides (no sign-up) is agree_across_surfaces' job, not this rule's
    same = Story(id="s", release="r", persona="p", events=[
        msg("a", "guest_report", 1, value=None, word="raise_retirement_saving"),
        msg("b", "ai_export", 2, value=None, word="deploy_idle_cash")])
    assert eval_agree_across_states(STATES, same, C) == []


def test_a_change_in_the_true_value_between_the_two_is_not_a_violation():
    story = journey(msg("auth_score", "signed_in_report", 3, fact="score", value=61))
    story.snapshots = [{"at": T0, "truth": {"score": 55}}, {"at": T0 + timedelta(minutes=2, seconds=30),
                                                         "truth": {"score": 61}}]
    assert [x for x in eval_agree_across_states(STATES, story, C) if x.status == "violated"] == []


def test_a_persona_reference_value_is_the_truth_when_no_oracle_reads_the_fact():
    from semaudit.relate.rules import eval_match_oracle
    story = Story(id="s", release="r", persona="p", truth={"limit_401k": 35750}, events=[
        msg("page", "report", 0, fact="limit_401k", value=24500, role="limit"),
        msg("pdf", "pdf_report", 1, fact="limit_401k", value=35750, role="limit")])
    rule = SimpleNamespace(id="R", check={"claims": ["limit_401k"], "must": "match_oracle"})
    assert eval_match_oracle(rule, story) == []                       # a limit claim does not state a current value
    lim = SimpleNamespace(facts=[Fact(id="limit_401k", truth_roles=["limit", "proposed"])])
    assert {(x.subject, x.status) for x in eval_match_oracle(rule, story, lim)} == \
        {("page", "violated"), ("pdf", "passed")}                     # ...unless the fact IS the limit
    snap = story.model_copy(update={"snapshots": [{"at": T0, "truth": {"limit_401k": 24500}}]})
    assert snap.truth_at("limit_401k", T0 + timedelta(minutes=1)) == 24500   # a measured oracle reading wins


def test_story_building_carries_the_persona_reference():
    import inspect

    from semaudit.story import build
    assert "truth=dict(persona.reference)" in inspect.getsource(build.story_from_episode)


def test_an_event_sent_email_surface_is_measured_without_a_clock():
    import inspect

    from semaudit.capture import runner
    from semaudit.contract.schema import Surface
    assert Surface(id="e", kind="email", locator="message_id", sink="outbox").timed is True
    assert Surface(id="e", kind="email", locator="message_id", sink="outbox", timed=False).timed is False
    assert 'if not hooks.has("clock") and s.timed:' in inspect.getsource(runner)
