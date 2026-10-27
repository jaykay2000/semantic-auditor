"""E2 baselines: the same model judging the auditor's OWN captured stories (docs/08-evaluation.md).

B-judge-1  one long-context call: every story, the owner's rules with their exceptions, the contract.
B-judge-N  budget-matched multi-pass: one pass per persona, a self-critique pass, a consolidation pass.

Fairness, as the protocol states it:
  * same model family and version as the auditor's interpreter (the `interpreter` role's model);
  * same information: the parsed contract (never raw YAML, whose comments are authoring notes, and never a
    persona's `role`, which the auditor does not judge with) and every captured event with its oracle readings;
  * never the auditor's own judgement: no extraction, no labels, no candidates;
  * output in the normalized findings format, so scoring is identical and needs no free-text normalizer.

The prompts live in bench/conditions/ and are frozen (hashed) before any benchmark run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from semaudit.contract.schema import Contract
from semaudit.decide.pipeline import measurement_problems
from semaudit.models.router import Router
from semaudit.story.build import story_from_episode
from semaudit.story.episode import Episode
from semaudit.story.model import Story

from .findings import Findings

CONDITIONS = Path(__file__).resolve().parents[3] / "bench" / "conditions"
ROLE = "interpreter"            # the baseline runs on the auditor's interpreter model, at its settings


def stories_for(run_dir: Path, release: str, contract: Contract) -> dict[str, Story]:
    """The auditor's own captures for one release, as stories, minus anything not measured."""
    out = {}
    for p in sorted((run_dir / "episodes" / release).glob("*.json")):
        ep = Episode.read(p)
        if not measurement_problems(ep):
            out[ep.persona] = story_from_episode(ep, contract)
    return out


def render_story(s: Story) -> dict[str, Any]:
    events = []
    for e in s.events:
        row: dict[str, Any] = {"id": e.id, "at": e.at.isoformat(), "kind": e.kind}
        if e.kind == "user_action":
            row.update(action=e.action, **({"effects": e.effects} if e.effects else {}))
        else:
            row.update(feature=e.feature, surface=e.surface, channel=e.channel, component=e.component,
                       message_key=e.copy_key, user_initiated=e.user_initiated, text=e.text)
        events.append(row)
    return {"persona": s.persona, "context": s.context, "truth": s.truth,
            "oracle_readings": s.snapshots, "events": events}


def render_contract(c: Contract) -> dict[str, Any]:
    dump = lambda xs: [x.model_dump(mode="json", exclude={"source"}) for x in xs]  # noqa: E731
    return {"subject": c.subject.model_dump(mode="json"), "rules": dump(c.rules), "decisions": dump(c.decisions),
            "features": dump(c.features), "surfaces": dump(c.surfaces), "facts": dump(c.facts),
            "state": dump(c.state), "rubric": c.rubric if isinstance(c.rubric, str) else str(c.rubric)}


def _schema() -> dict:
    target = {"type": "object", "additionalProperties": False,
              "required": ["kind", "features", "decision", "feature", "surface", "message_key"],
              "properties": {"kind": {"type": "string", "enum": ["relation", "event", "story"]},
                             "features": {"type": "array", "items": {"type": "string"}},
                             "decision": {"type": ["string", "null"]}, "feature": {"type": ["string", "null"]},
                             "surface": {"type": ["string", "null"]}, "message_key": {"type": ["string", "null"]}}}
    cited = {"type": "object", "additionalProperties": False, "required": ["persona", "event_id", "quote"],
             "properties": {"persona": {"type": "string"}, "event_id": {"type": "string"},
                            "quote": {"type": "string"}}}
    finding = {"type": "object", "additionalProperties": False,
               "required": ["personas", "rule", "label", "target", "severity", "confidence", "why", "cited"],
               "properties": {"personas": {"type": "array", "items": {"type": "string"}}, "rule": {"type": "string"},
                              "label": {"type": ["string", "null"],
                                        "enum": ["conflict", "unexplained_tradeoff", None]},
                              "target": target,
                              "severity": {"type": "string", "enum": ["minor", "major", "critical"]},
                              "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                              "why": {"type": "string"}, "cited": {"type": "array", "items": cited}}}
    return {"type": "object", "additionalProperties": False, "required": ["findings"],
            "properties": {"findings": {"type": "array", "items": finding}}}


SCHEMA = _schema()


def prompt(name: str) -> str:
    d = CONDITIONS / "prompts"
    return (d / f"{name}.md").read_text().replace("{{COMMON}}", (d / "_common.md").read_text().strip())


def _to_findings(items: list[dict], prefix: str) -> list[dict]:
    out = []
    for n, f in enumerate(items, 1):
        t = dict(f["target"])
        t = {k: v for k, v in t.items() if v not in (None, [])}
        out.append({**f, "id": f"{prefix}-{n:03d}", "target": t})
    return out


def _call(router: Router, system: str, payload: dict, *, fresh: bool) -> tuple[list[dict], float]:
    r = router.complete(ROLE, [{"role": "system", "content": system},
                               {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)}],
                        schema=SCHEMA, schema_name="findings", fresh=fresh)
    return r.parsed["findings"], (r.cost_usd or 0.0)


def judge_one(stories: dict[str, Story], contract: Contract, router: Router, *, release: str,
              fresh: bool = False, run: str = "1") -> tuple[Findings, list[str]]:
    payload = {"release": release, "contract": render_contract(contract),
               "stories": [render_story(s) for _, s in sorted(stories.items())]}
    items, cost = _call(router, prompt("judge_one"), payload, fresh=fresh)
    return _validated("B-judge-1", release, run, items, cost, 1)


def judge_multi(stories: dict[str, Story], contract: Contract, router: Router, *, release: str,
                fresh: bool = False, run: str = "1") -> tuple[Findings, list[str]]:
    """Per-persona passes, then self-critique over all candidates, then consolidation. Every pass sees the full
    contract; the critique and consolidation passes also see every story, so nothing is judged blind."""
    con, all_stories = render_contract(contract), [render_story(s) for _, s in sorted(stories.items())]
    candidates, cost, calls = [], 0.0, 0
    for persona, s in sorted(stories.items()):
        items, c = _call(router, prompt("judge_persona"),
                         {"release": release, "contract": con, "story": render_story(s)}, fresh=fresh)
        candidates += items
        cost, calls = cost + c, calls + 1
    kept, c = _call(router, prompt("judge_critique"),
                    {"release": release, "contract": con, "stories": all_stories, "candidates": candidates},
                    fresh=fresh)
    final, c2 = _call(router, prompt("judge_consolidate"),
                      {"release": release, "contract": con, "findings": kept}, fresh=fresh)
    return _validated("B-judge-N", release, run, final, cost + c + c2, calls + 2)


def _validated(system: str, release: str, run: str, items: list[dict], cost: float,
               calls: int) -> tuple[Findings, list[str]]:
    """Findings that do not fit the format are dropped and listed, never repaired: repairing a baseline's
    output by hand would be the scorer judging on its behalf."""
    from pydantic import ValidationError

    from .findings import Finding
    ok, dropped = [], []
    for f in _to_findings(items, system):
        try:
            ok.append(Finding.model_validate(f))
        except ValidationError as e:
            dropped.append(f"{f['id']}: {e.errors()[0]['msg']}")
    return Findings(system=system, release=release, run=run, findings=ok, cost_usd=round(cost, 6),
                    calls=calls), dropped
