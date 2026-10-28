"""W13c post-fix evaluation on FRESH sealed releases (bench/conditions/POST-FIX-EVAL.md).
RUN BY THE BENCHMARK CUSTODIAN ONLY. The building session never runs this, and never reads its inputs or
per-finding outputs. W13b's result is never rewritten; this writes a separate result.

Every measured system runs fresh (no cache). Steps in priority order under ONE total cap. Before a step starts,
the script checks that what is left covers that step's cap, and SKIPS it (recorded) if not:

  1. auditor, fresh, run 1 on every release
  2. B-judge-1, fresh, on each release's run-1 captures
  3. auditor, fresh, runs 2 and 3 on the stability release (--stability, default: the first release)
  4. B-judge-1, fresh, on the stability release's run-2 and run-3 captures (comparable repeats)
  5. B-judge-N, fresh, on each release's run-1 captures (lowest priority: only if the budget allows)

Then it scores everything with the frozen matcher, evaluates the predeclared thresholds, writes results.json and
the blind adjudication sheets, and prints COUNTS ONLY (negative controls totalled, no pattern names).

  python3 scripts/w13c_postfix.py --sealed <sealed dir> --releases bench-04,bench-05,bench-06 \
      --out <results dir> --max-usd 4.30
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
from semaudit.bench.findings import Truth, from_review  # noqa: E402
from semaudit.bench.match import evidence_index, jaccard, score  # noqa: E402
from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.decide.run import run_review  # noqa: E402
from semaudit.models.router import ModelError, Router  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
import freeze_conditions as freeze  # noqa: E402

CAPS = {"auditor": 1.85, "judge_one": 0.25, "judge_multi": 1.85}
THRESHOLDS = {                       # copied from POST-FIX-EVAL.md; a test pins the two against each other
    "fp_total_max": 2,               # auditor false alarms across all releases
    "fp_issue_free_max": 0,          # auditor false alarms on each issue-free release
    "nc_margin": 1,                  # auditor negative-control hits <= B-judge-1's + this
    "recall_min": 0.80,              # auditor recall over all releases
    "recall_margin": 0.10,           # auditor recall >= B-judge-1's - this (non-inferiority)
    "stability_min": 0.90,           # auditor Jaccard over 3 fresh runs
    "cost_per_release_max": 1.00,    # auditor fresh dollars per release
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sealed", type=Path, required=True)
    ap.add_argument("--releases", required=True)
    ap.add_argument("--stability", default=None, help="release for the 3-run stability check (default: first)")
    ap.add_argument("--base", default="2.3")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-usd", type=float, required=True)
    ap.add_argument("--seed", type=int, default=20261104)
    ap.add_argument("--frozen", type=Path, default=ROOT / "bench/conditions/FROZEN-POSTFIX.md",
                    help="freeze manifest the code must match before anything runs")
    a = ap.parse_args()
    bad = freeze.changed(a.frozen)
    if bad:                                    # nothing is spent on a run whose conditions are not the frozen ones
        sys.exit("refusing to run: the code does not match " + a.frozen.name + "\n" + "\n".join(bad))
    frozen = {"manifest": freeze.manifest_of(a.frozen), "file": a.frozen.name, "code": freeze.code()}
    cond = tomllib.loads((ROOT / "bench/conditions/conditions.toml").read_text())
    effort, samples = cond["B-judge-N"].get("effort", {}), cond["B-judge-N"].get("samples", 1)
    rels = a.releases.split(",")
    stab = a.stability or rels[0]
    out, runs_dir = a.out, a.out / "runs"
    out.mkdir(parents=True, exist_ok=True)
    left, log = [a.max_usd], []

    def step(name, cap, fn):
        if left[0] < cap:
            log.append({"step": name, "status": "skipped", "why": f"${left[0]:.2f} left < cap ${cap}"})
            return None
        t0, before = time.time(), _spent()
        try:
            res, status = fn(min(cap, left[0])), "done"
        except ModelError as e:
            res, status = None, f"not measured: {e}"
        except Exception as e:                                 # recorded, never hidden
            res, status = None, f"error: {type(e).__name__}: {e}"
            traceback.print_exc()
        spent = _spent() - before
        left[0] -= spent
        log.append({"step": name, "status": status, "spent_usd": round(spent, 4), "seconds": round(time.time() - t0)})
        print(f"{name}: {status} (${spent:.3f}, ${left[0]:.2f} left)", flush=True)
        return res

    cdir = lambda rel: a.sealed / "contracts" / rel  # noqa: E731
    reviews = {r: {} for r in rels}
    judged = {r: {} for r in rels}

    def auditor(rel, n):
        return lambda cap: run_review(cdir(rel), a.base, rel, run_id=f"{rel}-r{n}", runs_dir=runs_dir,
                                      max_usd=cap, fresh=True, root=ROOT)

    def judge_on(rel, n, fn, **kw):
        def go(cap):
            c = load_contract(cdir(rel))
            fs, _ = fn(judge.stories_for(runs_dir / f"{rel}-r{n}", rel, c), c, Router(ROOT, max_usd=cap),
                       release=rel, fresh=True, run=str(n), **kw)
            return fs
        return go

    for rel in rels:                                                                  # 1
        if p := step(f"auditor {rel} r1", CAPS["auditor"], auditor(rel, 1)):
            reviews[rel]["r1"] = p
    for rel in rels:                                                                  # 2
        if "r1" in reviews[rel] and (fs := step(f"judge_one {rel} r1", CAPS["judge_one"],
                                                judge_on(rel, 1, judge.judge_one))):
            judged[rel]["B-judge-1 r1"] = fs
    for n in (2, 3):                                                                  # 3
        if p := step(f"auditor {stab} r{n}", CAPS["auditor"], auditor(stab, n)):
            reviews[stab][f"r{n}"] = p
    for n in (2, 3):                                                                  # 4
        if f"r{n}" in reviews[stab] and (fs := step(f"judge_one {stab} r{n}", CAPS["judge_one"],
                                                    judge_on(stab, n, judge.judge_one))):
            judged[stab][f"B-judge-1 r{n}"] = fs
    for rel in rels:                                                                  # 5
        if "r1" in reviews[rel] and (fs := step(f"judge_multi {rel} r1", CAPS["judge_multi"],
                                                judge_on(rel, 1, judge.judge_multi, effort=effort,
                                                         samples=samples))):
            judged[rel]["B-judge-N r1"] = fs

    results = {"pre_adjudication": True, "plan": "bench/conditions/POST-FIX-EVAL.md", "frozen": _frozen(),
               "steps": log, "releases": {}}
    for rel in rels:
        truth = Truth.model_validate(json.loads((a.sealed / "ground_truth/normalized" / f"{rel}.truth.json").read_text()))
        r1 = json.loads(reviews[rel]["r1"].read_text()) if "r1" in reviews[rel] else None
        ev = evidence_index(r1) if r1 else None
        rows, systems = {}, []
        for key, path in reviews[rel].items():
            fs = from_review(json.loads(path.read_text()), run=key)
            rows[f"semaudit-full {key}"] = score(fs, truth, evidence=ev)
            if key == "r1":
                systems.append(fs)
        for key, fs in judged[rel].items():
            rows[key] = score(fs, truth, evidence=ev)
            if key.endswith("r1"):
                systems.append(fs)
        entry = {"issue_free": not any(i.kind == "issue" for i in truth.items), "scores": rows}
        runs = [reviews[rel][k] for k in ("r1", "r2", "r3") if k in reviews[rel]]
        if len(runs) > 1:
            entry["e3"] = e3.report(runs, truth, replay_usd=None)
            bj = [judged[rel][f"B-judge-1 r{n}"] for n in (1, 2, 3) if f"B-judge-1 r{n}" in judged[rel]]
            entry["b_judge_1_jaccard"] = jaccard(bj) if len(bj) > 1 else None
        if r1:
            c = load_contract(cdir(rel))
            sheet, key = adjudicate.build(systems, truth, {r.id: r.text for r in c.rules}, seed=a.seed,
                                          events=adjudicate.persona_events(r1),
                                          objective_rules={r.id for r in c.rules if r.check.get("must")})
            entry["adjudication"] = adjudicate.write(sheet, key, out / "adjudication" / rel, seed=a.seed)
        results["releases"][rel] = entry
    results["thresholds"] = evaluate_thresholds(results, stab)
    results["spent_usd"] = round(a.max_usd - left[0], 4)
    results["frozen"] = frozen
    (out / "results.json").write_text(json.dumps(results, indent=1, default=str))
    print(json.dumps(aggregate(results), indent=1))


def evaluate_thresholds(results: dict, stab: str) -> dict:
    """Each predeclared claim: met / not met / not measured, with the numbers it was judged on."""
    def tot(system, k):
        vals = [r["scores"][system][k] for r in results["releases"].values() if system in r["scores"]]
        return sum(vals) if len(vals) == len(results["releases"]) else None
    a_tp, a_fp, a_fn = (tot("semaudit-full r1", k) for k in ("tp", "fp", "fn"))
    b_tp, b_fn = tot("B-judge-1 r1", "tp"), tot("B-judge-1 r1", "fn")
    nc = lambda s: sum(sum(v["false_positives"] for v in (r["scores"][s].get("negative_controls") or {}).values())  # noqa: E731
                       for r in results["releases"].values() if s in r["scores"])
    out = {}
    if a_fp is None:
        out["false_alarms"] = {"verdict": "not measured"}
    else:
        free = [r["scores"]["semaudit-full r1"]["fp"] for r in results["releases"].values() if r["issue_free"]]
        ok = a_fp <= THRESHOLDS["fp_total_max"] and all(x <= THRESHOLDS["fp_issue_free_max"] for x in free) \
            and (b_tp is None or nc("semaudit-full r1") <= nc("B-judge-1 r1") + THRESHOLDS["nc_margin"])
        out["false_alarms"] = {"verdict": "met" if ok else "not met", "auditor_fp": a_fp, "issue_free_fp": free,
                               "auditor_nc": nc("semaudit-full r1"),
                               "b_judge_1_nc": nc("B-judge-1 r1") if b_tp is not None else None}
    if a_tp is None or b_tp is None or not (a_tp + a_fn) or not (b_tp + b_fn):
        out["recall"] = {"verdict": "not measured"}
    else:
        ra, rb = a_tp / (a_tp + a_fn), b_tp / (b_tp + b_fn)
        ok = ra >= THRESHOLDS["recall_min"] and ra >= rb - THRESHOLDS["recall_margin"]
        out["recall"] = {"verdict": "met" if ok else "not met", "auditor": round(ra, 4), "b_judge_1": round(rb, 4)}
    st = results["releases"].get(stab, {})
    aj = (st.get("e3") or {}).get("semaudit-full", {}).get("stability", {}).get("jaccard")
    bj = st.get("b_judge_1_jaccard")
    if aj is None or bj is None:
        out["stability"] = {"verdict": "not measured", "auditor": aj, "b_judge_1": bj}
    else:
        out["stability"] = {"verdict": "met" if aj >= THRESHOLDS["stability_min"] and aj >= bj else "not met",
                            "auditor": aj, "b_judge_1": bj}
    costs = [r["scores"]["semaudit-full r1"]["cost_usd"] for r in results["releases"].values()
             if "semaudit-full r1" in r["scores"]]
    out["cost"] = ({"verdict": "met" if max(costs) <= THRESHOLDS["cost_per_release_max"] else "not met",
                    "auditor_per_release": costs} if len(costs) == len(results["releases"]) else
                   {"verdict": "not measured"})
    return out


def aggregate(results: dict) -> dict:
    """Counts only, safe to forward: negative controls totalled, no pattern names, no finding ids."""
    keep = ("tp", "fp", "fn", "intervals", "label_accuracy", "cost_usd", "cost_if_fresh_usd", "fresh", "truncated")
    agg = {"spent_usd": results["spent_usd"], "steps": results["steps"], "thresholds": results["thresholds"],
           "releases": {}}
    for rel, r in results["releases"].items():
        rows = {}
        for sysn, s in r["scores"].items():
            row = {k: s[k] for k in keep if k in s}
            nc = s.get("negative_controls") or {}
            row["negative_control_hits"] = [sum(v["false_positives"] for v in nc.values()),
                                            sum(v["total"] for v in nc.values())]
            ev = s.get("evidence_support")
            row["evidence_support"] = {"share": ev["share"], "total": ev["total"]} if ev else None
            rows[sysn] = row
        agg["releases"][rel] = {"issue_free": r["issue_free"], "systems": rows,
                                "auditor_jaccard": ((r.get("e3") or {}).get("semaudit-full") or {})
                                .get("stability", {}).get("jaccard"),
                                "b_judge_1_jaccard": r.get("b_judge_1_jaccard")}
    return agg


def _spent() -> float:
    p = ROOT / "runs/ledger.jsonl"
    return sum(json.loads(x)["cost_usd"] or 0 for x in p.read_text().splitlines()
               if not json.loads(x)["cached"]) if p.exists() else 0.0


def _frozen() -> str | None:
    f = ROOT / "bench/conditions/FROZEN-POSTFIX.md"
    return f.read_text().splitlines()[0] if f.exists() else None


if __name__ == "__main__":
    main()
