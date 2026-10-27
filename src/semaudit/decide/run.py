"""`semaudit review`: the end-to-end path on one app (W9).

capture base + head -> stories -> rules -> issues -> re-capture the affected personas -> verify -> policy
-> review.json. Every model call goes through the router with a spend cap; capture and rules are code.
"""

from __future__ import annotations

from pathlib import Path

from semaudit.capture import Runner
from semaudit.contract.approve import approval_state
from semaudit.contract.schema import load_contract
from semaudit.decide import memory as mem
from semaudit.decide.issues import apply_delta, build_issues
from semaudit.decide.pipeline import evaluate_release
from semaudit.models.router import Router
from semaudit.report import manifest as mf
from semaudit.report.review import assemble, write
from semaudit.story.build import story_from_episode
from semaudit.verify.steps import verify


def run_review(contract_dir: Path, base: str, head: str, *, run_id: str, runs_dir: Path, max_usd: float,
               reuse: bool = False, fresh: bool = False, models: bool = True, root: Path | None = None,
               ablation: str | None = None) -> Path:
    """`ablation` (benchmark only, never a product mode): "no-exceptions" drops every rule's exceptions,
    "no-verifier" reports candidates without verification, "no-generators" replaces the code generators with a
    model-only candidate pass. The review is written beside the normal one, named for the ablation."""
    recorded = mem.snapshot(contract_dir)
    contract = load_contract(contract_dir, memory=recorded["issues"])
    router = Router(root=root or Path.cwd(), max_usd=max_usd)
    router.tag = f"{('ablation-' + ablation) if ablation else 'semaudit-full'}:{base}-{head}:{run_id}"
    generator = None
    if ablation == "no-exceptions":
        for r in contract.rules:
            r.exceptions = []
    elif ablation == "no-generators":
        from semaudit.bench.ablate import model_generator
        generator = model_generator(contract, router, fresh=fresh)
    elif ablation not in (None, "no-verifier"):
        raise ValueError(f"unknown ablation {ablation!r}")
    run_dir = runs_dir / run_id
    if not (reuse and (run_dir / "episodes" / base).exists() and (run_dir / "episodes" / head).exists()):
        with Runner(contract_dir, runs_dir=runs_dir, run_id=run_id) as r:
            r.capture(base)
            r.capture(head)
    b = evaluate_release(run_dir, base, contract, router, fresh=fresh, generator=generator)
    h = evaluate_release(run_dir, head, contract, router, fresh=fresh, generator=generator)
    head_issues = build_issues(head, h.results, contract)
    base_issues = build_issues(base, b.results, contract)
    resolved, unconfirmed = apply_delta(head_issues, base_issues, set(b.results), set(h.results))
    applied = mem.apply(head_issues, resolved, unconfirmed, recorded["issues"], contract,
                        {p: s for p, (s, _) in h.results.items()})
    head_issues = [i for i in head_issues if all(i is not s for s in applied.set_aside)]

    affected = sorted({p for i in head_issues for p in i.personas}) if ablation != "no-verifier" else []
    repro = {}
    if affected:
        with Runner(contract_dir, runs_dir=runs_dir, run_id=f"{run_id}-repro") as r:
            for ep in r.capture(head, affected):
                repro[ep.persona] = story_from_episode(ep, contract)
    stories = {p: s for p, (s, _) in h.results.items()}
    for i in head_issues:
        if ablation == "no-verifier":
            i.verification = {"status": "unverified", "reason": "ablation: no verifier", "steps": {}}
            i.confidence = {"level": "low", "basis": ["ablation: no verifier"]}
            continue
        verify(i, stories, h.episodes, run_dir, contract, router, repro=repro, fresh=fresh, models=models)
    out = run_dir / (f"review-{base}-{head}.{ablation}.json" if ablation else f"review-{base}-{head}.json")
    manifest = mf.build(contract_dir, contract, run_dir, base, head, router=router, models=models, max_usd=max_usd,
                        repro_run=f"{run_id}-repro" if affected else None, memory=recorded)
    manifest["ablation"] = ablation
    if generator is not None:
        manifest["ablation_dropped"] = generator.dropped     # model proposals not tied to the story's events
    review = assemble(b, h, contract, head_issues, resolved, router.spent_usd,
                      approval=approval_state(contract_dir, contract), unconfirmed=unconfirmed,
                      manifest=manifest, review_path=str(out), set_aside=applied.set_aside)
    return write(review, out)
