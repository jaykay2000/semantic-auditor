"""Input ablation of B-judge-1 (no model): each variant removes exactly what INPUT-ABLATION.md says, the prompt
keeps the frozen output format verbatim, and the custodian script forwards counts only."""

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from semaudit.bench import inputs, judge  # noqa: E402
from semaudit.bench.findings import Findings  # noqa: E402
from semaudit.contract.schema import load_contract  # noqa: E402

SRC = ROOT / "runs/e2e-2"
C = load_contract(ROOT / "examples/northbound/contract")
needs_run = pytest.mark.skipif(not (SRC / "episodes/2.4").exists(), reason="needs runs/e2e-2, the recorded Northbound demo run (10 MB of captures, kept out of git); these tests check facts of that one run")


def stories():
    return judge.stories_for(SRC, "2.4", C)


@needs_run
def test_each_variant_removes_exactly_its_input():
    s = stories()
    full = inputs.payload("no-method", s, C, "2.4")
    assert full["contract"] == judge.render_contract(C)                     # V1: contract and readings intact
    assert all("oracle_readings" in x and "truth" in x for x in full["stories"])
    no_oracle = inputs.payload("no-oracle", s, C, "2.4")
    assert no_oracle["contract"] == judge.render_contract(C)
    assert all("oracle_readings" not in x and "truth" not in x for x in no_oracle["stories"])
    assert [x["events"] for x in no_oracle["stories"]] == [x["events"] for x in full["stories"]]   # tags kept
    plain = inputs.payload("plain-rules", s, C, "2.4")
    assert plain["stories"] == no_oracle["stories"]
    for r in plain["contract"]["rules"]:
        assert not {"check", "count", "applies_to"} & set(r), r["id"]
    assert not {"facts", "state", "rubric"} & set(plain["contract"])


def test_exception_sentence_is_generated_from_the_contract_only():
    p1 = next(r for r in C.rules if r.id == "P1")
    s = inputs.plain_exception(p1.exceptions[0])
    assert s.startswith("Exception P1-E1: allowed only when ALL of these hold")
    assert "72 hours" in s and "units left claim is true" in s and "explains own tradeoff" in s
    assert "2027-01-31" in s and "surfaces: fare_detail, checkout" in s


def test_bare_prompt_keeps_the_frozen_format_and_drops_the_method():
    bare = (judge.CONDITIONS / "prompts/inputs/judge_bare.md").read_text()
    common = (judge.CONDITIONS / "prompts/_common.md").read_text()
    assert common[common.index("What to report"):].strip() in bare
    assert "How to judge" not in bare and "oracle" not in bare.lower()


def test_unknown_variant_refused():
    with pytest.raises(ValueError):
        inputs.payload("no-everything", {}, C, "2.4")


@needs_run
def test_custodian_script_scores_every_variant_and_prints_no_pattern_names(tmp_path, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("w13b_inputs", ROOT / "scripts/w13b_inputs.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sealed, results = tmp_path / "sealed", tmp_path / "results"
    shutil.copytree(ROOT / "examples/northbound/contract", sealed / "contracts/2.4")
    (sealed / "ground_truth/normalized").mkdir(parents=True)
    shutil.copy(ROOT / "bench/dev/northbound-2.4.truth.json", sealed / "ground_truth/normalized/2.4.truth.json")
    shutil.copytree(SRC / "episodes", results / "runs/2.4-r1/episodes")
    shutil.copy(SRC / "review-2.3-2.4.json", results / "runs/2.4-r1/review-2.3-2.4.json")
    calls = []

    def fake(variant, stories, c, router, *, release, **kw):
        calls.append(variant)
        return Findings(system=f"B-judge-1/{variant}", release=release, findings=[], fresh=True, cost_usd=0.05), []

    monkeypatch.setattr(m.inputs, "judge_variant", fake)
    monkeypatch.setattr(sys, "argv", ["x", "--sealed", str(sealed), "--results", str(results), "--releases", "2.4",
                                      "--max-usd", "1.0"])
    m.main()
    assert calls == list(inputs.VARIANTS)
    out = json.loads((results / "input-ablation.json").read_text())
    assert set(out["releases"]["2.4"]) == {f"B-judge-1/{v}" for v in inputs.VARIANTS}
    printed = capsys.readouterr().out
    agg = json.loads(printed[printed.index("{"):])
    row = agg["releases"]["2.4"]["B-judge-1/no-method"]
    assert row["fn"] > 0 and isinstance(row["negative_control_hits"], list)
    assert "negative_controls" not in json.dumps(agg)                       # totals only, never pattern names


@needs_run
def test_cap_skips_and_records(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("w13b_inputs", ROOT / "scripts/w13b_inputs.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sealed, results = tmp_path / "sealed", tmp_path / "results"
    shutil.copytree(ROOT / "examples/northbound/contract", sealed / "contracts/2.4")
    (sealed / "ground_truth/normalized").mkdir(parents=True)
    shutil.copy(ROOT / "bench/dev/northbound-2.4.truth.json", sealed / "ground_truth/normalized/2.4.truth.json")
    shutil.copytree(SRC / "episodes", results / "runs/2.4-r1/episodes")
    shutil.copy(SRC / "review-2.3-2.4.json", results / "runs/2.4-r1/review-2.3-2.4.json")
    monkeypatch.setattr(m.inputs, "judge_variant", lambda v, s, c, r, *, release, **kw: (
        Findings(system=f"B-judge-1/{v}", release=release, findings=[], fresh=True, cost_usd=0.15), []))
    monkeypatch.setattr(sys, "argv", ["x", "--sealed", str(sealed), "--results", str(results), "--releases", "2.4",
                                      "--max-usd", "0.40"])
    m.main()
    steps = json.loads((results / "input-ablation.json").read_text())["steps"]
    assert [s["status"] for s in steps][:2] == ["done", "done"] and steps[2]["status"] == "skipped"
