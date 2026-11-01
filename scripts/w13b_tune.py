"""W13b baseline tuning on the narrative fixture (Northbound 2.4, dev only).

One round = B-judge-1 and B-judge-N on the auditor's own 2.4 captures (runs/e2e-2), fresh model calls, scored
against the dev truth (bench/dev). Writes runs/w13b-tune/round-<n>/ with findings, scores, and what was
missed or wrongly raised, plus the prompt digests the round used. The prompts are revised between rounds
from misses on THIS fixture only, exactly as the auditor's rubric was; they are frozen before any bench run.

  python3 scripts/w13b_tune.py --round 0 --max-usd 1.0 [--only judge_one|judge_multi]
"""
import argparse
import hashlib
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from semaudit.bench import judge  # noqa: E402
from semaudit.bench.findings import Truth, from_review  # noqa: E402
from semaudit.bench.match import evidence_index, score  # noqa: E402
from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.models.router import Router  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", required=True)
    ap.add_argument("--max-usd", type=float, required=True)
    ap.add_argument("--only", choices=["judge_one", "judge_multi"])
    a = ap.parse_args()
    out = ROOT / "runs/w13b-tune" / f"round-{a.round}"
    out.mkdir(parents=True, exist_ok=True)
    c = load_contract(ROOT / "examples/northbound/contract")
    truth = Truth.model_validate(json.loads((ROOT / "bench/dev/northbound-2.4.truth.json").read_text()))
    review = json.loads((ROOT / "runs/e2e-2/review-2.3-2.4.json").read_text())
    ev = evidence_index(review)
    stories = judge.stories_for(ROOT / "runs/e2e-2", "2.4", c)
    router = Router(ROOT, max_usd=a.max_usd)
    prompts = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16]
               for p in sorted((judge.CONDITIONS / "prompts").glob("*.md"))}
    summary = {"round": a.round, "prompts": prompts, "systems": {}}
    jn = tomllib.loads((judge.CONDITIONS / "conditions.toml").read_text())["B-judge-N"]
    effort, samples = jn.get("effort", {}), jn.get("samples", 1)
    summary["judge_multi_plan"] = {"effort": effort, "samples": samples}
    runs = {"judge_one": judge.judge_one,
            "judge_multi": lambda *x, **k: judge.judge_multi(*x, effort=effort, samples=samples, **k)}
    for name, fn in runs.items():
        if a.only and name != a.only:
            continue
        fs, dropped = fn(stories, c, router, release="2.4", fresh=True)
        s = score(fs, truth, evidence=ev)
        (out / f"{fs.system}.findings.json").write_text(fs.model_dump_json(indent=1))
        missed = [i.model_dump() for i in truth.items if i.kind == "issue" and
                  sum(1 for m in s["matched"] if m[2] == i.id) < len(i.personas)]
        summary["systems"][fs.system] = {k: s[k] for k in ("tp", "fp", "fn", "precision", "recall",
                                                           "negative_controls", "label_confusion", "cost_usd",
                                                           "calls")}
        summary["systems"][fs.system].update(
            evidence=s["evidence_support"], dropped=dropped, missed=[(i["id"], i["rule"], i["target"]) for i in missed],
            nc_hits=s["negative_control_hits"], unmatched=s["unmatched"])
        print(f"{fs.system}: tp {s['tp']} fp {s['fp']} fn {s['fn']}  P {s['precision']} R {s['recall']}  "
              f"${fs.cost_usd}  evidence {s['evidence_support']['share']}  dropped {len(dropped)}")
    auditor = score(from_review(review), truth, evidence=ev)
    summary["auditor_reference"] = {k: auditor[k] for k in ("tp", "fp", "fn", "precision", "recall")}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    print(f"spent this round: ${router.spent_usd:.4f}", "->", out / "summary.json")


if __name__ == "__main__":
    main()
