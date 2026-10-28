"""W13b (no model): the sealed-run script runs steps in priority order, skips what the cap cannot cover (and says
so), scores every condition, and forwards only counts."""

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "runs/e2e-2"
pytestmark = pytest.mark.skipif(not (SRC / "episodes/2.4").exists(), reason="needs runs/e2e-2 (local)")


def load():
    spec = importlib.util.spec_from_file_location("w13b_bench", ROOT / "scripts/w13b_bench.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def sealed(tmp_path):
    d = tmp_path / "sealed"
    shutil.copytree(ROOT / "examples/northbound/contract", d / "contracts/2.4")
    (d / "ground_truth/normalized").mkdir(parents=True)
    shutil.copy(ROOT / "bench/dev/northbound-2.4.truth.json", d / "ground_truth/normalized/2.4.truth.json")
    return d


def run(m, monkeypatch, sealed, out, total, cost_per_call=0.3):
    spent = [0.0]

    def fake_review(contract_dir, base, head, *, run_id, runs_dir, ablation=None, **kw):
        spent[0] += cost_per_call
        dst = runs_dir / run_id
        if not dst.exists():
            shutil.copytree(SRC / "episodes", dst / "episodes")
        p = dst / (f"review-{base}-{head}.{ablation}.json" if ablation else f"review-{base}-{head}.json")
        r = json.loads((SRC / "review-2.3-2.4.json").read_text())
        r["manifest"]["ablation"] = ablation
        r["manifest"]["spend"] = {"fresh": True, "calls": 1, "cached": 0, "if_fresh_usd": cost_per_call}
        p.write_text(json.dumps(r))
        return p

    def fake_judge(name):
        def go(stories, c, router, *, release, fresh, run="1", **kw):
            spent[0] += cost_per_call
            from semaudit.bench.findings import Findings
            return Findings(system=name, release=release, findings=[], fresh=True), []
        return go

    monkeypatch.setattr(m, "run_review", fake_review)
    monkeypatch.setattr(m.judge, "judge_one", fake_judge("B-judge-1"))
    monkeypatch.setattr(m.judge, "judge_multi", fake_judge("B-judge-N"))
    monkeypatch.setattr(m, "_spent", lambda: spent[0])
    monkeypatch.setattr(sys, "argv", ["x", "--sealed", str(sealed), "--releases", "2.4", "--out", str(out),
                                      "--max-usd", str(total)])
    m.main()
    return json.loads((out / "results.json").read_text())


def test_everything_runs_and_every_condition_is_scored(tmp_path, monkeypatch, sealed):
    r = run(load(), monkeypatch, sealed, tmp_path / "out", 50.0)
    assert all(s["status"] == "done" for s in r["steps"])
    scores = r["releases"]["2.4"]["scores"]
    assert {"semaudit-full r1", "semaudit-full r2", "semaudit-full r3", "B-judge-1", "B-judge-N",
            "ablation-no-verifier", "ablation-no-exceptions"} <= set(scores)
    assert scores["semaudit-full r1"]["recall"] == 1.0
    assert r["releases"]["2.4"]["e3"]["semaudit-full"]["stability"]["jaccard"] == 1.0
    assert (tmp_path / "out/adjudication/2.4/sheet.csv").exists()


def test_a_step_whose_cap_the_budget_cannot_cover_is_skipped_and_says_why(tmp_path, monkeypatch, sealed):
    """$2.00: run 1 (cap 1.85) fits; after it, the multi-pass judge's 1.60 cap does not, nor runs 2-3. Cheaper
    later steps still use what is left. Nothing starts that could be cut off by the cap."""
    r = run(load(), monkeypatch, sealed, tmp_path / "out", 2.0)
    status = {s["step"]: s["status"] for s in r["steps"]}
    assert status["auditor 2.4 r1"] == "done" and status["judge_one 2.4"] == "done"
    assert status["judge_multi 2.4"] == status["auditor 2.4 r2"] == status["auditor 2.4 r3"] == "skipped"
    assert all("left < cap" in s["why"] for s in r["steps"] if s["status"] == "skipped")
    assert "B-judge-N" not in r["releases"]["2.4"]["scores"]


def test_only_counts_are_forwarded(tmp_path, monkeypatch, sealed, capsys):
    run(load(), monkeypatch, sealed, tmp_path / "out", 50.0)
    printed = capsys.readouterr().out
    agg = json.loads(printed[printed.index("{\n"):])
    text = json.dumps(agg)
    for leaked in ("matched", "unmatched", "negative_control_hits", "persona", "fl.banner"):
        assert leaked not in text, leaked
