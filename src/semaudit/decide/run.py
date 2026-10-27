"""`semaudit review`: the end-to-end path on one app (W9).

capture base + head -> stories -> rules -> issues -> re-capture the affected personas -> verify -> policy
-> review.json. Every model call goes through the router with a spend cap; capture and rules are code.
"""

from __future__ import annotations

from pathlib import Path

from semaudit.capture import Runner
from semaudit.contract.approve import approval_state
from semaudit.contract.schema import load_contract
from semaudit.decide.issues import apply_delta, build_issues
from semaudit.decide.pipeline import evaluate_release
from semaudit.models.router import Router
from semaudit.report import manifest as mf
from semaudit.report.review import assemble, write
from semaudit.story.build import story_from_episode
from semaudit.verify.steps import verify


def run_review(contract_dir: Path, base: str, head: str, *, run_id: str, runs_dir: Path, max_usd: float,
               reuse: bool = False, fresh: bool = False, models: bool = True, root: Path | None = None) -> Path:
    contract = load_contract(contract_dir)
    router = Router(root=root or Path.cwd(), max_usd=max_usd)
    run_dir = runs_dir / run_id
    if not (reuse and (run_dir / "episodes" / base).exists() and (run_dir / "episodes" / head).exists()):
        with Runner(contract_dir, runs_dir=runs_dir, run_id=run_id) as r:
            r.capture(base)
            r.capture(head)
    b = evaluate_release(run_dir, base, contract, router, fresh=fresh)
    h = evaluate_release(run_dir, head, contract, router, fresh=fresh)
    head_issues = build_issues(head, h.results, contract)
    base_issues = build_issues(base, b.results, contract)
    resolved, unconfirmed = apply_delta(head_issues, base_issues, set(b.results), set(h.results))

    affected = sorted({p for i in head_issues for p in i.personas})
    repro = {}
    if affected:
        with Runner(contract_dir, runs_dir=runs_dir, run_id=f"{run_id}-repro") as r:
            for ep in r.capture(head, affected):
                repro[ep.persona] = story_from_episode(ep, contract)
    stories = {p: s for p, (s, _) in h.results.items()}
    for i in head_issues:
        verify(i, stories, h.episodes, run_dir, contract, router, repro=repro, fresh=fresh, models=models)
    out = run_dir / f"review-{base}-{head}.json"
    manifest = mf.build(contract_dir, contract, run_dir, base, head, router=router, models=models, max_usd=max_usd,
                        repro_run=f"{run_id}-repro" if affected else None)
    review = assemble(b, h, contract, head_issues, resolved, router.spent_usd,
                      approval=approval_state(contract_dir, contract), unconfirmed=unconfirmed,
                      manifest=manifest, review_path=str(out))
    return write(review, out)
