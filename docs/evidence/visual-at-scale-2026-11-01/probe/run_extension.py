"""The extension (owner-approved 2026-11-01): `semaudit visual` on every eligible issue of more reviews, plus one
mutated control each, all under ONE spend cap. Same code path as the first run: `visual.visual_confirm` for the real
issues (what the CLI calls) and `visual.check_issue` on a copy of the issue for the control; the control claims come
from make_controls.py, unchanged since it was committed. Seed 1, the [roles.vision] of the root it runs from.

    python run_extension.py <reviews.txt> <out_dir> --max-usd 0.5

reviews.txt: one review path per line. Writes <out_dir>/<key>/{real.visual.json, controls.json, real-crops/,
control-crops/} and <out_dir>/rows.jsonl (one row per sent issue, with quote text: keep it out of the repo for a
private app).
"""
import argparse
import copy
import json
from pathlib import Path

from make_controls import main as make_controls

from semaudit.models.router import Router
from semaudit.verify import visual as V

ap = argparse.ArgumentParser()
ap.add_argument("reviews", type=Path)
ap.add_argument("out", type=Path)
ap.add_argument("--max-usd", type=float, required=True)
a = ap.parse_args()

router = Router(root=Path.cwd(), max_usd=a.max_usd)
rows = []
for line in a.reviews.read_text().split():
    review = Path(line)
    key = f"{review.parents[2].name}__{review.parent.name}__{review.stem}"
    out = a.out / key
    out.mkdir(parents=True, exist_ok=True)
    make_controls(review, out / "controls.json")
    counts = V.visual_confirm(review, out / "real.visual.json", router, crops_dir=out / "real-crops")
    print(key, counts, f"spent ${router.spent_usd:.4f}", flush=True)
    d = json.loads(review.read_text())
    events = {(p["id"], e["id"]): e for p in d["personas"] for e in p["events"]}
    issues = {i["id"]: i for i in d["issues"]}
    real = {i["id"]: i.get("visual") for i in json.loads((out / "real.visual.json").read_text())["issues"]}
    controls = {c["issue"]: c for c in json.loads((out / "controls.json").read_text())["controls"]}
    for iid, v in real.items():
        if v is None or "sent_sha256" not in v and v.get("reason") == "no cited event has a web capture":
            if v is not None:
                rows.append({"review": key, "issue": iid, "sent": False, "real": v, "control": None})
            continue
        c = controls.get(iid)
        cv = None
        if c is not None and c["control_quote"] is not None:
            issue = copy.deepcopy(issues[iid])
            e, quote = V.target(issue, events)
            assert quote == c["real_quote"], iid
            for occ in issue["occurrences"]:
                if any((events.get((occ.get("persona"), x)) or {}).get("capture", {}).get("kind") == "web"
                       for x in occ.get("events") or []):
                    occ["quotes"] = [c["control_quote"]] + list((occ.get("quotes") or [])[1:])
                    break
            cv = V.check_issue(issue, V.basis_of(issue), events, review.parent, router, role="vision", seed=1,
                               crops_dir=out / "control-crops")
            assert cv.get("quote") == c["control_quote"], iid
        rows.append({"review": key, "issue": iid, "sent": "sent_sha256" in v, "real": v,
                     "control": None if c is None else {**c, "visual": cv}})
    print(key, "controls done", f"spent ${router.spent_usd:.4f}", flush=True)
with (a.out / "rows.jsonl").open("w") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"total spent ${router.spent_usd:.4f}")
