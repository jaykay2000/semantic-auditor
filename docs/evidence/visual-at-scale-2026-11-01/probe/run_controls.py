"""Send each mutated control (from make_controls.py) through the same `visual.check_issue` path as the real issue:
same crop, same role, same seed; only the claimed quote differs. Run from a root whose semaudit.toml has
[roles.vision] (see ../README.md).

    python run_controls.py <review.json> <controls.json> <out.json> <crops_dir> --max-usd X
"""
import argparse
import copy
import json
from pathlib import Path

from semaudit.models.router import Router
from semaudit.verify import visual as V

ap = argparse.ArgumentParser()
ap.add_argument("review", type=Path)
ap.add_argument("controls", type=Path)
ap.add_argument("out", type=Path)
ap.add_argument("crops", type=Path)
ap.add_argument("--max-usd", type=float, required=True)
ap.add_argument("--seed", type=int, default=1)
a = ap.parse_args()

d = json.loads(a.review.read_text())
events = {(p["id"], e["id"]): e for p in d["personas"] for e in p["events"]}
issues = {i["id"]: i for i in d["issues"]}
router = Router(root=Path.cwd(), max_usd=a.max_usd)
rows = []
for c in json.loads(a.controls.read_text())["controls"]:
    if c["control_quote"] is None:
        rows.append({**c, "visual": None})
        continue
    issue = copy.deepcopy(issues[c["issue"]])
    e, quote = V.target(issue, events)
    assert quote == c["real_quote"], c["issue"]
    for occ in issue["occurrences"]:          # the occurrence `target` used: the first that cites a web event
        if any((events.get((occ.get("persona"), x)) or {}).get("capture", {}).get("kind") == "web"
               for x in occ.get("events") or []):
            occ["quotes"] = [c["control_quote"]] + list((occ.get("quotes") or [])[1:])
            break
    v = V.check_issue(issue, V.basis_of(issue), events, a.review.parent, router, role="vision", seed=a.seed,
                      crops_dir=a.crops)
    assert v.get("quote") == c["control_quote"], c["issue"]
    rows.append({**c, "visual": v})
    print(c["issue"], v["result"], repr(v.get("reads")))
a.out.write_text(json.dumps({"review": a.review.name, "seed": a.seed, "rows": rows}, indent=1, ensure_ascii=False) + "\n")
print(f"spent ${router.spent_usd:.4f}")
