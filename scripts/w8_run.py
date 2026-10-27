"""W8: the semantic core on REAL captures.

For every captured story: fresh extraction (once per distinct message), code generators and rule evaluation,
fresh P2 interpretation with shuffled candidate order. The result is compared with the hand-authored expected
vector of the matching W1b story, translated from fixture event ids to captured event ids.

Comparison, per story with a fixture:
- every expected entry must appear exactly (rule, subject, status, label, exception conditions);
- no other entry may mention an event the fixture covers;
- entries on events the fixture does not cover (core pages, greetings) must not be violations.
Stories without a fixture on the base release (2.3) are negative controls: they must raise nothing at all.

Then the falsifiability stubs (always-conflict, always-compatible, all-suggest extractor) must FAIL.
Run from the repo root:  python3 scripts/w8_run.py --run runs/w6 --runs 5 --max-usd 2
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.extract.messages import extract_unique  # noqa: E402
from semaudit.models.router import Router  # noqa: E402
from semaudit.relate.compare import entry_key  # noqa: E402
from semaudit.relate.interpret import model_interpreter, stub_always  # noqa: E402
from semaudit.relate.rules import evaluate  # noqa: E402
from semaudit.story.build import story_from_episode  # noqa: E402
from semaudit.story.episode import Episode  # noqa: E402
from semaudit.story.model import Extraction  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "stories"
FIXTURE_FOR = {("2.3", "maya"): "maya_23", ("2.4.1", "rina"): "rina", ("2.4.1", "maya"): "maya_241",
               ("2.4.1", "kai"): "kai_241",           # audit P1: cg.reconcile does not reconcile wait vs book now
               ("2.4", "family"): "maya"}           # NC4: the family's story is Maya's, with their own totals
EMAIL_ALIAS = {"pw.card": "pw.email.forecast", "pw.card.nodrop": "pw.email.forecast.nodrop"}
SLACK = timedelta(seconds=15)                        # fixtures place renders +5/+10 s after the action


def fixture_name(release: str, persona: str) -> str | None:
    if (release, persona) in FIXTURE_FOR:
        return FIXTURE_FOR[(release, persona)]
    f = FIX / f"{persona}.json"
    if f.exists() and json.loads(f.read_text())["story"]["release"] == release:
        return persona
    return None


def translate(fixture: dict, story) -> tuple[list[dict], set[str], list[str]]:
    """Fixture expected vector -> captured ids. Returns (expected, covered captured ids, unmatched fixture ids)."""
    real = story.messages()
    ids, unmatched = {}, []
    for fe in fixture["story"]["events"]:
        if fe["kind"] != "message":
            continue
        key = EMAIL_ALIAS.get(fe["copy_key"], fe["copy_key"]) if fe["channel"] == "email" else fe["copy_key"]
        at = datetime.fromisoformat(fe["at"])
        hit = [e for e in real if e.copy_key == key and e.feature == fe["feature"] and abs(e.at - at) <= SLACK]
        if len(hit) == 1:
            ids[fe["id"]] = hit[0].id
        else:
            unmatched.append(fe["id"])
    expected = [{**x, "subject": ids.get(x["subject"], x["subject"])} for x in fixture["expected"]]
    return expected, set(ids.values()), unmatched


def judge(entries, expected, covered, has_fixture) -> dict:
    got = {entry_key(*e.key()): e for e in entries}
    want = {entry_key(x["rule"], x["subject"], x["status"], x.get("label"), x.get("conditions", ())) for x in expected}
    if not has_fixture:
        bad = sorted(str(k) for k, e in got.items() if e.status == "violated")
        return {"match": not bad, "missing": [], "unexpected": bad}
    story_level = {"story"} | {x["subject"] for x in expected if "|" in x["subject"]}
    missing = sorted(str(k) for k in want - set(got))
    unexpected = sorted(str(k) for k, e in got.items() if k not in want and (
        e.subject in covered or e.subject in story_level or e.status == "violated"))
    return {"match": not missing and not unexpected, "missing": missing, "unexpected": unexpected}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--max-usd", type=float, required=True)
    ap.add_argument("--cached-extraction", action="store_true",
                    help="reuse cached extraction (unchanged inputs); interpretation is still fresh every run")
    args = ap.parse_args()
    contract = load_contract(ROOT / "examples" / "northbound" / "contract")
    router = Router(root=ROOT, max_usd=args.max_usd)
    episodes = [Episode.read(p) for p in sorted((args.run / "episodes").glob("*/*.json"))]
    stories = {(ep.release, ep.persona): story_from_episode(ep, contract) for ep in episodes}
    cases = {}
    for (rel, per), s in stories.items():
        name = fixture_name(rel, per)
        if name is None and rel != "2.3":
            continue                                 # head stories without an authored vector: not graded here
        fx = json.loads((FIX / f"{name}.json").read_text()) if name else None
        exp, cov, unm = translate(fx, s) if fx else ([], set(), [])
        if unm:
            print(f"   ! {rel}/{per}: fixture events with no unique captured match: {unm}")
        cases[(rel, per)] = (s, exp, cov, fx is not None)
    print(f"{len(cases)} graded stories ({sum(c[3] for c in cases.values())} against fixtures, "
          f"{sum(not c[3] for c in cases.values())} negative controls on 2.3)")
    msgs = [{"feature": e.feature, "channel": e.channel, "text": e.text} for s, *_ in cases.values() for e in s.messages()]

    report, runs, ext0 = {"runs": []}, [], None

    def attach(s, ext, mutate=None):
        for e in s.messages():
            x = ext[(e.feature or "", e.channel or "", e.text)]
            e.extraction = Extraction(**(x.model_dump() | (mutate or {})))

    for run in range(args.runs):
        ext = extract_unique(msgs, contract, router, fresh=not args.cached_extraction)
        ext0 = ext0 or ext
        row = {}
        for (rel, per), (s, exp, cov, hf) in sorted(cases.items()):
            attach(s, ext)
            interp = model_interpreter(router, fresh=True, rng=random.Random(f"{run}:{rel}:{per}"))
            entries = evaluate(s, contract, interp)
            row[f"{rel}/{per}"] = judge(entries, exp, cov, hf) | {
                "p2": [e.__dict__ for e in entries if e.rule == "P2"]}
        n = sum(v["match"] for v in row.values())
        print(f"run {run + 1}: {n}/{len(row)} stories match   (spent ${router.spent_usd:.3f})")
        for k, v in row.items():
            if not v["match"]:
                print(f"   ✗ {k}: missing={v['missing']} unexpected={v['unexpected']}")
        report["runs"].append(row)
        runs.append(n == len(row))

    def stub(make, mutate=None):
        fails = []
        for (rel, per), (s, exp, cov, hf) in sorted(cases.items()):
            attach(s, ext0, mutate)
            if not judge(evaluate(s, contract, make(rel, per)), exp, cov, hf)["match"]:
                fails.append(f"{rel}/{per}")
        return fails

    report["stubs"] = {
        "always_conflict": stub(lambda r, p: stub_always("conflict")),
        "always_compatible": stub(lambda r, p: stub_always("compatible")),
        "all_suggest_extractor": stub(lambda r, p: model_interpreter(router, fresh=False, rng=random.Random(f"0:{r}:{p}")),
                                      {"strength": "suggest"}),
    }
    for k, v in report["stubs"].items():
        print(f"stub {k}: {'FAILS as required' if v else 'PASSES: the test does not bite!'} ({len(v)}: {v})")
    report["spent_usd"] = round(router.spent_usd, 4)
    out = args.run / f"w8_report_{datetime.now():%Y%m%dT%H%M%S}.json"
    out.write_text(json.dumps(report, indent=1, default=str, ensure_ascii=False))
    ok = all(runs) and all(report["stubs"].values())
    print(f"report: {out}\n" + ("W8 ACCEPTED" if ok else "W8 NOT ACCEPTED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
