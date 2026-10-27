"""W4: the scenario runner drives Northbound for real (launched per release, a real Chromium) and its episodes
match the hand-authored stories in tests/fixtures/stories/.

Parity is checked on every marked message: key, feature, channel, surface, component, text, order and time to the
second. Two documented differences between fixture and app are tolerated, and nothing else is:

* build.py adds a 5 s / 10 s "render" gap after some actions (a card at 10:00:05 after a 10:00:00 search); the app
  renders at the request instant, so a page or chat message may be 0, 5 or 10 s earlier than the fixture row.
  Emails and pushes are sent by jobs and must match exactly.
* email and push sink documents carry no component (only page markup has `data-component`), so their component is
  not compared; the fixtures say "flight" for all of them.
* the fixtures use the copy key of the TEXT for the forecast email (`pw.card`); the app's template id is
  `pw.email.forecast` (same text). ALIASES lists exactly those pairs.

Extras the fixtures do not list are allowlisted explicitly: every `core` message (pages, confirmation email, PDF)
and the few non-core ones named in NON_CORE_EXTRAS, each with its reason.
"""

import json
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.adapters.base import StepFailed, StepResult, load_adapter  # noqa: E402
from semaudit.capture import Runner  # noqa: E402
from semaudit.capture.runner import Runner as RunnerClass  # noqa: E402
from semaudit.contract.schema import Scenario, Step, load_contract  # noqa: E402
from semaudit.story.episode import Episode  # noqa: E402

CONTRACT = ROOT / "examples" / "northbound" / "contract"
FIX = ROOT / "tests" / "fixtures" / "stories"

ALIASES = {("pw.card", "pw.email.forecast"), ("pw.card.nodrop", "pw.email.forecast.nodrop")}
RENDER_OFFSETS = {timedelta(0), timedelta(seconds=5), timedelta(seconds=10)}
# Non-core messages the app really shows that the hand-authored fixtures leave out (everything else must match).
NON_CORE_EXTRAS = {
    "cg.greeting": "every load of the chat page shows the Concierge greeting; the fixtures only list answers and tips",
    "pw.card.optin": "2.3 search page offers Price Watch opt-in; maya_23 starts at the opt-in click",
    "pw.card.watching": "2.3 search page after the opt-in click",
    "cg.answer.deal.booked": "2.3 Concierge answer at D2; maya_23's story stops at the booking",
}


# ---------------------------------------------------------------------------------------------------- helpers
def when(s) -> datetime:
    return datetime.fromisoformat(s)


def fixture_events(name, drop_keys=()):
    story = json.loads((FIX / f"{name}.json").read_text())["story"]
    return [e for e in story["events"] if e["kind"] == "message" and e["copy_key"] not in drop_keys]


def channel(m) -> str:
    if m["kind"] in ("email", "push"):
        return m["kind"]
    return next(c[4:] for c in m["attrs"].get("class", "").split() if c.startswith("msg-"))


def norm(t: str) -> str:
    return " ".join(t.split())


def check_capture_windows(ep: Episode) -> None:
    """Each email/push is captured by the step whose clock `set` delivered it, never later; pages at their step."""
    prev = datetime.min.replace(tzinfo=ep.steps[0].at.tzinfo)
    for st in ep.steps:
        for cap in st.captures:
            if cap.kind in ("email", "push"):
                assert cap.phase == "step", f"{cap.id} ({cap.elements[0].attrs.get('X-Message-Key')}) only found at the final drain"
                assert prev < cap.at <= st.at, f"{cap.id} sent {cap.at} captured at step {st.seq} ({prev}..{st.at}]"
            elif cap.kind == "web":
                assert cap.at == st.at
        prev = st.at


def assert_parity(ep: Episode, fixture, *, extra_ok=()):
    check_capture_windows(ep)
    obs = [m for m in ep.messages() if m["feature"] != "core" and m["key"] not in extra_ok]
    obs.sort(key=lambda m: when(m["shown_at"]))
    fixture = sorted(fixture, key=lambda f: when(f["at"]))      # maya_r.json appends its inline card after the later events
    got = [(m["shown_at"][11:19], m["feature"], m["surface"], channel(m), m["key"]) for m in obs]
    want = [(f["at"][11:19], f["feature"], f["surface"], f["channel"], f["copy_key"]) for f in fixture]
    assert len(obs) == len(fixture), f"messages differ:\n captured {got}\n fixture  {want}"
    for m, f in zip(obs, fixture):
        label = f"{m['key']} / {f['copy_key']}"
        assert (m["feature"], m["surface"], channel(m)) == (f["feature"], f["surface"], f["channel"]), label
        if m["kind"] not in ("email", "push"):
            assert m["component"] == f["component"], label
        assert m["key"] == f["copy_key"] or (f["copy_key"], m["key"]) in ALIASES, label
        assert norm(m["text"]) == norm(f["text"]), label
        gap = when(f["at"]) - when(m["shown_at"])
        if channel(m) in ("email", "push"):
            assert gap == timedelta(0), f"{label}: job-sent, must match to the second, off by {gap}"
        else:
            assert gap in RENDER_OFFSETS, f"{label}: fixture {f['at']} vs captured {m['shown_at']}"


# ------------------------------------------------------------------------------------------------ the runner
@pytest.fixture(scope="module")
def browser():
    """One Chromium for the module (Playwright's sync API allows one per thread); each Runner launches its own app."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        yield b
        b.close()


@pytest.fixture(scope="module")
def runner(tmp_path_factory, browser):
    with Runner(CONTRACT, runs_dir=tmp_path_factory.mktemp("runs"), run_id="t", browser=browser) as r:
        yield r


_cache: dict = {}


@pytest.fixture(scope="module")
def run(runner):
    def go(release, persona) -> Episode:
        if (release, persona) not in _cache:
            (ep,) = runner.capture(release, [persona])
            _cache[(release, persona)] = ep
        return _cache[(release, persona)]
    return go


# ---------------------------------------------------------------------------------------------- story parity
PARITY_24 = ["maya", "maya_r", "lena", "raj", "raj_x", "raj_72h", "raj_72h_30s", "raj_72h_1m", "kai", "hana",
             "omar", "sam_alex", "theo"]


@pytest.mark.parametrize("persona", PARITY_24)
def test_story_parity_on_2_4(run, persona):
    ep = run("2.4", persona)
    assert [s.status for s in ep.steps].count("failed") == 0, [(s.do, s.error) for s in ep.steps if s.error]
    assert_parity(ep, fixture_events(persona), extra_ok={"cg.greeting"})


def test_story_parity_rina_on_2_4_1(run):
    ep = run("2.4.1", "rina")
    assert_parity(ep, fixture_events("rina"))
    (m,) = [m for m in ep.messages() if m["key"] == "fl.hotel.urgent"]
    assert m["component"] == "hotel" and m["surface"] == "hotel_detail"


def test_story_parity_maya_on_2_4_1(run):
    """No fixture exists for maya on 2.4.1, so it is derived by the README's 2.4.1 table from maya_r: the inline
    reconcile is for everyone, follow-ups stop after booking (no pw.email.after, no pw.push.moving)."""
    ep = run("2.4.1", "maya")
    assert_parity(ep, fixture_events("maya_r", drop_keys={"pw.email.after", "pw.push.moving"}), extra_ok={"cg.greeting"})
    assert [m["key"] for m in ep.messages() if m["kind"] in ("email", "push")] == [
        "pw.email.forecast", "core.email.confirmation"]


def test_story_parity_maya_on_2_3(run):
    ep = run("2.3", "maya")
    assert_parity(ep, fixture_events("maya_23"), extra_ok=set(NON_CORE_EXTRAS))
    keys = {m["key"] for m in ep.messages()}
    assert "pw.card.optin" in keys and "pw.card.watching" in keys           # 2.3: opt-in offered, then watching
    assert not {k for k in keys if k.startswith("fl.")}                    # no Fare Lock in 2.3


def test_the_family_smoke(run):
    ep = run("2.4", "family")
    assert [s.status for s in ep.steps].count("failed") == 0
    final = ep.steps[-1].state["booking"].values
    assert final["status"] == "booked" and final["party"] if "party" in final else True
    assert final["total_cents"] == 4 * (12_900 + 2_400)                      # NC4: persona-specific totals
    keys = [m["key"] for m in ep.messages()]
    assert "core.email.confirmation" in keys and "core.confirmed" in keys and "fl.banner" in keys
    pdf = next(c for c in ep.captures() if c.kind == "pdf")
    assert any("612" in e.text for e in pdf.elements) and pdf.meta["pages"] == 1


# --------------------------------------------------------------------------------------------------- state
def test_booking_state_before_and_after_book(run):
    ep = run("2.4", "maya")
    before, after = ep.step(4).state["booking"].values, ep.step(5).state["booking"].values
    assert before["status"] == "not_booked" and after["status"] == "booked"
    assert after["fare_type"] == "non_refundable" and after["within_change_window"] is True   # 10:06, window is 24 h
    assert ep.step(9).state["booking"].values["within_change_window"] is False                  # D2: closed
    assert ep.initial_state["booking"].values["status"] == "not_booked"
    assert [c["what"] for c in after["charges"]] == ["fare", "taxes_and_fees"]


def test_omar_inventory_and_the_bucket_the_banner_shows(run):
    ep = run("2.4", "omar")
    assert ep.steps[-1].state["inventory"].values["seats_left"] == 9          # the oracle
    banner = next(m for m in ep.messages() if m["key"] == "fl.banner.urgent")
    assert "only 2 seats left" in banner["text"]                                # the bucket the page shows


def test_sam_alex_lock_charge(run):
    ep = run("2.4", "sam_alex")
    st = ep.step(4).state["booking"].values
    (lock,) = [c for c in st["charges"] if c["what"] == "fare_lock"]
    assert lock["amount_cents"] == 1800 and st["status"] == "not_booked" and st["total_cents"] == 1800
    assert ep.step(3).state["booking"].values["charges"] == []                 # nothing charged before the lock


def test_hotel_persona_reads_room_inventory_and_flight_oracles_are_not_applicable(run):
    ep = run("2.4.1", "rina")
    st = ep.steps[-1].state
    assert st["room_inventory"].status == "ok" and st["room_inventory"].values["rooms_left"] == 1
    assert st["inventory"].status == "not_applicable" and "fare" in st["inventory"].error


# ----------------------------------------------------------------------------------------- the runner itself
def test_when_offered_is_done_on_2_3_and_skipped_on_2_4(run):
    old, new = run("2.3", "maya").step(2), run("2.4", "maya").step(2)
    assert old.do == new.do == "opt_in_price_watch" and old.when_offered
    assert old.status == "done" and new.status == "skipped_not_offered" and new.captures == [] and new.error is None


def test_a_surface_the_release_does_not_have_is_recorded_as_failed_not_absent(run):
    ep = run("2.4", "rina")                                                     # hotels arrive in 2.4.1
    (st,) = ep.steps
    assert st.status == "failed" and "404" in st.error
    assert not [m for m in ep.messages() if m["feature"] == "fare_lock"]


def test_episode_shape_ids_files_and_locators(run, runner):
    ep = run("2.4", "maya")
    caps = ep.captures()
    ids = [c.id for c in caps]
    assert len(ids) == len(set(ids)) and ids[0] == "2.4.maya.S-book-flexible.s01.c01"
    for c in caps:
        for role, rel in c.files.items():
            assert (runner.run_dir / rel).is_file(), (c.id, role)
    web = next(c for c in caps if c.surface == "fare_detail")
    el = next(e for e in web.elements if e.attrs["data-message-key"] == "fl.banner")
    assert el.locator["kind"] == "css" and el.bbox.width > 0 and el.attrs["data-feature"] == "fare_lock"
    assert el.attrs["data-shown-at"] == "2026-11-02T10:03:00+00:00"
    page = (runner.run_dir / web.files["dom"]).read_text()
    assert page.count("data-message-key") >= 2
    email = next(c for c in caps if c.kind == "email")
    assert email.elements[0].locator["kind"] == "message_id" and email.elements[0].attrs["X-Message-Key"] == "pw.email.forecast"
    push = next(c for c in caps if c.kind == "push")
    assert push.elements[0].locator["kind"] == "notification_id" and push.elements[0].text.startswith("Prices on LIS")
    chat = next(c for c in caps if c.kind == "chat")
    assert [e.attrs["who"] for e in chat.elements][-2:] == ["traveller", "concierge"]
    assert chat.elements[-1].locator == {"kind": "chat_turn", "turn": len(chat.elements) - 1, "span": [0, len(chat.elements[-1].text)]}
    pdf = next(c for c in caps if c.kind == "pdf")
    assert pdf.elements[0].locator["kind"] == "pdf_page" and "core.pdf.itinerary" in pdf.meta["Keywords"]
    assert Episode.read(runner.run_dir / "episodes" / "2.4" / "maya__S-book-flexible.json").id == ep.id


def test_every_sink_message_is_captured_once(run):
    ep = run("2.4", "maya")
    mids = [c.elements[0].attrs["message_id"] for c in ep.captures() if c.kind in ("email", "push")]
    assert len(mids) == len(set(mids)) == 4                                      # forecast, confirmation, after, push


# -------------------------------------------------------------------------------------------- determinism
def _stable(ep: Episode) -> dict:
    d = json.loads(ep.model_dump_json())
    d.pop("started_wall")
    return d


def test_the_same_episode_twice_is_identical(browser, tmp_path):
    out = []
    for i in range(2):
        with Runner(CONTRACT, browser=browser, runs_dir=tmp_path, run_id=f"det{i}") as r:
            (ep,) = r.capture("2.4", ["maya"])
        out.append(_stable(ep))
    assert out[0] == out[1]
    assert (tmp_path / "det0" / "episodes" / "2.4" / "maya__S-book-flexible.json").exists()


# --------------------------------------------------------------------------------------- failure is recorded
def _contract_with(steps, persona="maya", sid="S-test"):
    c = load_contract(CONTRACT)
    c.scenarios = [Scenario(id=sid, day0="2026-11-02T00:00:00Z", personas=[persona], steps=steps)]
    return c


def test_an_unknown_verb_fails_the_step_and_the_run_goes_on(browser, tmp_path):
    c = _contract_with([Step(at="D0 10:00", do="search", params={"route": "LIS-BER"}), Step(at="D0 10:01", do="teleport"),
                        Step(at="D0 10:03", do="open_fare", params={"pick": "cheapest"})])
    with Runner(CONTRACT, c, browser=browser, runs_dir=tmp_path) as r:
        (ep,) = r.capture("2.4", ["maya"])
    assert [s.status for s in ep.steps] == ["done", "failed", "done"]
    assert "unknown verb 'teleport'" in ep.steps[1].error
    assert not [c for c in ep.steps[1].captures if c.kind == "web"]            # nothing was shown by the failed verb
    assert ep.steps[2].captures and ep.steps[1].state["booking"].status == "ok"   # state still snapshotted


def test_a_broken_click_selector_is_a_failed_step(browser, tmp_path):
    base = load_adapter(load_contract(CONTRACT).app.adapter, CONTRACT)

    class Broken(type(base)):
        def verb_search(self, step, s):
            s.page.goto("/search")
            s.page.click("#no-such-button", timeout=300)
            return StepResult(landed="search_results")

    c = _contract_with([Step(at="D0 10:00", do="search", params={"route": "LIS-BER"})])
    with Runner(CONTRACT, c, browser=browser, runs_dir=tmp_path, adapter=Broken(), step_timeout_ms=500) as r:
        (ep,) = r.capture("2.4", ["maya"])
    assert ep.steps[0].status == "failed" and "Timeout" in ep.steps[0].error


def test_a_broken_message_selector_is_not_measured_never_a_silent_pass(browser, tmp_path):
    c = _contract_with([Step(at="D0 10:00", do="search", params={"route": "LIS-BER"})])
    c.surfaces = [s.model_copy(update={"message_selector": "[[ nope"}) if s.id == "search_results" else s
                  for s in c.surfaces]
    with Runner(CONTRACT, c, browser=browser, runs_dir=tmp_path) as r:
        (ep,) = r.capture("2.4", ["maya"])
    (cap,) = [x for x in ep.captures() if x.surface == "search_results"]
    assert cap.status == "not_measured" and "message_selector" in cap.error and cap.elements == []
    assert cap.files["dom"] and cap.files["screenshot"]                          # the page itself is still kept


def test_a_missing_clock_hook_marks_every_time_triggered_surface_not_measured(browser, tmp_path):
    c = _contract_with([Step(at="D0 10:00", do="search", params={"route": "LIS-BER"}),
                        Step(at="D0 10:03", do="check_inbox")])
    c.app.hooks = c.app.hooks.model_copy(update={"clock": None})
    with Runner(CONTRACT, c, browser=browser, runs_dir=tmp_path) as r:
        (ep,) = r.capture("2.4", ["maya"])
    assert ep.clock_measured is False and {n.surface for n in ep.not_measured} == {"inbox", "device"}
    assert all(s.clock is None for s in ep.steps)
    assert not [x for x in ep.captures() if x.kind == "email"]                  # nothing was driven, nothing is claimed


def test_a_release_that_will_not_boot_is_a_launch_error_not_a_pass(browser, tmp_path):
    from semaudit.capture import LaunchError
    c = load_contract(CONTRACT)
    c.app.launch = c.app.launch.model_copy(update={"cmd": ["{python}", "-c", "raise SystemExit(3)"], "startup_timeout": 5})
    with Runner(CONTRACT, c, browser=browser, runs_dir=tmp_path) as r, pytest.raises(LaunchError, match="exited with 3"):
        r.capture("2.4", ["maya"])


# -------------------------------------------------------------------------------------------- mutation checks
def test_mutation_no_sink_drain_between_steps_breaks_parity(browser, tmp_path, monkeypatch):
    real = RunnerClass._drain

    def only_final(self, ectx, surfaces, sctx):
        return [] if sctx.phase == "step" else real(self, ectx, surfaces, sctx)

    monkeypatch.setattr(RunnerClass, "_drain", only_final)
    with Runner(CONTRACT, browser=browser, runs_dir=tmp_path) as r:
        (ep,) = r.capture("2.4", ["maya"])
    with pytest.raises(AssertionError, match="final drain"):
        assert_parity(ep, fixture_events("maya"), extra_ok={"cg.greeting"})


def test_mutation_dropping_the_clock_set_breaks_parity(browser, tmp_path, monkeypatch):
    monkeypatch.setattr(RunnerClass, "_set_clock", staticmethod(lambda hooks, body: None))
    with Runner(CONTRACT, browser=browser, runs_dir=tmp_path) as r:
        (ep,) = r.capture("2.4", ["maya"])
    with pytest.raises(AssertionError):
        assert_parity(ep, fixture_events("maya"), extra_ok={"cg.greeting"})


def test_mutation_random_capture_ids_break_determinism(browser, tmp_path, monkeypatch):
    def random_id(self, ectx, sctx):
        sctx.n += 1
        return f"c-{uuid.uuid4().hex[:8]}"

    monkeypatch.setattr(RunnerClass, "_new_id", random_id)
    out = []
    for i in range(2):
        with Runner(CONTRACT, browser=browser, runs_dir=tmp_path, run_id=f"mut{i}") as r:
            (ep,) = r.capture("2.4", ["maya"])
        out.append(_stable(ep))
    assert out[0] != out[1]


# ------------------------------------------------------------------------------------------------------- CLI
def _cli(tmp_path, *args):
    import os
    import subprocess
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run([sys.executable, "-m", "semaudit.cli", "capture", "--contract", str(CONTRACT),
                           "--runs-dir", str(tmp_path), "--run-id", "cli", *args],
                          capture_output=True, text=True, env=env, cwd=ROOT)


def test_cli_capture_writes_episodes_and_exits_0(tmp_path):
    r = _cli(tmp_path, "--release", "2.4", "--persona", "theo")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "2.4/theo/S-direct-book: 3 done" in r.stdout
    assert Episode.read(tmp_path / "cli" / "episodes" / "2.4" / "theo__S-direct-book.json").persona == "theo"


def test_cli_capture_exits_2_when_something_could_not_be_measured(tmp_path):
    r = _cli(tmp_path, "--release", "2.4", "--persona", "rina")               # no hotel page before 2.4.1
    assert r.returncode == 2 and "not measured" in r.stdout and "404" in r.stdout


# ------------------------------------------------------------------------------- W6: episode -> story (no model)
from semaudit.contract.schema import load_contract as _load_contract  # noqa: E402
from semaudit.story.build import story_from_episode  # noqa: E402

sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
from extraction_gold import gold_for  # noqa: E402

_C = _load_contract(CONTRACT)


def test_story_from_maya_episode_orders_attributes_and_marks_initiative(run):
    s = story_from_episode(run("2.4", "maya"), _C)
    by = {e.id: e for e in s.messages()}
    assert by["pw.email.forecast"].channel == "email" and by["pw.push.moving"].channel == "push"
    assert by["pw.card"].channel not in (None, "page") and by["fl.banner"].channel not in (None, "page")
    assert by["cg.regret"].user_initiated and not by["cg.upgrade"].user_initiated
    assert by["cg.upgrade"].at == when("2026-11-02T13:00:00+00:00")
    assert all(e.topic == "booking" for e in s.messages() if e.feature == "core")
    assert [e.at for e in s.events] == sorted(e.at for e in s.events)
    assert [e.action for e in s.events if e.kind == "user_action"][:3] == ["search", "check_inbox", "open_fare"]


def test_story_truth_is_read_at_the_time_shown(run):
    s = story_from_episode(run("2.4", "maya"), _C)
    banner = next(e for e in s.messages() if e.copy_key == "fl.banner")
    assert s.truth_at("units_left", banner.at) == 2                      # before she books
    assert s.final_truth("units_left") == 1                              # after: her seat is gone
    lock = story_from_episode(run("2.4", "sam_alex"), _C)
    assert lock.final_truth("fee_total") == 18                           # 2 x EUR 9, the per-traveller bug
    assert lock.truth_at("fee_total", next(e for e in lock.messages() if e.copy_key == "fl.banner").at) is None


def test_every_captured_message_has_hand_authored_gold(run):
    for persona in PARITY_24:
        for e in story_from_episode(run("2.4", persona), _C).messages():
            assert gold_for(e.copy_key, e.text) is not None, f"{persona}: no gold for {e.copy_key}"


# ------------------------------------------------------------------------------- W7: base <-> head alignment
from semaudit.story.align import align  # noqa: E402


def _non_core(ids):
    return sorted(i for i in ids if not i.startswith(("core.", "a")))


def test_maya_diff_2_3_to_2_4(run):
    d = align(story_from_episode(run("2.3", "maya"), _C), story_from_episode(run("2.4", "maya"), _C))
    assert _non_core(d.added) == ["cg.upgrade", "fl.banner", "pw.email.after", "pw.push.moving"]
    assert _non_core(d.removed) == ["pw.card.watching"]
    fuzzy = {(p.base, p.head) for p in d.pairs if p.status == "fuzzy"}
    assert fuzzy == {("pw.card.optin", "pw.card"), ("cg.answer.deal.booked", "cg.regret")}
    assert d.head_status("pw.email.forecast") == "unchanged"


def test_maya_diff_2_4_to_2_4_1_shows_the_fixes(run):
    d = align(story_from_episode(run("2.4", "maya"), _C), story_from_episode(run("2.4.1", "maya"), _C))
    assert _non_core(d.removed) == ["pw.email.after", "pw.push.moving"]
    assert _non_core(d.added) == ["cg.reconcile"]


def test_alignment_never_pairs_across_slots(run):
    """Every head event is paired or added exactly once; fuzzy pairs share feature, surface, channel and time."""
    b, h = story_from_episode(run("2.3", "maya"), _C), story_from_episode(run("2.4", "maya"), _C)
    d = align(b, h)
    heads = [p.head for p in d.pairs] + d.added
    assert sorted(heads) == sorted(e.id for e in h.events)
    assert sorted([p.base for p in d.pairs] + d.removed) == sorted(e.id for e in b.events)
    be, he = {e.id: e for e in b.events}, {e.id: e for e in h.events}
    for p in d.pairs:
        if p.status == "fuzzy":
            x, y = be[p.base], he[p.head]
            assert (x.feature, x.surface, x.channel, x.at) == (y.feature, y.surface, y.channel, y.at)
