"""Verdict stability: the model-judged verification steps (second-model check, defence) can run k times.

A step then passes only if every run passed (pass^k), fails only if every run failed, and is otherwise "mixed",
which neither verifies nor disputes the issue and caps its confidence at low. Each step records how many runs
passed (n of k). Run 0 is the ordinary call, so a review with --repeats 1 is the review as before and its cached
replies stay valid; run s > 0 sends seed s, so each repeat is its own request and cache entry."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.decide.issues import Issue, Occurrence  # noqa: E402
from semaudit.models.router import Router  # noqa: E402
from semaudit.relate.rules import Entry  # noqa: E402
from semaudit.verify import steps as S  # noqa: E402

C = load_contract(ROOT / "examples" / "northbound" / "contract")


def _issue(personas=("lena", "maya")):
    return Issue(id="I", signature=(), rule="U1", rule_kind="universal", layer="release", label=None,
                 occurrences=[Occurrence(p, "x", ["e1"], Entry("U1", "e1", "violated", meta={"fact": "tax_total"}),
                                         "after_decision") for p in personas], severity={}, why="")


def _step(result, **occ):
    return {"result": result, "detail": {p: f"{p} {v}" for p, v in occ.items()}, "occurrences": dict(occ)}


def test_a_step_passes_only_if_every_run_passed_and_fails_only_if_every_run_failed():
    assert S.combined_result(["pass", "pass", "pass"]) == "pass"
    assert S.combined_result(["fail", "fail"]) == "fail"
    assert S.combined_result(["pass", "fail", "pass"]) == "mixed"


def test_one_run_is_the_step_as_before_and_k_runs_record_n_of_k():
    one = _step("pass", lena="pass")
    assert S.combine_samples([one]) is one                    # --repeats 1: byte-identical record
    got = S.combine_samples([_step("pass", lena="pass", maya="pass"), _step("fail", lena="pass", maya="fail"),
                             _step("pass", lena="pass", maya="pass")])
    assert got["result"] == "mixed"
    assert got["occurrences"] == {"lena": "pass", "maya": "mixed"}
    assert got["samples"]["k"] == 3 and got["samples"]["passed"] == 2
    assert got["samples"]["results"] == ["pass", "fail", "pass"]
    assert got["samples"]["occurrences"] == {"lena": "3/3", "maya": "2/3"}
    assert got["detail"] == {"lena": "lena pass", "maya": "maya pass"} and len(got["samples"]["details"]) == 2


def test_each_runs_defence_is_judged_against_the_same_runs_cross_check(monkeypatch):
    seen = []

    class R:
        sample = 0
    router = R()

    def cross(issue, stories, contract, router, *, fresh, readings):
        readings["lena"] = {"e1": f"reading of run {router.sample}"}
        return _step("pass" if router.sample != 1 else "fail", lena="pass" if router.sample != 1 else "fail")

    def defend(issue, stories, contract, router, *, fresh, cross):
        seen.append((router.sample, cross["lena"]["e1"]))
        return _step("pass", lena="pass")
    monkeypatch.setattr(S, "step_cross_model", cross)
    monkeypatch.setattr(S, "step_defended", defend)
    cm, df = S.model_steps(_issue(("lena",)), {}, C, router, fresh=False, repeats=3)
    assert seen == [(0, "reading of run 0"), (1, "reading of run 1"), (2, "reading of run 2")]
    assert (cm["result"], cm["samples"]["passed"]) == ("mixed", 2) and df["result"] == "pass"
    assert router.sample == 0                                  # restored for whatever the router does next


def test_a_mixed_step_neither_verifies_nor_disputes_and_caps_confidence_at_low():
    mixed = S.combine_samples([_step("fail", lena="fail"), _step("pass", lena="pass"), _step("fail", lena="fail")])
    steps = {"reproduced": {"result": "pass"}, "evidence_linked": {"result": "pass"},
             "cross_model": {"result": "fail"}, "defended": mixed, "oracle_checked": {"result": "pass"}}
    v = S.verification_status(steps)
    assert (v["status"], v["reason"]) == ("partially_verified", "cross_model, defended")   # not "failed: disputed"
    conf = S.confidence_of(_issue(("lena",)), steps, C)
    assert conf["level"] == "low" and "defended: held in 1 of 3 samples" in conf["basis"]
    steps["cross_model"] = {"result": "pass"}                 # only the mixed defence can lower it now
    assert S.verification_status(steps)["status"] == "partially_verified"
    assert S.confidence_of(_issue(("lena",)), steps, C)["level"] == "low"
    steps["defended"] = S.combine_samples([_step("pass", lena="pass")] * 3)
    assert S.verification_status(steps)["status"] == "verified"
    assert "defended: held in 3 of 3 samples" in S.confidence_of(_issue(("lena",)), steps, C)["basis"]


def test_run_zero_is_the_ordinary_request_and_later_runs_are_separate_requests(tmp_path, monkeypatch):
    bodies = []

    def fetch(self, role, provider, model, body, digest, timeout_s):
        bodies.append((dict(body), digest))
        return {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}], "usage": {}}, 0.0
    monkeypatch.setattr(Router, "_fetch", fetch)
    r = Router(root=tmp_path)
    msgs = [{"role": "user", "content": "x"}]
    r.complete("defender", msgs)
    r.sample = 2
    r.complete("defender", msgs)
    r.sample = 0
    r.complete("defender", msgs)                               # run 0 again: the first request, now from cache
    assert "seed" not in bodies[0][0] and bodies[1][0]["seed"] == 2
    assert bodies[0][1] != bodies[1][1] and len(bodies) == 2
    r.sample = 2
    r.complete("defender", msgs, seed=7)                       # an explicit seed is the caller's, not replaced
    assert bodies[-1][0]["seed"] == 7


def test_verify_report_checks_each_step_result_against_its_recorded_runs(tmp_path, monkeypatch):
    """On the committed sample review: recorded runs that give the recorded result are consistent; a result the runs
    do not give (a forged pass over a failed run) is reported."""
    import shutil
    from semaudit.verify.report import verify_report
    dst = tmp_path / "sample"
    shutil.copytree(ROOT / "docs" / "try-it" / "northbound-2.3-2.4", dst)
    work = tmp_path / "clone"
    work.mkdir()
    (work / "examples").symlink_to(ROOT / "examples")
    monkeypatch.chdir(work)
    path = dst / "review-2.3-2.4.json"
    r = json.loads(path.read_text())
    issue = next(i for i in r["issues"] if i["verification"]["status"] == "verified")
    step = issue["verification"]["steps"]["defended"]
    one = {k: step[k] for k in ("result", "detail", "occurrences")}
    step.update(S.combine_samples([one, one, one]))             # three passing runs: still verified, consistent
    path.write_text(json.dumps(r))
    assert verify_report(path, root=tmp_path) == []
    step["samples"]["results"][1] = "fail"                     # a failed run under a recorded pass
    step["samples"]["passed"] = 2
    path.write_text(json.dumps(r))
    assert verify_report(path, root=tmp_path) == \
        [f"{issue['id']}: defended result does not follow from its 3 recorded samples"]


def test_compare_prompts_runs_each_issue_under_both_defender_prompts_and_restores_the_current_one(tmp_path,
                                                                                                    monkeypatch):
    import shutil
    import subprocess

    import pytest
    from semaudit.verify import compare as K
    if subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", "96eb296"], capture_output=True).returncode:
        pytest.skip("needs the repository history (commit 96eb296)")
    dst = tmp_path / "sample"
    shutil.copytree(ROOT / "docs" / "try-it" / "northbound-2.3-2.4", dst)
    (tmp_path / "root").mkdir()
    shutil.copytree(dst / "model-cache", tmp_path / "root" / ".semaudit-cache")   # the recorded readings
    work = tmp_path / "clone"
    work.mkdir()
    (work / "examples").symlink_to(ROOT / "examples")
    monkeypatch.chdir(work)

    def refuse(*a, **k):
        raise AssertionError("a model was called")
    monkeypatch.setattr(Router, "_fetch", refuse)
    current = S.DEFENSE_INSTRUCTIONS
    calls = []

    def steps(issue, stories, contract, router, *, fresh, repeats):
        old = S.DEFENSE_INSTRUCTIONS != current
        calls.append((issue.id, old, repeats))
        held = "fail" if old else "pass"                       # pretend the old prompt let defences stand
        df = S.combine_samples([_step(held, **{o.persona: held for o in issue.occurrences})] * repeats)
        return S.combine_samples([_step("pass", **{o.persona: "pass" for o in issue.occurrences})] * repeats), df
    monkeypatch.setattr(S, "model_steps", steps)
    out = K.compare_prompts(dst / "review-2.3-2.4.json", "96eb296", repeats=2, root=tmp_path / "root", max_usd=0.01)
    assert S.DEFENSE_INSTRUCTIONS == current                   # restored
    assert out["prompts"] == {"defense": "differs", "interpret": "same", "extraction": "same"}
    review = json.loads((dst / "review-2.3-2.4.json").read_text())
    dropped = [s for x in review["not_raised"] if x["status"] == "not_raised" for s in x["subjects"]]
    assert {i["id"] for i in out["issues"]} <= {i["id"] for i in review["issues"]} | set(dropped)
    assert len(out["issues"]) == len(review["issues"])          # every raised issue (this sample drops none)
    assert len(calls) == 2 * len(out["issues"]) and all(k == 2 for _, _, k in calls)
    first = out["issues"][0]
    assert first["old"]["defended"] == "0/2" and first["current"]["defended"] == "2/2"
    assert first["current"]["status"] == "verified" or first["current"]["status"].startswith("partially")
    assert out["spend"]["spent_usd"] == 0


def test_compare_prompts_restores_the_current_prompt_when_a_run_fails(tmp_path, monkeypatch):
    import shutil
    import subprocess

    import pytest
    from semaudit.verify import compare as K
    if subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", "96eb296"], capture_output=True).returncode:
        pytest.skip("needs the repository history (commit 96eb296)")
    dst = tmp_path / "sample"
    shutil.copytree(ROOT / "docs" / "try-it" / "northbound-2.3-2.4", dst)
    (tmp_path / "root").mkdir()
    shutil.copytree(dst / "model-cache", tmp_path / "root" / ".semaudit-cache")
    work = tmp_path / "clone"
    work.mkdir()
    (work / "examples").symlink_to(ROOT / "examples")
    monkeypatch.chdir(work)
    current = (S.DEFENSE_INSTRUCTIONS, S.DEFENSE_SCHEMA)

    def boom(*a, **k):
        raise RuntimeError("budget exhausted")                # e.g. the spend cap, during the old prompt's runs
    monkeypatch.setattr(S, "model_steps", boom)
    with pytest.raises(RuntimeError):
        K.compare_prompts(dst / "review-2.3-2.4.json", "96eb296", repeats=2, root=tmp_path / "root", max_usd=0.01)
    assert (S.DEFENSE_INSTRUCTIONS, S.DEFENSE_SCHEMA) == current
