"""An action the app offered and then failed is a finding, not a hole in the measurement.

Found on Medusa v2.18.0 (2026-11-05): after a shopper removed a promotion on the review step, the store left only a
disabled "Select a payment method" button. The adapter recorded the step as failed, and SRA excluded the whole
shopper from the release as "not measured": the defect, and every figure the shopper had already seen, disappeared
from the review. Of the fixes Spree shipped in the 16 days after 6.0.0, seven were shopper actions that errored or
pages that went missing (docs/evidence/escape-backtest-spree-6.0).

An adapter now says who failed: AppFailed (the app refused or failed it) or any other exception (the harness could
not do the step). Only the second is a hole.
"""
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from semaudit.adapters.base import AppFailed, StepFailed, StepResult
from semaudit.capture.runner import Runner, _EpisodeCtx
from semaudit.contract.schema import Step
from semaudit.decide.pipeline import blocked_steps, measurement_problems
from semaudit.relate.rules import eval_offered_actions_complete
from semaudit.story.model import Event, Story

DAY0 = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)


class _Adapter:
    """place_order: the app leaves a disabled button; read_order_page then cannot run; open_home works."""

    def run_step(self, step, sess):
        if step.do == "place_order":
            raise AppFailed("the only button reads 'Select a payment method' (disabled)", landed="checkout")
        if step.do == "read_order_page":
            raise StepFailed("no order was placed in this episode")
        if step.do == "broken_selector":
            raise StepFailed("selector #pay not found")
        if step.do == "app_error_result":
            return StepResult(landed="cart", error="HTTP 500 from POST /store/carts/x/promotions")
        return StepResult(landed="home")

    def oracle_params(self, persona, sess):
        return {}


def _runner():
    r = object.__new__(Runner)
    r._adapter = _Adapter()
    r.contract = SimpleNamespace(surfaces=[])
    r.captured = []
    r._capture_page = lambda ectx, sess, surface, chat=None: r.captured.append(surface)
    r._drain = lambda ectx, surfaces, sctx: []
    return r


def _run(dos):
    r = _runner()
    ectx = _EpisodeCtx(release="v1", persona=SimpleNamespace(id="jonas"), scenario=SimpleNamespace(day0=DAY0),
                       app=None, out_dir=Path("/nonexistent"))
    hooks = SimpleNamespace(has=lambda _: False)
    oracles = SimpleNamespace(snapshot=lambda _: {})
    sess = SimpleNamespace(persona=ectx.persona)
    recs = [r._run_step(ectx, sess, hooks, oracles, None, i, Step(at=f"D0 10:{i:02d}", do=d))
            for i, d in enumerate(dos, 1)]
    return recs, r.captured


def test_an_app_refusal_is_app_failed_and_what_the_user_saw_is_captured():
    recs, captured = _run(["open_home", "place_order"])
    assert [x.status for x in recs] == ["done", "app_failed"]
    assert "Select a payment method" in recs[1].error
    assert captured == ["home", "checkout"]


def test_a_step_that_fails_after_an_app_failure_is_blocked_not_a_harness_fault():
    recs, _ = _run(["place_order", "read_order_page", "open_home"])
    assert [x.status for x in recs] == ["app_failed", "blocked", "done"]
    assert recs[1].error.startswith("after step 1 (place_order) failed in the app:")


def test_a_harness_failure_with_no_app_failure_before_it_is_still_a_hole():
    recs, _ = _run(["open_home", "broken_selector"])
    assert [x.status for x in recs] == ["done", "failed"]


def test_an_error_the_adapter_returns_is_the_app_answering_with_a_failure():
    recs, captured = _run(["app_error_result"])
    assert recs[0].status == "app_failed" and "HTTP 500" in recs[0].error and captured == ["cart"]


def _ep(statuses):
    steps = [SimpleNamespace(seq=i, do=f"s{i}", status=s, error=f"e{i}", state={}) for i, s in enumerate(statuses, 1)]
    return SimpleNamespace(steps=steps, captures=lambda: [], not_measured=[], initial_state={})


def test_app_failed_and_blocked_steps_do_not_exclude_the_persona_but_are_reported():
    ep = _ep(["done", "app_failed", "blocked"])
    assert measurement_problems(ep) == []
    assert blocked_steps(ep) == ["step 3 (s3): e3"]
    assert measurement_problems(_ep(["done", "failed"])) == ["step 2 (s2): e2"]


def _story():
    t = lambda m: DAY0.replace(minute=m)  # noqa: E731
    return Story(id="s", release="r", persona="p", events=[
        Event(id="a01_open_home", at=t(1), kind="user_action", action="open_home"),
        Event(id="a02_place_order", at=t(2), kind="failed_action", action="place_order",
              copy_key="action:place_order", text="disabled 'Select a payment method'")])


def test_the_rule_raises_the_failed_action_and_passes_the_completed_ones():
    rule = SimpleNamespace(id="R0", check={"must": "offered_actions_complete"})
    got = {e.subject: e.status for e in eval_offered_actions_complete(rule, _story())}
    assert got == {"a01_open_home": "passed", "a02_place_order": "violated"}


def test_the_rule_can_be_limited_to_some_actions():
    rule = SimpleNamespace(id="R0", check={"must": "offered_actions_complete", "actions": ["open_home"]})
    assert [e.status for e in eval_offered_actions_complete(rule, _story())] == ["passed"]


def test_a_failed_action_changes_no_state():
    s = _story()
    var = SimpleNamespace(id="order_status", kind="plain", initial="not_placed", set_by={"place_order": "placed"})
    assert s.state_at(DAY0.replace(minute=59), [var]) == {"order_status": "not_placed"}
