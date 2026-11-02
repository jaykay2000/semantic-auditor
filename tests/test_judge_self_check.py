"""Judge self-check (no model): scoring, the pass path, both ways it fails, not-run, and that it leaves the review's
own verdicts exactly as they were. Every model reply here is a stub; the stubs answer from the case file."""

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.decide import run as run_mod  # noqa: E402
from semaudit.models.router import ModelError, Result, Router, UnreadableReply  # noqa: E402
from semaudit.relate.rules import p2_candidates  # noqa: E402
from semaudit.report.review import outcome_of  # noqa: E402
from semaudit.story.episode import Episode  # noqa: E402
from semaudit.verify import selfcheck  # noqa: E402
from semaudit.verify.report import selfcheck_problem  # noqa: E402

NB = ROOT / "examples" / "northbound" / "contract"
SAMPLE = ROOT / "docs" / "try-it" / "northbound-2.3-2.4"
APPROVED = {"complete": True, "pending": []}
MEASURED = {"complete": True, "base": {}, "head": {}}


def planted() -> dict[str, str]:
    import yaml
    spec = yaml.safe_load(selfcheck.CASES.read_text())
    return {c["id"]: (c.get("planted") or {}).get("event") for c in spec["cases"]}


class StubJudge(Router):
    """The interpreter, answering from the case file: right on every case except those in `miss` (a planted mistake
    it passes) and `flag` (a correct case it flags). `fail_at`: raise this error on that call. Every call is logged
    with the release it was about, so a test can see which calls belonged to the self-check."""
    miss: set = set()
    flag: set = set()
    fail_at: tuple | None = None
    log: list = []

    def __init__(self, root=None, max_usd=None, **kw):
        super().__init__(root=root, max_usd=max_usd, **kw)
        self.roles["interpreter"] = {"provider": "meta", "model": "muse-spark-1.3"}

    def complete(self, role, messages, *, schema=None, fresh=False, **kw):
        payload = json.loads(messages[-1]["content"])
        who = [x["persona"] for x in payload.get("stories", [])] or [payload.get("persona")]
        StubJudge.log.append((role, payload.get("release"), fresh, who))
        if StubJudge.fail_at and len(StubJudge.log) == StubJudge.fail_at[0]:
            raise StubJudge.fail_at[1]
        parsed = self._reader(payload) if "stories" in payload else self._label(payload)
        return Result(role, "muse-spark-1.3", json.dumps(parsed), parsed, {"prompt_tokens": 1000,
                      "completion_tokens": 200}, 0.002, False, 0.0, {"choices": [{"finish_reason": "stop"}]})

    def _label(self, p):
        case = p["persona"]
        concierge = [e["id"] for e in p["story_in_time_order"] if e.get("feature") == "concierge"]
        actions = sorted({e["action"] for pair in p["candidate_pairs"] for e in pair})
        right = case.startswith("rules-right")
        if (right and case not in self.flag) or (not right and case in self.miss):
            return {"label": "explained_tradeoff", "reconciling_event_id": concierge[0] if concierge else "",
                    "addresses_actions": actions, "rationale": "stub"}
        return {"label": "conflict" if p["pair_type"] == "incompatible" else "unexplained_tradeoff",
                "reconciling_event_id": "", "addresses_actions": [], "rationale": "stub"}

    def _reader(self, p):
        if p["release"] != "self-check":                # the review's own reading: one finding per chunk
            s = p["stories"][0]
            ev = next(e for e in s["events"] if e["kind"] == "message" and any(ch.isdigit() for ch in e["text"]))
            return {"findings": [{"personas": [s["persona"]], "rule": "U1", "label": None,
                                  "target": {"kind": "event", "features": [], "decision": None,
                                             "feature": ev["feature"], "surface": ev["surface"],
                                             "message_key": ev["message_key"]},
                                  "severity": "critical", "confidence": "high", "why": "stub finding",
                                  "cited": [{"persona": s["persona"], "event_id": ev["id"], "quote": ev["text"]}]}]}
        where = planted()
        out = []
        for s in p["stories"]:
            case = s["persona"]
            wrong = case.startswith("reader-wrong")
            if (wrong and case not in self.miss) or (not wrong and case in self.flag):
                ev = next(e for e in s["events"] if e["id"] == where[case]) if wrong else \
                    next(e for e in s["events"] if e["kind"] == "message")
                out.append({"personas": [case], "rule": "U1", "label": None,
                            "target": {"kind": "event", "features": [], "decision": None, "feature": ev["feature"],
                                       "surface": ev["surface"], "message_key": ev["message_key"]},
                            "severity": "critical", "confidence": "high", "why": "units_left does not match",
                            "cited": [{"persona": case, "event_id": ev["id"], "quote": ev["text"]}]})
        return {"findings": out}


@pytest.fixture(autouse=True)
def stub(monkeypatch, tmp_path):
    StubJudge.miss, StubJudge.flag, StubJudge.fail_at, StubJudge.log = set(), set(), None, []
    monkeypatch.setattr(selfcheck, "Router", StubJudge)
    monkeypatch.chdir(tmp_path)                     # ledger rows go to tmp, never this checkout's runs/
    return StubJudge


# ---------------------------------------------------------------- the cases themselves

def test_cases_are_dev_and_judgeable():
    import yaml
    spec = yaml.safe_load(selfcheck.CASES.read_text())
    assert spec["label"] == "dev" and (selfcheck.CASES.parent / spec["contract"]).resolve() == NB.resolve()
    for mode in ("rules", "reader"):
        cases, contract, _ = selfcheck.load_cases(selfcheck.CASES, mode)
        assert len(cases) == 6 and sum(c["expect"] == "flag" for c in cases) == 3
        for c in cases:
            if mode == "rules":                     # exactly one pair for the judge to label
                assert len(p2_candidates(c["story"], contract)) == 1, c["id"]
            elif c["expect"] == "flag":             # the planted message is in the story
                assert any(e.id == c["planted"]["event"] for e in c["story"].events), c["id"]


def test_case_texts_are_the_apps_own_copy():
    """Every unplanted text is the Northbound app's template filled with the values release 2.4 fills in."""
    import yaml
    src = "".join(p.read_text() for p in (ROOT / "examples/northbound/northbound").rglob("*.py"))
    spec = yaml.safe_load(selfcheck.CASES.read_text())
    for key, text in spec["copy"].items():
        stem = text.split("2 seats")[0].split("€")[0].split("10:06")[0][:40]
        assert stem in src, key


# ---------------------------------------------------------------- scoring

def test_scoring_is_exact():
    cases = [{"id": "w", "expect": "flag"}, {"id": "r", "expect": "clear"}]
    ok = selfcheck.score(cases, {"w": {"flagged": True}, "r": {"flagged": False}})
    assert (ok["status"], ok["caught"], ok["cleared"], ok["answered_correctly"], ok["failing"]) == \
        ("passed", 1, 1, 2, [])
    missed = selfcheck.score(cases, {"w": {"flagged": False}, "r": {"flagged": False}})
    assert missed["status"] == "failed" and missed["failing"] == ["w"] and missed["caught"] == 0
    flagged = selfcheck.score(cases, {"w": {"flagged": True}, "r": {"flagged": True}})
    assert flagged["status"] == "failed" and flagged["failing"] == ["r"] and flagged["cleared"] == 0
    err = selfcheck.score(cases, {"w": {"flagged": True}, "r": {"error": "no key"}})
    assert err["status"] == "not_run"               # one unjudged case: never a pass, whatever the others say
    assert selfcheck.score(cases, {})["status"] == "not_run"


# ---------------------------------------------------------------- pass, and the two ways to fail

@pytest.mark.parametrize("mode", ["rules", "reader"])
def test_pass_path(mode, tmp_path):
    sc = selfcheck.run(mode, root=tmp_path, max_usd=0.25)
    assert sc["status"] == "passed", sc
    assert (sc["cases_run"], sc["caught"], sc["cleared"], sc["failing"]) == (6, 3, 3, [])
    assert sc["line"].startswith("Judge self-check: 6 of 6 planted cases answered correctly")
    assert sc["role"] == "interpreter" and sc["model"] == "muse-spark-1.3"
    assert all(release in (None, "self-check") and fresh for _, release, fresh, _ in StubJudge.log)
    assert len(StubJudge.log) == (6 if mode == "rules" else 1)
    assert outcome_of("hold", MEASURED, APPROVED, sc) == {"status": "decided", "recommendation": "hold", "reason": ""}


@pytest.mark.parametrize("mode,case", [("rules", "rules-wrong-1"), ("reader", "reader-wrong-2")])
@pytest.mark.parametrize("policy", ["hold", "ship"])
def test_a_planted_mistake_that_slips_through_blocks_hold_and_ship(mode, case, policy, tmp_path):
    StubJudge.miss = {case}
    sc = selfcheck.run(mode, root=tmp_path, max_usd=0.25)
    assert sc["status"] == "failed" and sc["failing"] == [case] and sc["caught"] == 2
    out = outcome_of(policy, MEASURED, APPROVED, sc)
    assert out["status"] == "not_measurable" and out["recommendation"] == "not_measurable"
    assert out["reason"] == f"judge self-check failed: {case}"
    assert "FAILED" in sc["line"] and case in sc["line"]


def test_code_still_catches_a_reconciler_that_is_not_there(tmp_path):
    """Rules mode: a judge that calls an unreconciled pair 'explained' with no reconciling message is overruled by
    code (rules.eval_p2), so the case still counts as caught: the self-check scores the whole path, not the label."""
    StubJudge.miss = {"rules-wrong-2", "rules-wrong-3"}
    assert selfcheck.run("rules", root=tmp_path, max_usd=0.25)["status"] == "passed"


@pytest.mark.parametrize("mode,case", [("rules", "rules-right-1"), ("reader", "reader-right-1")])
def test_a_correct_case_flagged_blocks_too(mode, case, tmp_path):
    StubJudge.flag = {case}
    sc = selfcheck.run(mode, root=tmp_path, max_usd=0.25)
    assert sc["status"] == "failed" and sc["failing"] == [case] and sc["cleared"] == 2
    out = outcome_of("ship", MEASURED, APPROVED, sc)
    assert out["status"] == "not_measurable" and case in out["reason"]


# ---------------------------------------------------------------- not run: never a pass

def test_no_key_is_not_run(monkeypatch, tmp_path):
    monkeypatch.setattr(selfcheck, "Router", Router)          # the real router, with no key anywhere
    monkeypatch.delenv("META_MODEL_API_KEY", raising=False)
    monkeypatch.setattr("httpx.post", lambda *a, **k: pytest.fail("the network was called"))
    sc = selfcheck.run("rules", root=tmp_path, max_usd=0.25)
    assert sc["status"] == "not_run" and sc["reason"].startswith("no key") and sc.get("answered_correctly") == 0
    assert sc["line"].startswith("Judge self-check: not run (no key")
    out = outcome_of("ship", MEASURED, APPROVED, sc)
    assert out["status"] == "not_measurable" and out["reason"].startswith("judge self-check not run")


def test_no_budget_left_is_not_run(tmp_path):
    sc = selfcheck.run("reader", root=tmp_path, max_usd=0.0)
    assert sc["status"] == "not_run" and sc["reason"].startswith("budget") and not StubJudge.log
    assert outcome_of("hold", MEASURED, APPROVED, sc)["status"] == "not_measurable"


@pytest.mark.parametrize("err", [ModelError("budget exhausted: spent $0.2500 of $0.25"),
                                 UnreadableReply("meta/muse-spark-1.3: reply is not JSON")])
def test_budget_running_out_or_an_unreadable_reply_midway_is_not_run(err, tmp_path):
    StubJudge.fail_at = (4, err)                    # three cases answered correctly, then the fourth call fails
    sc = selfcheck.run("rules", root=tmp_path, max_usd=0.25)
    assert sc["status"] == "not_run" and "passed" not in sc["line"] and sc["line"].startswith("Judge self-check: not run")
    assert outcome_of("ship", MEASURED, APPROVED, sc)["status"] == "not_measurable"


def test_a_missing_case_file_is_not_run(tmp_path):
    sc = selfcheck.run("rules", root=tmp_path, max_usd=0.25, path=tmp_path / "none.yaml")
    assert sc["status"] == "not_run" and "not found" in sc["reason"]


def test_turned_off_or_not_asked_changes_nothing():
    for sc in (None, selfcheck.off()):
        assert outcome_of("ship", MEASURED, APPROVED, sc) == {"status": "decided", "recommendation": "ship",
                                                              "reason": ""}
    assert selfcheck.line(selfcheck.off()) == "Judge self-check: off (turned off with --no-self-check)"
    assert selfcheck.line(None) == "Judge self-check: not run (none recorded in this review)"


def test_verify_report_rescores_the_recorded_answers(tmp_path):
    sc = selfcheck.run("rules", root=tmp_path, max_usd=0.25)
    assert selfcheck_problem(sc) is None
    forged = json.loads(json.dumps(sc))
    forged["cases"][0]["got"] = "flag" if forged["cases"][0]["got"] == "clear" else "clear"   # status still "passed"
    assert "status" in selfcheck_problem(forged)


# ---------------------------------------------------------------- the review's own verdicts do not move

def _reader_review(tmp_path, monkeypatch, self_check):
    runs = tmp_path / "runs"
    shutil.copytree(SAMPLE / "episodes", runs / "r" / "episodes", dirs_exist_ok=True)
    monkeypatch.setattr(run_mod, "Router", StubJudge)
    out = run_mod.run_review(NB, "2.3", "2.4", run_id="r", runs_dir=runs, max_usd=0.25, reuse=True, reader=True,
                             root=tmp_path, self_check=self_check)
    return json.loads(out.read_text())


class FakeRunner:
    """The re-capture of affected personas, served from the recorded head episodes (no browser)."""
    def __init__(self, contract_dir, runs_dir, run_id, **kw):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def capture(self, release, personas=None):
        eps = [Episode.read(p) for p in sorted((SAMPLE / "episodes" / release).glob("*.json"))]
        return [e for e in eps if personas is None or e.persona in personas]


def _rules_review(tmp_path, monkeypatch, self_check):
    """The committed sample's rules review, re-derived offline from its recorded model replies; the verifier is a
    stub (its replies are not recorded), the same for every run."""
    runs = tmp_path / "runs"
    shutil.copytree(SAMPLE / "episodes", runs / "r" / "episodes", dirs_exist_ok=True)

    def offline(**kw):
        r = Router(**{**kw, "offline": True})
        r.cache_dir = SAMPLE / "model-cache"
        return r

    def fake_verify(i, stories, episodes, run_dir, contract, router, **kw):
        i.verification = {"status": "verified", "reason": "", "steps": {}}
        i.confidence = {"level": "medium", "basis": ["stub verifier"]}
    monkeypatch.setattr(run_mod, "Router", offline)
    monkeypatch.setattr(run_mod, "Runner", FakeRunner)
    monkeypatch.setattr(run_mod, "verify", fake_verify)
    out = run_mod.run_review(NB, "2.3", "2.4", run_id="r", runs_dir=runs, max_usd=0.25, reuse=True,
                             root=ROOT, self_check=self_check)
    return json.loads(out.read_text())


def _verdicts(r: dict) -> dict:
    return {k: v for k, v in r.items() if k not in ("written_at", "self_check", "outcome")}


@pytest.mark.parametrize("review", [_reader_review, _rules_review])
def test_review_verdicts_are_identical_with_the_self_check_on_or_off(review, tmp_path, monkeypatch):
    if review is _rules_review:
        monkeypatch.setattr(Router, "_log", lambda *a, **k: None)   # the offline router's ledger is ROOT's: skip it
    unasked = review(tmp_path / "a", monkeypatch, None)
    off = review(tmp_path / "b", monkeypatch, False)
    StubJudge.log = []
    on = review(tmp_path / "c", monkeypatch, True)
    assert "self_check" not in unasked and off["self_check"]["status"] == "off"
    assert unasked["issues"] and unasked["policy"]["fired_by"]       # real verdicts to compare
    assert on["self_check"]["status"] == "passed" and on["self_check"]["cases_run"] == 6
    canon = lambda r: json.dumps(_verdicts(r), sort_keys=True).replace(str(tmp_path), "")   # noqa: E731
    for r in (off, on):
        assert canon(r).replace("/b/", "/x/").replace("/c/", "/x/") == canon(unasked).replace("/a/", "/x/")
        assert r["outcome"] == unasked["outcome"]                     # a pass changes nothing
    case = lambda w: any(str(p).startswith(("rules-", "reader-")) for p in w)   # noqa: E731
    mine = [x for x in StubJudge.log if case(x[3])]
    assert len(mine) == 6 if review is _rules_review else len(mine) == 1
    assert all(fresh and all(case([p]) for p in who) for _, _, fresh, who in mine)   # no review persona in a case call
    assert all(not case(who) for *_, who in StubJudge.log if (*_, who) not in mine)   # no case in a review call
    if review is _reader_review:
        assert {x[1] for x in StubJudge.log if not case(x[3])} == {"2.3", "2.4"}       # its own two releases

    StubJudge.miss = {"rules-wrong-1", "reader-wrong-1"}
    failed = review(tmp_path / "d", monkeypatch, True)
    assert canon(failed).replace("/d/", "/x/") == canon(unasked).replace("/a/", "/x/")   # verdicts unchanged
    assert failed["outcome"]["status"] == "not_measurable" and "judge self-check failed" in failed["outcome"]["reason"]


def test_review_cli_has_the_switch():
    from typer.testing import CliRunner

    from semaudit.cli import app
    out = CliRunner().invoke(app, ["review", "--help"], env={"COLUMNS": "200"}).output
    assert "--self-check" in out and "--no-self-check" in out
