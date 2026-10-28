"""Input ablation of B-judge-1 on the sealed releases (bench/conditions/INPUT-ABLATION.md).
RUN BY THE BENCHMARK CUSTODIAN ONLY. The building session never runs this, and never reads its inputs or
per-finding outputs.

Judges the sealed run's own `semaudit-full r1` captures with the three variants, once each, under one total cap.
A call is checked against what is left before it starts and SKIPPED (recorded) if the per-call cap does not fit.
Writes input-ablation.json beside the run's results. Prints COUNTS ONLY, with negative controls totalled (no
pattern names), so stdout is safe to forward.

  python3 scripts/w13b_inputs.py --sealed <sealed dir> --results <results dir of the 2026-10-27 run> \
      --releases bench-01,bench-02,bench-03 --max-usd 1.00
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from semaudit.bench import inputs, judge  # noqa: E402
from semaudit.bench.findings import Truth  # noqa: E402
from semaudit.bench.match import evidence_index, score  # noqa: E402
from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.models.router import ModelError, Router  # noqa: E402

PER_CALL_CAP = 0.20
ABLATIONS = ("no-verifier", "no-exceptions", "no-generators")   # auditor ablation reviews beside r1
KEEP = ("tp", "fp", "fn", "intervals", "label_accuracy", "cost_usd", "cost_if_fresh_usd", "fresh", "truncated")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sealed", type=Path, required=True)
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--releases", required=True)
    ap.add_argument("--max-usd", type=float, required=True)
    a = ap.parse_args()
    left, log, out = a.max_usd, [], {"plan": "bench/conditions/INPUT-ABLATION.md", "pre_adjudication": True,
                                      "releases": {}}
    for variant in inputs.VARIANTS:
        for rel in a.releases.split(","):
            name = f"{variant} {rel}"
            if left < PER_CALL_CAP:
                log.append({"step": name, "status": "skipped", "why": f"${left:.2f} left < ${PER_CALL_CAP}"})
                continue
            c = load_contract(a.sealed / "contracts" / rel)
            run_dir = a.results / "runs" / f"{rel}-r1"
            stories = judge.stories_for(run_dir, rel, c)
            t0 = time.time()
            try:
                fs, _ = inputs.judge_variant(variant, stories, c, Router(ROOT, max_usd=min(PER_CALL_CAP, left)),
                                             release=rel)
            except ModelError as e:
                log.append({"step": name, "status": f"not measured: {e}"})
                continue
            left -= fs.cost_usd
            truth = Truth.model_validate(json.loads((a.sealed / "ground_truth/normalized" / f"{rel}.truth.json")
                                                    .read_text()))
            review = next(p for p in sorted(run_dir.glob("review-*.json"))
                          if not any(p.name.endswith(f".{x}.json") for x in ABLATIONS))
            s = score(fs, truth, evidence=evidence_index(json.loads(review.read_text())))
            out["releases"].setdefault(rel, {})[fs.system] = s
            log.append({"step": name, "status": "done", "spent_usd": round(fs.cost_usd, 4),
                        "seconds": round(time.time() - t0)})
            print(f"{name}: done (${fs.cost_usd:.3f}, ${left:.2f} left)", flush=True)
    out["steps"], out["spent_usd"] = log, round(a.max_usd - left, 4)
    (a.results / "input-ablation.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(aggregate(out), indent=1))


def aggregate(out: dict) -> dict:
    """Counts only. Negative controls are totalled, so no sealed pattern name is printed."""
    agg = {"spent_usd": out["spent_usd"], "steps": out["steps"], "releases": {}}
    for rel, systems in out["releases"].items():
        agg["releases"][rel] = {}
        for sysn, s in systems.items():
            row = {k: s[k] for k in KEEP if k in s}
            nc = s.get("negative_controls") or {}
            row["negative_control_hits"] = [sum(v["false_positives"] for v in nc.values()),
                                            sum(v["total"] for v in nc.values())]
            ev = s.get("evidence_support")
            row["evidence_support"] = {"share": ev["share"], "total": ev["total"]} if ev else None
            row["dropped_malformed"] = len(s.get("malformed", []))
            agg["releases"][rel][sysn] = row
    return agg


if __name__ == "__main__":
    main()
