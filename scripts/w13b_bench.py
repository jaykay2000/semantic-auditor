"""W13b sealed benchmark run. RUN BY THE BENCHMARK CUSTODIAN ONLY: the building session never runs this, and
never reads its inputs or per-finding outputs.

Runs the frozen conditions (bench/conditions/FROZEN-CONDITIONS.md) in priority order under ONE total cap. Each
step has its own cap, sized from measured costs; before a step starts, the script checks the total left covers
that step's cap, and SKIPS it (recorded, never silently) if not. A step that runs out of budget mid-way is
recorded as not measured. Lowest priority first to be dropped:

  1. auditor, fresh, every release                          (E2, E3 run 1)
  2. B-judge-1 on each auditor run's captures                (E2)
  3. B-judge-N on the same captures, frozen effort           (E2, budget-matched)
  4. no-verifier ablation, every release (reuses run 1)      (ablation)
  5. auditor, fresh, runs 2 and 3 on the first release       (E3 stability)
  6. no-exceptions ablation on the first release (reuse)     (ablation)

Then scores every condition against the sealed normalized truth (pre-adjudication: seeded subjective items are
hypotheses), the E3 report, and the blind adjudication sheet + key. Writes everything under --out.

  python3 scripts/w13b_bench.py --sealed <sealed dir> --releases bench-01,bench-02,bench-03 \
      --out bench/results/<date> --max-usd <total>
"""
import argparse
import json
import sys
import time
import tomllib
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from semaudit.bench import adjudicate, e3, judge  # noqa: E402
from semaudit.bench.findings import Findings, Truth, from_review  # noqa: E402
from semaudit.bench.match import evidence_index, score  # noqa: E402
from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.decide.run import run_review  # noqa: E402
from semaudit.models.router import ModelError, Router  # noqa: E402

CAPS = {"auditor": 1.85, "judge_one": 0.25, "judge_multi": 1.85, "no-verifier": 0.3, "no-exceptions": 1.0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sealed", type=Path, required=True)
    ap.add_argument("--releases", required=True)
    ap.add_argument("--base", default="2.3")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-usd", type=float, required=True)
    ap.add_argument("--contract-template", default="{sealed}/contracts/{rel}")
    ap.add_argument("--truth-template", default="{sealed}/ground_truth/normalized/{rel}.truth.json")
    ap.add_argument("--seed", type=int, default=20261101)
    a = ap.parse_args()
    cond = tomllib.loads((ROOT / "bench/conditions/conditions.toml").read_text())
    effort, samples = cond["B-judge-N"].get("effort", {}), cond["B-judge-N"].get("samples", 1)
    rels = a.releases.split(",")
    out, runs_dir = a.out, a.out / "runs"
    out.mkdir(parents=True, exist_ok=True)
    left = [a.max_usd]
    log: list[dict] = []

    def step(name: str, cap: float, fn):
        if left[0] < cap:
            log.append({"step": name, "status": "skipped", "why": f"${left[0]:.2f} left < cap ${cap}"})
            return None
        t0, spent_before = time.time(), _spent()
        try:
            res = fn(min(cap, left[0]))
            status = "done"
        except ModelError as e:
            res, status = None, f"not measured: {e}"
        except Exception as e:                                     # recorded, never hidden
            res, status = None, f"error: {type(e).__name__}: {e}"
            traceback.print_exc()
        spent = _spent() - spent_before
        left[0] -= spent
        log.append({"step": name, "status": status, "spent_usd": round(spent, 4), "seconds": round(time.time() - t0)})
        print(f"{name}: {status} (${spent:.3f}, ${left[0]:.2f} left)", flush=True)
        return res

    def contract_dir(rel):
        return Path(a.contract_template.format(sealed=a.sealed, rel=rel))

    reviews: dict[str, dict[str, Path]] = {r: {} for r in rels}
    findings: dict[str, list[Findings]] = {r: [] for r in rels}

    def auditor(rel, n):
        return lambda cap: run_review(contract_dir(rel), a.base, rel, run_id=f"{rel}-r{n}", runs_dir=runs_dir,
                                      max_usd=cap, fresh=True, root=ROOT)

    def judged(rel, fn, **kw):
        def go(cap):
            c = load_contract(contract_dir(rel))
            router = Router(ROOT, max_usd=cap)
            fs, _ = fn(judge.stories_for(runs_dir / f"{rel}-r1", rel, c), c, router, release=rel, fresh=True, **kw)
            return fs
        return go

    def ablation(rel, name):
        return lambda cap: run_review(contract_dir(rel), a.base, rel, run_id=f"{rel}-r1", runs_dir=runs_dir,
                                      max_usd=cap, reuse=True, fresh=False, root=ROOT, ablation=name)

    for rel in rels:                                                                  # 1
        if p := step(f"auditor {rel} r1", CAPS["auditor"], auditor(rel, 1)):
            reviews[rel]["r1"] = p
    for rel in rels:                                                                  # 2, 3
        if "r1" not in reviews[rel]:
            continue
        for name, fn, kw in (("judge_one", judge.judge_one, {}), ("judge_multi", judge.judge_multi, {"effort": effort, "samples": samples})):
            if fs := step(f"{name} {rel}", CAPS[name], judged(rel, fn, **kw)):
                findings[rel].append(fs)
    for rel in rels:                                                                  # 4
        if "r1" in reviews[rel] and (p := step(f"no-verifier {rel}", CAPS["no-verifier"], ablation(rel, "no-verifier"))):
            reviews[rel]["no-verifier"] = p
    first = rels[0]
    for n in (2, 3):                                                                  # 5
        if p := step(f"auditor {first} r{n}", CAPS["auditor"], auditor(first, n)):
            reviews[first][f"r{n}"] = p
    if "r1" in reviews[first] and (p := step(f"no-exceptions {first}", CAPS["no-exceptions"],     # 6
                                             ablation(first, "no-exceptions"))):
        reviews[first]["no-exceptions"] = p

    results: dict = {"pre_adjudication": True, "frozen": _frozen(), "steps": log, "releases": {}}
    sheet_systems, sheet_truth = [], []
    for rel in rels:
        tp = Path(a.truth_template.format(sealed=a.sealed, rel=rel))
        truth = Truth.model_validate(json.loads(tp.read_text()))
        rows = {}
        r1 = json.loads(reviews[rel]["r1"].read_text()) if "r1" in reviews[rel] else None
        ev = evidence_index(r1) if r1 else None
        for key, path in reviews[rel].items():
            rv = json.loads(path.read_text())
            fs = from_review(rv, run=key)
            rows[fs.system if key in ("no-verifier", "no-exceptions") else f"semaudit-full {key}"] = score(fs, truth, evidence=ev)
            if key == "r1":
                sheet_systems.append(fs)
        for fs in findings[rel]:
            rows[fs.system] = score(fs, truth, evidence=ev)
            sheet_systems.append(fs)
        runs_full = [reviews[rel][k] for k in ("r1", "r2", "r3") if k in reviews[rel]]
        results["releases"][rel] = {"scores": rows,
                                    "e3": e3.report(runs_full, truth, replay_usd=None) if len(runs_full) > 1 else None}
        sheet_truth.append((rel, truth, r1))
    # one adjudication sheet per release (the persona/event names are release-scoped)
    for rel, truth, r1 in sheet_truth:
        if r1 is None:
            continue
        c = load_contract(contract_dir(rel))
        systems = [s for s in sheet_systems if s.release == rel]
        sheet, key = adjudicate.build(systems, truth, {r.id: r.text for r in c.rules}, seed=a.seed,
                                      events=adjudicate.persona_events(r1),
                                      objective_rules={r.id for r in c.rules if r.check.get("must")})
        results["releases"][rel]["adjudication"] = adjudicate.write(sheet, key, out / "adjudication" / rel, seed=a.seed)
    results["spent_usd"] = round(a.max_usd - left[0], 4)
    (out / "results.json").write_text(json.dumps(results, indent=1, default=str))
    print(json.dumps(_aggregate(results), indent=1))


def _spent() -> float:
    p = ROOT / "runs/ledger.jsonl"
    return sum(json.loads(x)["cost_usd"] or 0 for x in p.read_text().splitlines()
               if not json.loads(x)["cached"]) if p.exists() else 0.0


def _frozen() -> str | None:
    f = ROOT / "bench/conditions/FROZEN-CONDITIONS.md"
    return f.read_text().splitlines()[0] if f.exists() else None


def _aggregate(results: dict) -> dict:
    """Counts only, safe to forward to the building session."""
    keep = ("tp", "fp", "fn", "intervals", "negative_controls", "label_accuracy", "evidence_support",
            "cost_usd", "cost_if_fresh_usd", "fresh", "truncated")
    agg = {"spent_usd": results["spent_usd"], "steps": results["steps"], "releases": {}}
    for rel, r in results["releases"].items():
        agg["releases"][rel] = {sysn: {k: (v if k != "evidence_support" else
                                          {"share": v["share"], "total": v["total"]} if v else None)
                                       for k, v in s.items() if k in keep}
                                for sysn, s in r["scores"].items()}
        if r.get("e3"):
            agg["releases"][rel]["e3_stability"] = r["e3"]["semaudit-full"]["stability"]
    return agg


if __name__ == "__main__":
    main()
