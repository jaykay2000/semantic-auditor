"""must: agree_across_surfaces (docs/03 `fact_divergence`): the same fact must read the same on every surface one
persona sees, in the same state. No oracle. Built generically (no app vocabulary in the core)."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from semaudit.relate.rules import eval_agree_across_surfaces  # noqa: E402
from semaudit.story.model import Event, Extraction, Story  # noqa: E402

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
RULE = SimpleNamespace(id="C1", check={"claims": ["annual_limit"], "must": "agree_across_surfaces"})


def msg(i, surface, value, minutes, fact="annual_limit"):
    x = Extraction(message_kind="information", decision="none", action="none", strength="inform",
                   urgency_cue="none", explains_own_tradeoff=False,
                   claims=[{"type": fact, "value": value, "unit": "USD"}])
    return Event(id=i, at=T0 + timedelta(minutes=minutes), kind="message", feature="f", surface=surface,
                 text=f"{value}", extraction=x)


def run(*events):
    return {(x.subject, x.status, tuple(x.meta.get("events", []))) for x in
            eval_agree_across_surfaces(RULE, Story(id="s", release="r", persona="p", events=list(events)))}


def test_two_surfaces_disagreeing_is_a_violation_on_both():
    got = run(msg("page", "report", 24500, 0), msg("export", "export", 32500, 1))
    assert got == {("page", "violated", ("page", "export")), ("export", "violated", ("export", "page"))}


def test_agreeing_surfaces_pass_and_one_surface_alone_is_not_checked():
    assert run(msg("page", "report", 32500, 0), msg("export", "export", 32500, 1)) == \
        {("page", "passed", ()), ("export", "passed", ())}
    assert run(msg("page", "report", 24500, 0), msg("again", "report", 32500, 1)) == set()   # same surface


def test_a_state_change_between_them_is_not_a_disagreement():
    act = Event(id="a", at=T0 + timedelta(minutes=1), kind="user_action", action="update", effects={"x": 1})
    assert run(msg("page", "report", 24500, 0), act, msg("export", "export", 32500, 2)) == set()


def test_an_unreadable_claim_is_never_a_disagreement():
    assert run(msg("page", "report", None, 0), msg("export", "export", 32500, 1)) == set()


def test_the_verifier_re_derives_the_disagreement_from_the_cited_messages():
    from semaudit.relate.rules import Entry
    from semaudit.verify.steps import _step_agreement
    page, export = msg("page", "report", 24500, 0), msg("export", "export", 32500, 1)
    story = Story(id="s", release="r", persona="p", events=[page, export])
    occ = lambda ids: SimpleNamespace(persona="p", entry=Entry("C1", "page", "violated", meta={"events": ids}))  # noqa: E731
    assert _step_agreement(SimpleNamespace(occurrences=[occ(["page", "export"])]), {"p": story},
                           {"annual_limit"})["result"] == "pass"
    assert _step_agreement(SimpleNamespace(occurrences=[occ(["page"])]), {"p": story},
                           {"annual_limit"})["result"] == "fail"           # nothing to disagree with


def test_other_facts_are_ignored():
    assert run(msg("page", "report", 24500, 0), msg("export", "export", 7500, 1, fact="other")) == set()
