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


def test_a_surface_the_release_does_not_offer_is_recorded_as_not_offered(run):
    """The contract marks open_hotel 'only if offered': on 2.4 there are no hotel pages, recorded explicitly."""
    ep = run("2.4", "rina")                                                     # hotels arrive in 2.4.1
    (st,) = ep.steps
    assert st.status == "skipped_not_offered" and st.captures == []
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


def _contract_copy(tmp_path, edit):
    import shutil
    import yaml
    d = tmp_path / "contract"
    shutil.copytree(CONTRACT, d)
    app = yaml.safe_load((d / "app.yaml").read_text())
    app["launch"]["cwd"] = str(CONTRACT.parent)
    app["adapter"] = str(CONTRACT.parent / "adapter.py")
    (d / "app.yaml").write_text(yaml.safe_dump(app))
    data = yaml.safe_load((d / "scenarios.yaml").read_text())
    edit(data)
    (d / "scenarios.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    return d


def test_cli_capture_exits_2_when_something_could_not_be_measured(tmp_path):
    """Without 'only if offered', the same missing hotel page is a step that could not run: exit 2."""
    def required(sc):
        for s in sc:
            for st in s["steps"]:
                st.pop("when_offered", None)
    d = _contract_copy(tmp_path, required)
    import os
    import subprocess
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    r = subprocess.run([sys.executable, "-m", "semaudit.cli", "capture", "--contract", str(d), "--runs-dir",
                        str(tmp_path), "--run-id", "cli", "--release", "2.4", "--persona", "rina"],
                       capture_output=True, text=True, env=env, cwd=ROOT)
    assert r.returncode == 2 and "not measured" in r.stdout and "not offered" in r.stdout


# ------------------------------------------------------------------------------- W6: episode -> story (no model)
from semaudit.contract.schema import load_contract as _load_contract  # noqa: E402
from semaudit.story.build import story_from_episode  # noqa: E402

sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
from extraction_gold import gold_for  # noqa: E402
from stories.build import RECONCILES  # noqa: E402

_C = _load_contract(CONTRACT)
_C_DIR = CONTRACT


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
    assert lock.final_truth("fee_total", "fare_lock") == 18              # 2 x EUR 9, the per-traveller bug
    banner_at = next(e for e in lock.messages() if e.copy_key == "fl.banner").at
    assert lock.truth_at("fee_total", banner_at, "fare_lock") is None    # nothing charged yet when shown
    assert lock.final_truth("fee_total", "core") is None                 # another feature's fee: never the lock


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


# ------------------------------------------------------------- evidence lineage (audit P0): fails closed
import shutil as _shutil  # noqa: E402

from semaudit.verify.evidence import resolve  # noqa: E402


def test_every_captured_message_resolves_to_its_exact_capture(run, runner):
    ep = run("2.4", "maya")
    story = story_from_episode(ep, _C)
    results = [resolve(e, ep, runner.run_dir) for e in story.messages()]
    assert results and all(ok for ok, _ in results), [r for r in results if not r[0]]
    assert all(e.evidence.step and e.evidence.capture_id and e.evidence.locator for e in story.messages())


def test_evidence_fails_closed_on_tampering(run, runner, tmp_path):
    ep = run("2.4", "maya")
    story = story_from_episode(ep, _C)
    banner = next(e for e in story.messages() if e.copy_key == "fl.banner")
    altered = banner.model_copy(deep=True)
    altered.text = banner.text.replace("2 seats", "3 seats")
    assert resolve(altered, ep, runner.run_dir) == (False, "quoted text differs from the captured element")
    gone = banner.model_copy(deep=True)
    gone.evidence.capture_id = "no.such.capture"
    assert not resolve(gone, ep, runner.run_dir)[0]
    # a stored artifact edited after capture
    copy = tmp_path / "run"
    _shutil.copytree(runner.run_dir, copy)
    cap = next(c for c in ep.captures() if c.id == banner.evidence.capture_id)
    dom = copy / cap.files["dom"]
    dom.write_text(dom.read_text().replace("2 seats", "2 seat"))
    assert resolve(banner, ep, copy) == (False, "artifact dom changed since capture")
    no_ev = banner.model_copy(deep=True)
    no_ev.evidence = None
    assert resolve(no_ev, ep, runner.run_dir) == (False, "no evidence recorded")


# ---------------------------------------------------- W9: issues from real captures (gold extraction, no model)
from semaudit.decide.issues import apply_delta, build_issues  # noqa: E402
from semaudit.relate.rules import evaluate as _evaluate  # noqa: E402
from semaudit.story.model import Extraction as _Extraction  # noqa: E402

ALL = [p.id for p in _C.personas]


def _gold_results(run, release, contract=None):
    """Every measured persona on a release, with gold extraction and the fixture's P2 label (no model)."""
    contract = contract or _C
    sys.path.insert(0, str(ROOT / "scripts"))
    import json as _json

    import w8_run as W
    out = {}
    for persona in ALL:
        ep = run(release, persona)
        if any(s.status == "failed" for s in ep.steps):
            continue
        s = story_from_episode(ep, contract)
        for e in s.messages():
            e.extraction = _Extraction(**gold_for(e.copy_key, e.text))
        name = W.fixture_name(release, persona)
        fx = _json.loads((W.FIX / f"{name}.json").read_text()) if name else {"expected": []}
        p2 = next((x for x in fx["expected"] if x["rule"] == "P2"), None)
        rec = next((e.id for e in s.messages() if e.copy_key == "cg.reconcile"), "")   # gold: it reconciles
        if fx.get("gold_reconciler"):
            fe = next(x for x in fx["story"]["events"] if x["id"] == fx["gold_reconciler"])
            rec = next(e.id for e in s.messages() if e.copy_key == fe["copy_key"])
        label = p2["label"] if p2 else ("explained_tradeoff" if release == "2.4.1" else "compatible")
        adds = RECONCILES.get(next((e.copy_key for e in s.messages() if e.id == rec), ""), [])
        interp = lambda st, c, k, label=label, rec=rec, adds=adds: {"label": label, "reconciling_event_id": rec,  # noqa
                                                                     "addresses_actions": adds, "rationale": "g"}
        out[persona] = (s, _evaluate(s, contract, interp))
    return out


def test_issues_on_2_4_are_the_accepted_violations_grouped(run):
    issues = {i.id: i for i in build_issues("2.4", _gold_results(run, "2.4"), _C)}
    expect = {
        "I-2.4-P2-fare-lock-price-watch-unexplained-tradeoff": (["family", "maya", "sam_alex"], "critical"),
        "I-2.4-P2-fare-lock-price-watch-conflict": (["kai"], "critical"),
        "I-2.4-P1-fare-lock-fl-banner-urgent-a": (["hana", "raj_72h_1m", "raj_72h_30s"], "major"),
        "I-2.4-P1-fare-lock-fl-banner-urgent-bare-c": (["raj_x"], "major"),
        "I-2.4-U1-fare-lock-fl-banner-urgent": (["omar"], "major"),
        "I-2.4-U2-fare-lock-fl-banner": (["sam_alex"], "major"),
        "I-2.4-U3-price-watch-pw-email-after": (["family", "maya", "maya_r"], "minor"),
        "I-2.4-U4-concierge-cg-regret": (["family", "maya", "maya_r"], "minor"),
        "I-2.4-P3-story": (["family", "maya", "maya_r"], "minor"),
    }
    assert {k: (i.personas, i.severity["level"]) for k, i in issues.items()} == expect
    omar = issues["I-2.4-U1-fare-lock-fl-banner-urgent"].occurrences[0]
    assert [a.rule for a in omar.also] == ["P1"]          # one event, one issue: U1 first, P1 carried


def test_delta_2_4_to_2_4_1_resolves_the_fixes_and_flags_rina(run):
    head = build_issues("2.4.1", _gold_results(run, "2.4.1"), _C)
    base = build_issues("2.4", _gold_results(run, "2.4"), _C)
    measured = set(_gold_results(run, "2.4.1"))
    resolved = {i.id for i in apply_delta(head, base, set(_gold_results(run, "2.4")), measured)[0]}
    assert {"I-2.4-U3-price-watch-pw-email-after", "I-2.4-P3-story", "I-2.4-U2-fare-lock-fl-banner",
            "I-2.4-P2-fare-lock-price-watch-unexplained-tradeoff"} <= resolved
    kai = next(i for i in head if i.rule == "P2" and i.label == "conflict")      # not reconciled by cg.reconcile
    assert kai.personas == ["kai"] and kai.delta == "pre_existing"
    assert "I-2.4-P2-fare-lock-price-watch-conflict" not in resolved
    rina = next(i for i in head if i.personas == ["rina"])
    assert rina.delta == "new" and "nearest exception P1-E1 does not apply: scope" in rina.why
    assert next(i for i in head if i.rule == "U4").delta == "pre_existing"


# ---------------------------------------------- W10b: the Release Story page, driven in a real browser
from semaudit.decide.pipeline import ReleaseEval  # noqa: E402
from semaudit.report.page import build as _build_page  # noqa: E402
from semaudit.contract.approve import approval_state as _approval  # noqa: E402
from semaudit.report.review import assemble as _assemble  # noqa: E402
from semaudit.report.review import write as _write  # noqa: E402
from semaudit.verify.steps import verify as _verify  # noqa: E402


@pytest.fixture(scope="module")
def page_path(run, runner):
    evs = {}
    for rel in ("2.3", "2.4"):
        res = _gold_results(run, rel)
        evs[rel] = ReleaseEval(rel, {p: run(rel, p) for p in res}, res, {})
    head = build_issues("2.4", evs["2.4"].results, _C)
    resolved, _ = apply_delta(head, build_issues("2.3", evs["2.3"].results, _C), set(evs["2.3"].results),
                              set(evs["2.4"].results))
    stories = {p: s for p, (s, _) in evs["2.4"].results.items()}
    for i in head:                         # no model: cross-check and defense are recorded as not run
        _verify(i, stories, evs["2.4"].episodes, runner.run_dir, _C, None, repro=stories, models=False)
    out = runner.run_dir / "review-2.3-2.4.json"
    review = _assemble(evs["2.3"], evs["2.4"], _C, head, resolved, 0.0, approval=_approval(_C_DIR, _C),
                       review_path=str(out))
    path = _write(review, out)
    return _build_page(path)


def _open(browser, page_path, hash_=""):
    pg = browser.new_page(viewport={"width": 1600, "height": 1000})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: m.type == "error" and errors.append(m.text))
    pg.goto(page_path.resolve().as_uri() + hash_)
    pg.wait_for_selector("h1")
    return pg, errors


def test_page_opens_on_the_hero_with_its_issues_and_policy(browser, page_path):
    pg, errors = _open(browser, page_path)
    assert pg.inner_text("h1") == "Maya" and not errors, errors
    assert "Unexplained tradeoff" in pg.inner_text(".rail")
    # nothing in the contract is owner-approved yet: the policy's answer is shown, but only as provisional
    assert pg.inner_text(".rec") == "Provisional"
    assert "The policy would say Needs owner review" in pg.inner_text(".box.row")   # models off: partially verified
    assert pg.locator(".msg.sel").count() == 2                           # moments A and B ringed
    detail = pg.inner_text(".detail")
    assert "rule p2" in detail.lower() and "semaudit repro I-2.4-P2" in detail
    assert "not yet owner-approved" in detail.lower()
    assert {"Severity", "Confidence", "Verification"} <= {x.strip().title() for x in pg.locator(".detail .h").all_inner_texts()}
    # every quote on the page is the exact captured text
    texts = set(pg.locator(".quote").all_inner_texts())
    banner = next(e for e in story_from_episode(_cache[("2.4", "maya")], _C).messages() if e.copy_key == "fl.banner")
    assert f"“{banner.text}”" in texts
    pg.close()


def test_page_raj_has_nothing_raised_and_shows_his_rule_panel(browser, page_path):
    pg, errors = _open(browser, page_path, "#persona=raj&mode=head&issue=")
    assert pg.inner_text("h1") == "Raj" and not errors, errors
    assert "Nothing raised for Raj" in pg.inner_text(".rail")
    panel = pg.inner_text(".detail")
    assert "P1 applies" in panel and "excepted" in panel and "≤ 72 h" in panel
    assert "P2 not applicable" in panel
    pg.close()


def test_page_diff_mode_marks_added_and_removed(browser, page_path):
    pg, errors = _open(browser, page_path, "#persona=maya&mode=diff&issue=")
    assert not errors, errors
    badges = set(pg.locator(".badge").all_inner_texts())
    assert {"+ added", "− removed"} <= badges and pg.locator(".msg.ghost").count() > 0
    pg.close()


def test_page_deep_link_opens_kais_conflict(browser, page_path):
    pg, errors = _open(browser, page_path, "#persona=kai&mode=head&issue=I-2.4-P2-fare-lock-price-watch-conflict")
    assert not errors, errors
    assert "Conflicting advice" in pg.inner_text(".detail h2") and "incompatible" in pg.inner_text(".detail")
    pg.close()


def test_page_is_self_contained(page_path):
    html = page_path.read_text()
    assert "__REVIEW_JSON__" not in html and "<script src=" not in html     # data and code inline; no CDN
    shots = {e["capture"]["screenshot"] for p in json.loads(
        (page_path.parent.parent / "review-2.3-2.4.json").read_text())["personas"]
        for e in p["events"] if (e.get("capture") or {}).get("screenshot")}
    assert shots and all((page_path.parent / s).is_file() for s in shots)


def test_page_shows_issues_resolved_since_base(browser, run, runner, tmp_path):
    evs = {}
    for rel in ("2.4", "2.4.1"):
        res = _gold_results(run, rel)
        evs[rel] = ReleaseEval(rel, {p: run(rel, p) for p in res}, res, {})
    head = build_issues("2.4.1", evs["2.4.1"].results, _C)
    resolved, _ = apply_delta(head, build_issues("2.4", evs["2.4"].results, _C), set(evs["2.4"].results),
                              set(evs["2.4.1"].results))
    stories = {p: s for p, (s, _) in evs["2.4.1"].results.items()}
    for i in head:
        _verify(i, stories, evs["2.4.1"].episodes, runner.run_dir, _C, None, repro=stories, models=False)
    path = _write(_assemble(evs["2.4"], evs["2.4.1"], _C, head, resolved, 0.0, approval=_approval(_C_DIR, _C)),
                  runner.run_dir / "review-2.4-2.4.1.json")
    pg, errors = _open(browser, _build_page(path), "#persona=maya&mode=head&issue=")
    rail = pg.inner_text(".rail")
    assert not errors and "resolved since 2.4" in rail.lower() and "Unexplained tradeoff" in rail, errors
    pg.close()


# ---------------------------------------------- W11: owner decisions -> memory -> the next review (no model)
from semaudit.contract.approve import load_approvals as _load_approvals  # noqa: E402
from semaudit.contract.approve import rule_digest as _rule_digest  # noqa: E402
from semaudit.decide import memory as _mem  # noqa: E402
from semaudit.report import manifest as _mf  # noqa: E402
from semaudit.report.page import render as _render_page  # noqa: E402

KAI = "I-2.4-P2-fare-lock-price-watch-conflict"
TRADEOFF = "I-2.4-P2-fare-lock-price-watch-unexplained-tradeoff"
U4 = "I-2.4-U4-concierge-cg-regret"
RINA = "I-2.4.1-P1-fare-lock-fl-hotel-urgent-scope"
HANA = "I-2.4-P1-fare-lock-fl-banner-urgent-a"


def _review(run, runner, cdir, base, head, out):
    """The W9 review path on gold extraction, applying whatever the owner has decided in `cdir`."""
    rec = _mem.snapshot(cdir)
    c = _load_contract(cdir, memory=rec["issues"])
    evs = {}
    for rel in (base, head):
        res = _gold_results(run, rel, c)
        evs[rel] = ReleaseEval(rel, {p: run(rel, p) for p in res}, res, {})
    h = build_issues(head, evs[head].results, c)
    resolved, unconf = apply_delta(h, build_issues(base, evs[base].results, c), set(evs[base].results),
                                   set(evs[head].results))
    applied = _mem.apply(h, resolved, unconf, rec["issues"], c, {p: s for p, (s, _) in evs[head].results.items()})
    h = [i for i in h if all(i is not s for s in applied.set_aside)]
    stories = {p: s for p, (s, _) in evs[head].results.items()}
    for i in h:
        _verify(i, stories, evs[head].episodes, runner.run_dir, c, None, repro=stories, models=False)
    manifest = _mf.build(cdir, c, runner.run_dir, base, head, router=None, models=False, max_usd=0.0,
                         repro_run=None, memory=rec)
    review = _assemble(evs[base], evs[head], c, h, resolved, 0.0, approval=_approval(cdir, c), unconfirmed=unconf,
                       manifest=manifest, review_path=str(out), set_aside=applied.set_aside)
    return _write(review, out), json.loads(json.dumps(review, default=str))


@pytest.fixture
def owner(tmp_path):
    return _contract_copy(tmp_path, lambda data: None)


def test_fix_is_confirmed_when_resolved_and_raised_as_still_open_when_not(run, runner, owner, tmp_path):
    r24, _ = _review(run, runner, owner, "2.3", "2.4", tmp_path / "r24.json")
    _mem.decide_issue(r24, TRADEOFF, "fix", by="test", on="2026-10-27")
    _mem.decide_issue(r24, KAI, "fix", by="test", on="2026-10-27")
    _, r = _review(run, runner, owner, "2.4", "2.4.1", tmp_path / "r241.json")
    tradeoff = next(x for x in r["resolved"] if x["id"] == TRADEOFF)
    assert tradeoff["memory"]["status"] == "fix_confirmed" and tradeoff["memory"]["decision"] == "D-001"
    kai = next(x for x in r["issues"] if x["rule"] == "P2" and x["label"] == "conflict")
    assert kai["delta"] == "still_open" and kai["memory"]["decision"] == "D-002"
    assert "marked fix in D-002 on 2.4" in kai["delta_basis"]
    assert r["manifest"]["memory"]["sha256"] == _mem.digest(r["manifest"]["memory"]["issues"])


def test_not_an_issue_sets_aside_only_the_exact_signature_messages_and_personas(run, runner, owner, tmp_path):
    r24, _ = _review(run, runner, owner, "2.3", "2.4", tmp_path / "r24.json")
    d = _mem.decide_issue(r24, U4, "not_an_issue", by="test", reason="a gentle tip, not second-guessing",
                          on="2026-10-27")
    assert {o["persona"] for o in d["occurrences"]} == {"family", "maya", "maya_r"}
    _, r = _review(run, runner, owner, "2.4", "2.4.1", tmp_path / "r241.json")
    assert not [x for x in r["issues"] if x["rule"] == "U4"]
    aside = [x for x in r["not_raised"] if x["status"] == "owner_set_aside"]
    assert len(aside) == 1 and "a gentle tip" in aside[0]["reason"] and aside[0]["rule"] == "U4"
    # a variant -- one persona's message text differs from what the owner judged -- is raised, saying so
    data = _mem.load(owner)
    data["issues"][0]["occurrences"][0]["texts"] = ["something the owner never saw"]
    _mem.save(owner, data)
    _, r = _review(run, runner, owner, "2.4", "2.4.1", tmp_path / "r241b.json")
    u4 = next(x for x in r["issues"] if x["rule"] == "U4")
    assert u4["memory"]["status"] == "variant" and "message text changed" in u4["memory"]["note"]
    # a decision made under another version of the rule does not apply
    data["issues"][0]["occurrences"] = d["occurrences"]
    data["issues"][0]["rule_digest"] = "0" * 16
    _mem.save(owner, data)
    _, r = _review(run, runner, owner, "2.4", "2.4.1", tmp_path / "r241c.json")
    assert next(x for x in r["issues"] if x["rule"] == "U4")["memory"]["status"] == "stale"


def test_accept_narrows_to_the_issues_own_events_and_does_not_spread(run, runner, owner, tmp_path):
    r241, review = _review(run, runner, owner, "2.4", "2.4.1", tmp_path / "r241.json")
    rina = next(x for x in review["issues"] if x["id"] == RINA)
    assert rina["occurrences"][0]["exception"] == "P1-E1"
    before = {x["id"]: x["signature"] for x in review["issues"]}
    d = _mem.decide_issue(r241, RINA, "accept", by="test", expires="2026-12-31", on="2026-10-27")
    (ex,) = d["exceptions"]
    assert ex["id"] == "P1-E2" and ex["scope"] == {"features": ["fare_lock"], "surfaces": ex["scope"]["surfaces"],
                                                   "components": ["hotel"]}
    assert [c["id"] for c in ex["conditions"]] == ["a", "b", "c"]            # every condition kept
    c = _load_contract(owner)
    assert [x.id for x in c.rule("P1").exceptions] == ["P1-E1", "P1-E2"]
    assert _approval(owner, c)["items"]["exception:P1-E2"] == "approved"      # the decision is the approval
    assert _approval(owner, c)["items"]["rule:P1"] == _approval(owner, _C)["items"]["rule:P1"]
    assert _load_approvals(owner)["exception:P1-E2"]["by"] == "test"
    _, after = _review(run, runner, owner, "2.4", "2.4.1", tmp_path / "r241b.json")
    ids = {x["id"] for x in after["issues"]}
    assert RINA not in ids
    assert any(x["persona"] == "rina" and x["status"] == "excepted" for x in after["not_raised"])
    for iid, sig in before.items():                       # nothing else moved: the flight banner stays raised
        if iid != RINA:
            assert iid in ids and next(x for x in after["issues"] if x["id"] == iid)["signature"] == sig


def test_accept_is_refused_where_it_would_drop_a_condition_or_clear_a_universal_rule(run, runner, owner, tmp_path):
    r24, _ = _review(run, runner, owner, "2.3", "2.4", tmp_path / "r24.json")
    with pytest.raises(_mem.DecisionError, match="failed on a, not on scope alone"):
        _mem.decide_issue(r24, HANA, "accept", by="test", expires="2026-12-31")
    with pytest.raises(_mem.DecisionError, match="only for conditional rules"):
        _mem.decide_issue(r24, U4, "accept", by="test", expires="2026-12-31")
    with pytest.raises(_mem.DecisionError, match="needs a reason"):
        _mem.decide_issue(r24, U4, "not_an_issue", by="test")
    with pytest.raises(_mem.DecisionError, match="not an open issue"):
        _mem.decide_issue(r24, "I-nope", "fix", by="test")
    assert _mem.load(owner) == {"issues": [], "releases": []}             # nothing half-recorded


def test_a_decision_needs_a_review_that_matches_the_contract(run, runner, owner, tmp_path):
    r24, _ = _review(run, runner, owner, "2.3", "2.4", tmp_path / "r24.json")
    p = owner / "principles.yaml"
    p.write_text(p.read_text().replace("severity: critical", "severity: major", 1))
    with pytest.raises(_mem.DecisionError, match="contract changed since this review"):
        _mem.decide_issue(r24, KAI, "fix", by="test")


def test_a_rules_approval_does_not_cover_its_exceptions():
    p1 = _C.rule("P1")
    narrowed = p1.model_copy(update={"exceptions": p1.exceptions[:0]})
    assert _rule_digest(p1) == _rule_digest(narrowed)
    assert _rule_digest(p1) != _rule_digest(p1.model_copy(update={"text": p1.text + "!"}))


def test_altered_recorded_decisions_fail_the_manifest_check(run, runner, owner, tmp_path):
    r24, _ = _review(run, runner, owner, "2.3", "2.4", tmp_path / "r24.json")
    _mem.decide_issue(r24, KAI, "fix", by="test")
    _, r = _review(run, runner, owner, "2.4", "2.4.1", tmp_path / "r241.json")
    m = r["manifest"]
    assert _mf.memory_problems(m) == []
    m["memory"]["issues"][0]["kind"] = "not_an_issue"
    assert _mf.memory_problems(m) == ["the owner decisions recorded in this review were altered"]


def test_release_decision_sits_beside_the_recommendation(run, runner, owner, tmp_path):
    r24, review = _review(run, runner, owner, "2.3", "2.4", tmp_path / "r24.json")
    d = _mem.decide_release(r24, "hold", by="test", note="fix the P2 conflict first", on="2026-10-27")
    assert d["review_said"]["policy"] == review["policy"]["recommendation"]
    assert json.loads(r24.read_text())["policy"] == review["policy"]                 # the review is untouched
    assert _mem.decisions_for(r24, owner)["release"]["decision"] == "hold"


def test_page_shows_decisions_and_offers_buttons_only_when_served(browser, run, runner, owner, tmp_path):
    r24, _ = _review(run, runner, owner, "2.3", "2.4", runner.run_dir / "review-w11-2.3-2.4.json")
    _mem.decide_issue(r24, TRADEOFF, "fix", by="test", on="2026-10-27")
    _mem.decide_release(r24, "hold", by="test", on="2026-10-27")
    static = _build_page(r24, runner.run_dir / "report-w11")            # the screenshots are copied beside it
    pg, errors = _open(browser, static, f"#persona=maya&mode=head&issue={TRADEOFF}")
    assert not errors, errors
    assert "owner: fix" in pg.inner_text(".rail")
    assert "Owner decision Hold · test · 2026-10-27" in " ".join(pg.inner_text(".box.row").split())
    assert pg.locator("form").count() == 0                                  # static: no buttons
    pg.close()
    served = static.parent / "served.html"
    served.write_text(_render_page(r24, interactive=True, by="test"))
    pg, errors = _open(browser, served, f"#persona=kai&mode=head&issue={KAI}")
    assert not errors, errors
    assert pg.locator("form[action='/decide']").count() == 2                 # fix, not an issue
    assert pg.locator("button[disabled]", has_text="Accept scoped exception").count() == 1   # coherence rule
    pg.close()


def test_serve_records_a_decision_through_the_same_path(run, runner, owner, tmp_path):
    import threading
    import urllib.parse
    import urllib.request
    from http.server import HTTPServer

    from semaudit.report import serve as _serve
    r24, _ = _review(run, runner, owner, "2.3", "2.4", tmp_path / "r24.json")
    captured = {}
    real = HTTPServer.__init__

    def grab(self, addr, handler, *a, **k):
        real(self, ("127.0.0.1", 0), handler, *a, **k)
        captured["srv"] = self
    HTTPServer.__init__ = grab
    try:
        th = threading.Thread(target=_serve.serve, args=(r24,), kwargs={"by": "test"}, daemon=True)
        th.start()
        for _ in range(200):
            if "srv" in captured:
                break
            import time
            time.sleep(0.02)
        port = captured["srv"].server_address[1]
        body = urllib.parse.urlencode({"issue": KAI, "kind": "fix", "back": "#persona=kai"}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{port}/decide", data=body, method="POST")
        with urllib.request.urlopen(req) as resp:
            page = resp.read().decode()                                          # followed the redirect
            assert resp.status == 200 and f'"issue": "{KAI}"' in page and '"interactive": true' in page
        bad = urllib.parse.urlencode({"issue": U4, "kind": "not_an_issue"}).encode()
        try:
            urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/decide", data=bad, method="POST"))
            raise AssertionError("expected 400")
        except urllib.error.HTTPError as e:
            assert e.code == 400 and "needs a reason" in e.read().decode()
    finally:
        HTTPServer.__init__ = real
        if "srv" in captured:
            captured["srv"].shutdown()
    assert [d["issue"] for d in _mem.load(owner)["issues"]] == [KAI]
