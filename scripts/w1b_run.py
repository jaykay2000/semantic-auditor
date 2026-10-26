"""W1b: semantic-core proof with the real model.

For each hand-authored story: the model extracts every message from raw text, code builds
candidates and evaluates rules, the model labels P2 candidates; the result is compared
with the authored expected vector as an exact set. Five fresh runs, shuffled candidate
order. Then three stubs that must FAIL: always-conflict, always-compatible, all-suggest.

Run from the repo root:  python3 scripts/w1b_run.py [--runs 5] [--max-usd 6]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.extract.messages import extract_story  # noqa: E402
from semaudit.models.router import Router  # noqa: E402
from semaudit.relate.compare import diff  # noqa: E402
from semaudit.relate.interpret import model_interpreter, stub_always  # noqa: E402
from semaudit.relate.rules import evaluate  # noqa: E402
from semaudit.story.model import Extraction, Story  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "stories"


def load_all():
    raws = {p.stem: json.loads(p.read_text()) for p in sorted(FIX.glob("*.json")) if p.stem != "copy_gold"}
    return raws, json.loads((FIX / "copy_gold.json").read_text())


def attach(raw, extraction):
    story = Story(**raw["story"])
    for e in story.messages():
        e.extraction = extraction[e.id]
    return story


def extraction_errors(story, gold):
    errs = []
    for e in story.messages():
        g, x = gold[e.copy_key], e.extraction.model_dump()
        for k in ("message_kind", "decision", "action", "strength", "explains_own_tradeoff"):
            if x[k] != g[k]:
                errs.append(f"{e.id}.{k}: got {x[k]} want {g[k]}")
        gc = sorted((c["type"], c["value"]) for c in g["claims"])
        xc = sorted((c["type"], c["value"]) for c in x["claims"])
        if gc != xc:
            errs.append(f"{e.id}.claims: got {xc} want {gc}")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--max-usd", type=float, default=6.0)
    args = ap.parse_args()
    router = Router(root=ROOT, max_usd=args.max_usd)
    contract = load_contract(ROOT / "examples" / "northbound" / "contract")
    raws, gold = load_all()
    out_dir = ROOT / "runs" / "w1b" / time.strftime("%Y%m%dT%H%M%S")
    out_dir.mkdir(parents=True)
    report = {"runs": [], "stubs": {}}
    run0_extractions = {}

    for run in range(args.runs):
        def one(name):
            raw = raws[name]
            ext = extract_story(Story(**raw["story"]), contract, router, fresh=True)
            story = attach(raw, ext)
            interp = model_interpreter(router, fresh=True, rng=random.Random(f"{run}:{name}"))
            entries = evaluate(story, contract, interp)
            return name, ext, diff(entries, raw["expected"]), extraction_errors(story, gold), \
                [e.__dict__ | {"conditions": e.conditions} for e in entries if e.rule == "P2"]

        names = list(raws)
        random.Random(run).shuffle(names)
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(one, names))
        row = {}
        for name, ext, d, xerr, p2 in results:
            row[name] = {**d, "extraction_errors": xerr, "p2": p2}
            if run == 0:
                run0_extractions[name] = ext
        matched = sum(v["match"] for v in row.values())
        print(f"run {run + 1}: {matched}/{len(row)} stories match   (spent ${router.spent_usd:.3f})")
        for name, v in sorted(row.items()):
            if not v["match"]:
                print(f"   ✗ {name}: missing={v['missing']} unexpected={v['unexpected']}")
                for x in v["extraction_errors"]:
                    print(f"       extraction: {x}")
        report["runs"].append(row)

    # Falsifiability controls, on run-1 extractions (no new extraction spend).
    def stub_result(interpreter_factory, mutate=None):
        fails = []
        for name, raw in raws.items():
            ext = {k: Extraction(**(v.model_dump() | (mutate or {}))) for k, v in run0_extractions[name].items()}
            story = attach(raw, ext)
            if not diff(evaluate(story, contract, interpreter_factory(name)), raw["expected"])["match"]:
                fails.append(name)
        return fails

    report["stubs"]["always_conflict"] = stub_result(lambda n: stub_always("conflict"))
    report["stubs"]["always_compatible"] = stub_result(lambda n: stub_always("compatible"))
    report["stubs"]["all_suggest_extractor"] = stub_result(
        lambda n: model_interpreter(router, fresh=False, rng=random.Random(f"0:{n}")), {"strength": "suggest"})
    for k, v in report["stubs"].items():
        print(f"stub {k}: {'FAILS as required' if v else 'PASSES — the test does not bite!'} ({len(v)} stories: {sorted(v)})")

    per_story = {n: sum(r[n]["match"] for r in report["runs"]) for n in raws}
    report["summary"] = {"per_story_matches": per_story, "runs": args.runs,
                         "all_stories_all_runs": all(v == args.runs for v in per_story.values()),
                         "all_stubs_fail": all(report["stubs"].values()), "spent_usd": round(router.spent_usd, 4)}
    (out_dir / "report.json").write_text(json.dumps(report, indent=1, default=str, ensure_ascii=False))
    print(json.dumps(report["summary"], indent=1))
    print(f"report: {out_dir.relative_to(ROOT)}/report.json")
    ok = report["summary"]["all_stories_all_runs"] and report["summary"]["all_stubs_fail"]
    print("W1b ACCEPTED" if ok else "W1b NOT ACCEPTED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
