"""Negative control: the real tax-line issue, but the text record claims $39.99 (the subtotal), not $43.19."""
import json
import pathlib
import sys

from semaudit.models.router import Router
from semaudit.verify import visual as V

review, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
d = json.loads(review.read_text())
events = {(p["id"], e["id"]): e for p in d["personas"] for e in p["events"]}
issue = json.loads(json.dumps(d["issues"][0]))
issue["occurrences"][0]["quotes"] = ["$39.99"]
r = Router(root=pathlib.Path.cwd(), max_usd=0.05)
v = V.check_issue(issue, V.basis_of(issue), events, review.parent, r, role="vision", seed=1, crops_dir=out)
print(json.dumps(v, indent=1))
(out / "control.json").write_text(json.dumps({"claimed_quote": "$39.99", "visual": v}, indent=1) + "\n")
