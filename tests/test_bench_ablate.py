"""W13b (no model): the three ablations change exactly the part they name."""

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.bench import ablate, judge  # noqa: E402
from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.decide import run as run_mod  # noqa: E402

NB = ROOT / "examples/northbound/contract"
C = load_contract(NB)
SRC = ROOT / "runs/e2e-2"
pytestmark = pytest.mark.skipif(not (SRC / "episodes/2.4").exists(), reason="needs runs/e2e-2, the recorded Northbound demo run (10 MB of captures, kept out of git); these tests check facts of that one run")


def kai():
    return judge.stories_for(SRC, "2.4", C)["kai"]


def rel(label="conflict", cited=("pw.email.forecast", "fl.banner.urgent")):
    return {"personas": ["kai"], "rule": "P2", "label": label,
            "target": {"kind": "relation", "features": ["price_watch", "fare_lock"], "decision": "when_to_book"},
            "cited": [{"persona": "kai", "event_id": e, "quote": ""} for e in cited]}


def test_model_proposals_become_entries_tied_to_real_events():
    s = kai()
    ev = {"personas": ["kai"], "rule": "P1", "label": None, "cited": [],
          "target": {"kind": "event", "feature": "fare_lock", "surface": "fare_detail",
                     "message_key": "fl.banner.urgent"}}
    entries, dropped = ablate.entries_from([rel(), ev], s)
    assert not dropped
    p2, p1 = entries
    assert p2.subject == "fare_lock|price_watch@when_to_book:incompatible" and p2.label == "conflict"
    assert p2.meta["pairs"] == [["fl.banner.urgent", "pw.email.forecast"]]
    assert p1.subject == "fl.banner.urgent" and p1.status == "violated"


def test_a_proposal_not_tied_to_the_story_is_dropped_never_repaired():
    s = kai()
    ghost = {"personas": ["kai"], "rule": "P1", "label": None, "cited": [],
             "target": {"kind": "event", "feature": "fare_lock", "surface": "checkout", "message_key": "nope"}}
    entries, dropped = ablate.entries_from([ghost, rel(cited=("pw.email.forecast",)), rel(label=None)], s)
    assert entries == [] and len(dropped) == 3


def _run(tmp_path, monkeypatch, ablation, generator_entries=None):
    runs = tmp_path / "runs"
    (runs / "abl").mkdir(parents=True)
    shutil.copytree(SRC / "episodes", runs / "abl" / "episodes")
    shutil.copytree(SRC / "captures", runs / "abl" / "captures")
    if generator_entries is not None:
        def fake(contract, router, fresh=False):
            def gen(story):
                return [e for e in generator_entries(story)]
            gen.dropped = {}
            return gen
        monkeypatch.setattr(ablate, "model_generator", fake)
    # cache-only router: no model call can be made, so nothing is spent
    real = run_mod.Router
    monkeypatch.setattr(run_mod, "Router", lambda **kw: real(**{**kw, "offline": True}))
    out = run_mod.run_review(NB, "2.3", "2.4", run_id="abl", runs_dir=runs, max_usd=0.0, reuse=True,
                             models=False, ablation=ablation, root=ROOT)
    return json.loads(out.read_text()), out


def test_no_verifier_reports_candidates_unverified(tmp_path, monkeypatch):
    r, out = _run(tmp_path, monkeypatch, "no-verifier")
    assert out.name == "review-2.3-2.4.no-verifier.json" and r["manifest"]["ablation"] == "no-verifier"
    assert r["issues"] and all(i["verification"]["status"] == "unverified" for i in r["issues"])


def test_no_exceptions_raises_what_an_exception_used_to_permit(tmp_path, monkeypatch):
    r, _ = _run(tmp_path, monkeypatch, "no-exceptions")
    p1 = {p for i in r["issues"] if i["rule"] == "P1" for p in i["personas"]}
    assert {"raj", "kai"} <= p1                       # P1-E1 excepted them in the full auditor
    assert not any(x["status"] == "excepted" for x in r["not_raised"])


def test_no_generators_uses_only_what_the_model_proposed(tmp_path, monkeypatch):
    def only_kai(story):
        return ablate.entries_from([rel()], story)[0] if story.persona == "kai" else []
    r, _ = _run(tmp_path, monkeypatch, "no-generators", only_kai)
    assert [(i["rule"], i["personas"]) for i in r["issues"]] == [("P2", ["kai"])]
    assert r["manifest"]["ablation"] == "no-generators"


def test_unknown_ablation_is_refused(tmp_path, monkeypatch):
    with pytest.raises(ValueError):
        _run(tmp_path, monkeypatch, "no-everything")


def test_e3_stability_refuses_mixed_fresh_and_cached_runs():
    from semaudit.bench.e3 import stability
    from semaudit.bench.findings import Findings
    a = Findings(system="x", release="t", findings=[], fresh=True)
    b = Findings(system="x", release="t", findings=[], fresh=False)
    assert stability([a, a])["jaccard"] == 1.0
    s = stability([a, b])
    assert s["jaccard"] is None and "not every run was fresh" in s["note"]


def test_a_review_carries_its_freshness_into_findings():
    from semaudit.bench.findings import from_review
    r = json.loads((SRC / "review-2.3-2.4.json").read_text())
    assert from_review(r).fresh in (None, False)       # cached regeneration: never read as a fresh run
