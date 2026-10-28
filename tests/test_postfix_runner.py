"""W13c (no model): the post-fix runner runs every system fresh in priority order, repeats the auditor AND
B-judge-1 comparably, evaluates exactly the thresholds POST-FIX-EVAL.md predeclares, and forwards counts only."""

import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "runs/e2e-2"
needs_run = pytest.mark.skipif(not (SRC / "episodes/2.4").exists(), reason="needs runs/e2e-2 (local)")


def load():
    spec = importlib.util.spec_from_file_location("w13c", ROOT / "scripts/w13c_postfix.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_the_plan_and_the_script_declare_the_same_thresholds():
    plan = (ROOT / "bench/conditions/POST-FIX-EVAL.md").read_text()
    declared = {k: float(v) for k, v in re.findall(r"`(\w+) = ([\d.]+)`", plan)}
    assert declared == {k: float(v) for k, v in load().THRESHOLDS.items()}


@pytest.fixture
def sealed(tmp_path):
    d = tmp_path / "sealed"
    shutil.copytree(ROOT / "examples/northbound/contract", d / "contracts/2.4")
    (d / "ground_truth/normalized").mkdir(parents=True)
    shutil.copy(ROOT / "bench/dev/northbound-2.4.truth.json", d / "ground_truth/normalized/2.4.truth.json")
    return d


def run(m, monkeypatch, sealed, out, total, cost=0.3):
    spent, calls = [0.0], []

    def fake_review(contract_dir, base, head, *, run_id, runs_dir, fresh, **kw):
        assert fresh is True                                   # every measured system runs fresh
        spent[0] += cost
        calls.append(f"auditor {run_id}")
        dst = runs_dir / run_id
        shutil.copytree(SRC / "episodes", dst / "episodes")
        p = dst / f"review-{base}-{head}.json"
        r = json.loads((SRC / "review-2.3-2.4.json").read_text())
        r["manifest"]["spend"] = {"fresh": True, "calls": 1, "cached": 0, "if_fresh_usd": cost}
        p.write_text(json.dumps(r))
        return p

    def fake_judge(name):
        def go(stories, c, router, *, release, fresh, run="1", **kw):
            assert fresh is True
            spent[0] += cost / 3
            calls.append(f"{name} r{run}")
            from semaudit.bench.findings import Findings
            return Findings(system=name, release=release, run=run, findings=[], fresh=True), []
        return go

    monkeypatch.setattr(m, "run_review", fake_review)
    monkeypatch.setattr(m.judge, "judge_one", fake_judge("B-judge-1"))
    monkeypatch.setattr(m.judge, "judge_multi", fake_judge("B-judge-N"))
    monkeypatch.setattr(m, "_spent", lambda: spent[0])
    monkeypatch.setattr(m.freeze, "changed", lambda manifest: [])   # the dev tree is past the W13c freeze
    monkeypatch.setattr(sys, "argv", ["x", "--sealed", str(sealed), "--releases", "2.4", "--out", str(out),
                                      "--max-usd", str(total)])
    m.main()
    return json.loads((out / "results.json").read_text()), calls


@needs_run
def test_priority_order_and_comparable_repeats(tmp_path, monkeypatch, sealed, capsys):
    r, calls = run(load(), monkeypatch, sealed, tmp_path / "out", 50.0)
    assert calls == ["auditor 2.4-r1", "B-judge-1 r1", "auditor 2.4-r2", "auditor 2.4-r3", "B-judge-1 r2",
                     "B-judge-1 r3", "B-judge-N r1"]
    rel = r["releases"]["2.4"]
    assert {"semaudit-full r1", "semaudit-full r2", "semaudit-full r3", "B-judge-1 r1", "B-judge-1 r2",
            "B-judge-1 r3", "B-judge-N r1"} == set(rel["scores"])
    assert rel["e3"]["semaudit-full"]["stability"]["jaccard"] == 1.0 and rel["b_judge_1_jaccard"] == 1.0
    t = r["thresholds"]
    assert t["recall"] == {"verdict": "met", "auditor": 1.0, "b_judge_1": 0.0}   # real dev review vs a fake judge
    assert t["stability"]["verdict"] == "met" and t["false_alarms"]["verdict"] == "met"
    printed = capsys.readouterr().out
    agg = json.loads(printed[printed.index('{\n "spent_usd"'):])
    assert "negative_controls" not in json.dumps(agg) and "matched" not in json.dumps(agg)


@needs_run
def test_budget_drops_the_lowest_priority_first(tmp_path, monkeypatch, sealed):
    """$2.20: run 1 (cap 1.85) fits; then B-judge-1 (cap 0.25) fits; repeats and B-judge-N do not, and say so."""
    r, calls = run(load(), monkeypatch, sealed, tmp_path / "out", 2.2)
    assert calls == ["auditor 2.4-r1", "B-judge-1 r1"]
    status = {s["step"]: s["status"] for s in r["steps"]}
    assert status["auditor 2.4 r2"] == "skipped" and status["judge_multi 2.4 r1"] == "skipped"
    assert r["thresholds"]["stability"]["verdict"] == "not measured"


def test_an_issue_free_release_with_any_false_alarm_fails_the_claim():
    m = load()
    res = {"releases": {
        "a": {"issue_free": False, "scores": {"semaudit-full r1": {"tp": 5, "fp": 0, "fn": 0, "cost_usd": 0.5},
                                              "B-judge-1 r1": {"tp": 5, "fp": 0, "fn": 0, "cost_usd": 0.1}}},
        "b": {"issue_free": True, "scores": {"semaudit-full r1": {"tp": 0, "fp": 1, "fn": 0, "cost_usd": 0.5},
                                             "B-judge-1 r1": {"tp": 0, "fp": 0, "fn": 0, "cost_usd": 0.1}}}}}
    t = m.evaluate_thresholds(res, "a")
    assert t["false_alarms"]["verdict"] == "not met" and t["false_alarms"]["issue_free_fp"] == [1]
    assert t["recall"]["verdict"] == "met" and t["cost"]["verdict"] == "met"


def test_the_runner_refuses_before_spending_when_the_code_is_not_the_frozen_code(tmp_path, monkeypatch):
    m = load()
    calls = []
    monkeypatch.setattr(m, "run_review", lambda *a, **k: calls.append("auditor"))
    monkeypatch.setattr(m.freeze, "changed", lambda manifest: ["CHANGED: src/semaudit/relate/claims.py"])
    monkeypatch.setattr(sys, "argv", ["x", "--sealed", str(tmp_path), "--releases", "2.4", "--out",
                                      str(tmp_path / "out"), "--max-usd", "5"])
    with pytest.raises(SystemExit, match="claims.py"):
        m.main()
    assert calls == [] and not (tmp_path / "out").exists()


@needs_run
def test_results_record_the_freeze_they_ran_under(tmp_path, monkeypatch, sealed):
    r, _ = run(load(), monkeypatch, sealed, tmp_path / "out", 2.2)
    assert r["frozen"]["file"] == "FROZEN-POSTFIX.md"
    assert re.fullmatch(r"[0-9a-f]{64}", r["frozen"]["manifest"]) and re.fullmatch(r"[0-9a-f]{40}", r["frozen"]["code"])


def test_the_freeze_check_sees_an_edit_and_an_uncommitted_file(tmp_path, monkeypatch):
    import subprocess
    spec = importlib.util.spec_from_file_location("fz", ROOT / "scripts/freeze_conditions.py")
    fz = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fz)
    (tmp_path / "src/semaudit").mkdir(parents=True)
    f = tmp_path / "src/semaudit/a.py"
    f.write_text("x = 1\n")
    git = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)  # noqa: E731
    git("init", "-q"); git("add", "."); git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x")
    monkeypatch.setattr(fz, "ROOT", tmp_path)
    man = tmp_path / "FROZEN-T.md"
    monkeypatch.setattr(sys, "argv", ["x", "--out", str(man)])
    fz.main()
    assert fz.changed(man) == []
    f.write_text("x = 2\n")
    assert fz.changed(man) == ["CHANGED: src/semaudit/a.py", "UNCOMMITTED: src/semaudit/a.py"]
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "y")
    assert fz.changed(man) == ["CHANGED: src/semaudit/a.py"]       # committed, but not the frozen bytes
