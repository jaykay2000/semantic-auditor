"""E3 release reproducibility (docs/08-evaluation.md), for what can be measured without the explorer.

  stability     mean pairwise Jaccard of the finding units across k FRESH runs (cache disabled)
  replay        the share of findings whose `semaudit repro` reproduces them (replay of evidence, which may hit
                the cache: it measures that a finding can be shown again, not that inference is stable)
  attribution   new / changed / existing and the responsible features, from the matcher, per run

B-repeat (the explorer plus a multi-pass judge over the explorer's own captures) is NOT measured here: it needs
B-explore. The judge baselines' stability on the auditor's captures is reported under its own name,
"judgement stability", so it is never read as B-repeat.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .findings import Findings, Truth, from_review
from .match import evidence_index, jaccard, score, wilson


def stability(runs: list[Findings]) -> dict[str, Any]:
    fresh = [r for r in runs if r.fresh]
    return {"k": len(runs), "fresh": len(fresh), "jaccard": jaccard(runs) if len(fresh) == len(runs) >= 2 else None,
            "note": None if len(fresh) == len(runs) else "not every run was fresh: stability not reported"}


def replay_success(review_path: Path, *, max_usd: float, issue_ids: list[str] | None = None) -> dict[str, Any]:
    from semaudit.decide.repro import replay
    review = json.loads(review_path.read_text())
    ids = issue_ids or [i["id"] for i in review["issues"]]
    rows = {}
    for iid in ids:
        try:
            res = replay(review_path, iid, max_usd=max_usd)
            rows[iid] = {"reproduced": res.ok, "failed_checks": [c.name for c in res.checks if not c.ok]}
        except Exception as e:                      # could not measure: counted, not hidden
            rows[iid] = {"reproduced": None, "error": f"{type(e).__name__}: {e}"[:300]}
    measured = [r for r in rows.values() if r["reproduced"] is not None]
    return {"issues": rows, "share": wilson(sum(r["reproduced"] for r in measured), len(measured)),
            "not_measured": len(rows) - len(measured)}


def report(reviews: list[Path], truth: Truth, *, replay_usd: float | None = None,
           judge_runs: dict[str, list[Path]] | None = None) -> dict[str, Any]:
    loaded = [json.loads(p.read_text()) for p in reviews]
    runs = [from_review(r, run=str(n)) for n, r in enumerate(loaded, 1)]
    scores = [score(f, truth, evidence=evidence_index(r)) for f, r in zip(runs, loaded)]
    out: dict[str, Any] = {
        "semaudit-full": {
            "stability": stability(runs),
            "per_run": [{k: s[k] for k in ("tp", "fp", "fn", "intervals", "attribution", "cost_usd",
                                           "cost_if_fresh_usd", "fresh")} for s in scores],
            "replay": ({str(p): replay_success(p, max_usd=replay_usd) for p in reviews} if replay_usd is not None
                       else None),
        },
        "B-repeat": {"measured": False, "why": "needs B-explore (not built)"},
    }
    for name, paths in (judge_runs or {}).items():
        jr = [Findings.model_validate_json(p.read_text()) for p in paths]
        out[name] = {"judgement_stability": stability(jr),
                     "per_run": [{k: v for k, v in score(f, truth).items() if k in ("tp", "fp", "fn")} for f in jr]}
    return out
