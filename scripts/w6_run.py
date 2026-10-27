"""W6: extraction from real captures.

Builds a story from every episode in a capture run, extracts each distinct message once (Muse Spark,
cached by content hash), grades the extraction against the hand-authored gold, and writes the stories
with their extractions to runs/<run>/stories/ for W7/W8.

Acceptance: every hero/boundary message exactly right on every fresh repeat; >= 90% of the rest.
Run from the repo root:  python3 scripts/w6_run.py --run runs/w6 [--repeats 3] [--max-usd 1]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))

from extraction_gold import FIELDS, HERO, gold_for  # noqa: E402

from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.extract.messages import extract_unique  # noqa: E402
from semaudit.models.router import Router  # noqa: E402
from semaudit.story.build import story_from_episode  # noqa: E402
from semaudit.story.episode import Episode  # noqa: E402


def mismatches(x: dict, g: dict) -> list[str]:
    errs = [f"{k}: {x[k]} != {g[k]}" for k in FIELDS if x[k] != g[k]]
    xc = sorted((c["type"], float(c["value"])) for c in x["claims"])
    gc = sorted((c["type"], float(c["value"])) for c in g["claims"])
    if xc != gc:
        errs.append(f"claims: {xc} != {gc}")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--max-usd", type=float, required=True)
    args = ap.parse_args()
    contract = load_contract(ROOT / "examples" / "northbound" / "contract")
    router = Router(root=ROOT, max_usd=args.max_usd)
    stories = [story_from_episode(Episode.read(p), contract) for p in sorted((args.run / "episodes").glob("*/*.json"))]
    msgs = [{"feature": e.feature, "channel": e.channel, "text": e.text, "key": e.copy_key}
            for s in stories for e in s.messages()]
    key_of = {(m["feature"] or "", m["channel"] or "", m["text"]): m["key"] for m in msgs}
    print(f"{len(stories)} stories, {len(msgs)} message impressions, {len(key_of)} distinct messages")

    ok = True
    report = {"repeats": []}
    first = None
    for rep in range(args.repeats):
        ext = extract_unique(msgs, contract, router, fresh=True)
        first = first or ext
        hero_bad, rest_bad, ungraded, rows = [], [], [], {}
        for k, x in ext.items():
            key = key_of[k]
            g = gold_for(key, k[2])
            if g is None:
                ungraded.append(key)
                continue
            errs = mismatches(x.model_dump(), g)
            rows[f"{key} | {k[2][:50]}"] = errs
            if errs:
                (hero_bad if key in HERO else rest_bad).append((key, errs))
        n_hero = sum(1 for k in ext if key_of[k] in HERO)
        n_rest = len(ext) - n_hero - len(ungraded)
        rest_acc = 1 - len(rest_bad) / n_rest if n_rest else 1.0
        passed = not hero_bad and rest_acc >= 0.9 and not ungraded
        ok &= passed
        print(f"repeat {rep + 1}: hero {n_hero - len(hero_bad)}/{n_hero} exact · rest {n_rest - len(rest_bad)}/{n_rest} "
              f"({rest_acc:.0%}) · ungraded {len(ungraded)} · spent ${router.spent_usd:.3f}")
        for key, errs in hero_bad + rest_bad:
            print(f"   ✗ {key}: {'; '.join(errs)}")
        for key in ungraded:
            print(f"   ? no gold for {key}")
        report["repeats"].append({"hero_bad": hero_bad, "rest_bad": rest_bad, "ungraded": ungraded,
                                  "rest_accuracy": rest_acc, "rows": rows})

    out = args.run / "stories"
    out.mkdir(exist_ok=True)
    for s in stories:
        for e in s.messages():
            e.extraction = first[(e.feature or "", e.channel or "", e.text)]
        (out / f"{s.id}.json").write_text(s.model_dump_json(indent=1))
    report["spent_usd"] = round(router.spent_usd, 4)
    (args.run / "w6_report.json").write_text(json.dumps(report, indent=1, default=str, ensure_ascii=False))
    print(f"stories with extractions (repeat 1): {out}")
    print("W6 ACCEPTED" if ok else "W6 NOT ACCEPTED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
