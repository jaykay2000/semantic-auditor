"""Input ablation of B-judge-1 (bench/conditions/INPUT-ABLATION.md): the same single call with the auditor's
inputs removed one at a time. Benchmark only, never a product mode.

  V1 no-method    the judging method is removed from the prompt (prompts/inputs/judge_bare.md)
  V2 no-oracle    also: the oracle readings and the story's static truth
  V3 plain-rules  also: the structured contract -> rule text + one generated sentence per exception

Everything else is B-judge-1's: the interpreter role at its settings, one call, the normalized output schema,
the same validation (findings that do not fit are dropped and counted, never repaired).
"""

from __future__ import annotations

from typing import Any

from semaudit.contract.schema import Contract
from semaudit.models.router import Router
from semaudit.story.model import Story

from . import judge
from .findings import Findings

VARIANTS = ("no-method", "no-oracle", "plain-rules")


def plain_exception(ex) -> str:
    """One sentence an owner could have written, generated mechanically from the exception's own fields."""
    parts = []
    for c in ex.conditions:
        if c.kind == "judged":
            parts.append(f"the message {c.field.replace('_', ' ')}")
        elif c.test == "time_until":
            parts.append(f"the persona's {c.context_field.replace('_', ' ')} is at most {c.hours:g} hours after "
                         f"the message")
        elif c.test == "claim_matches_oracle":
            parts.append(f"the message's {c.claim.replace('_', ' ')} claim is true")
        else:
            parts.append(f"{c.test or c.field or c.id} holds")
    scope = "; ".join(f"{k}: {', '.join(v)}" for k, v in sorted(ex.scope.items()))
    s = f"Exception {ex.id}: allowed only when ALL of these hold: " + "; ".join(parts) + "."
    if scope:
        s += f" It covers only {scope}."
    if ex.approved.get("expires"):
        s += f" It expires after {ex.approved['expires']}."
    return s


def plain_contract(c: Contract) -> dict[str, Any]:
    rules = [{"id": r.id, "kind": r.kind, "title": r.title, "text": r.text, "severity": r.severity,
              **({"severity_by_label": r.severity_by_label} if r.severity_by_label else {}),
              **({"exceptions": [plain_exception(x) for x in r.exceptions]} if r.exceptions else {})}
             for r in c.rules]
    # `kind` stays: the output format needs it (coherence -> relation target, load -> story target)
    return {"rules": rules, "features": [f.id for f in c.features],
            "decisions": [{"id": d.id, "actions": list(d.actions)} for d in c.decisions],
            "surfaces": [s.id for s in c.surfaces]}


def story_without_oracle(s: Story) -> dict[str, Any]:
    out = judge.render_story(s)
    out.pop("truth", None)
    out.pop("oracle_readings", None)
    return out


def payload(variant: str, stories: dict[str, Story], contract: Contract, release: str) -> dict[str, Any]:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}; known: {VARIANTS}")
    render = judge.render_story if variant == "no-method" else story_without_oracle
    con = judge.render_contract(contract) if variant != "plain-rules" else plain_contract(contract)
    return {"release": release, "contract": con, "stories": [render(s) for _, s in sorted(stories.items())]}


def judge_variant(variant: str, stories: dict[str, Story], contract: Contract, router: Router, *, release: str,
                  fresh: bool = True, run: str = "1") -> tuple[Findings, list[str]]:
    tally = judge.Tally()
    router.tag = f"B-judge-1/{variant}:{release}:{run}"
    system = (judge.CONDITIONS / "prompts" / "inputs" / "judge_bare.md").read_text()
    items = judge._call(router, system, payload(variant, stories, contract, release), fresh=fresh, tally=tally)
    return judge._validated(f"B-judge-1/{variant}", release, run, items, tally)
