"""One row per run x check: each release's votes, evidence status and assertion, the base->head outcome, and the
run's all-in cost (sum of the result-level cost_usd). Reads saved-checks.json files only; no model call.

    python summarize.py runs/*/saved-checks.json > summary.json
"""
import json
import sys
from pathlib import Path

rows, runs = [], []
for f in sys.argv[1:]:
    d = json.loads(Path(f).read_text())
    cost = 0.0
    for c in d["checks"]:
        row = {"run": d["run"], "check": c["id"], "outcome": c["memory"]["status"], "why": c["memory"].get("why")}
        for rel in (d["base"], d["head"]):
            r = c["results"][rel]
            cost += r.get("cost_usd") or 0
            row[rel] = {"assertion": r["assertion"]["outcome"], "votes": r["assertion"]["votes"],
                        "agreement": r["semantic_confidence"]["agreement"], "evidence": r["evidence"]["status"],
                        "replay": r["replay"]["status"], "malformed_reasks": r.get("malformed_reasks"),
                        "runaway_retries": r.get("runaway_retries"), "cost_usd": r.get("cost_usd")}
        rows.append(row)
    runs.append({"run": d["run"], "at": d["at"], "cost_usd": round(cost, 6), "loaded_from_storage": d["loaded_from_storage"]})
print(json.dumps({"runs": runs, "total_cost_usd": round(sum(r["cost_usd"] for r in runs), 6), "rows": rows}, indent=1))
