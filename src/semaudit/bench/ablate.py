"""The no-generators ablation: the auditor with its code candidate generators and rule evaluation replaced by a
model-only pass over each story (docs/08-evaluation.md, "Ablations").

Everything else is the auditor's: extraction, issue grouping, the delta against the base release, and the full
verifier. The model pass uses the published per-persona baseline prompt (bench/conditions/prompts), on the
interpreter's model and settings, so the only thing removed is the code that proposes and evaluates candidates.
A proposal that cannot be tied to the story's own events is dropped and counted, never repaired.
"""

from __future__ import annotations

import json

from semaudit.contract.schema import Contract
from semaudit.models.router import Router
from semaudit.relate.rules import Entry
from semaudit.story.model import Story

from . import judge

PAIR_KIND = {"conflict": "incompatible", "unexplained_tradeoff": "tradeoff"}


def entries_from(findings: list[dict], story: Story) -> tuple[list[Entry], list[str]]:
    by_id = {e.id: e for e in story.events}
    msgs = [e for e in story.events if e.kind == "message"]
    out, dropped = [], []
    for n, f in enumerate(findings):
        if story.persona not in f["personas"]:
            continue
        t = f["target"]
        cited = [c["event_id"] for c in f.get("cited", []) if c["persona"] == story.persona and c["event_id"] in by_id]
        if t["kind"] == "event":
            hit = next((e for e in msgs if (e.feature, e.surface, e.copy_key) ==
                        (t.get("feature"), t.get("surface"), t.get("message_key"))), None)
            if hit is None:
                dropped.append(f"{n}: no {t.get('message_key')} on {t.get('surface')} in {story.persona}'s story")
                continue
            out.append(Entry(f["rule"], hit.id, "violated", meta={"events": [hit.id]}))
        elif t["kind"] == "relation":
            feats, label = sorted(t.get("features") or []), f.get("label")
            sides = [[e.id for e in msgs if e.feature == x and e.id in cited] for x in feats]
            if len(feats) != 2 or label not in PAIR_KIND or not all(sides):
                dropped.append(f"{n}: relation {feats} {label} not tied to cited messages of both features")
                continue
            subject = f"{feats[0]}|{feats[1]}@{t.get('decision')}:{PAIR_KIND[label]}"
            out.append(Entry(f["rule"], subject, "violated", label=label,
                             meta={"pairs": [[a, b] for a in sides[0] for b in sides[1]]}))
        else:
            out.append(Entry(f["rule"], "story", "violated", meta={"events": cited or [m.id for m in msgs]}))
    return out, dropped


def model_generator(contract: Contract, router: Router, *, fresh: bool = False):
    con = judge.render_contract(contract)
    system = judge.prompt("judge_persona")
    log: dict[str, list[str]] = {}

    def generate(story: Story) -> list[Entry]:
        r = router.complete(judge.ROLE, [{"role": "system", "content": system},
                                         {"role": "user", "content": json.dumps(
                                             {"release": story.release, "contract": con,
                                              "story": judge.render_story(story)}, ensure_ascii=False,
                                             default=str)}],
                            schema=judge.SCHEMA, schema_name="findings", fresh=fresh)
        entries, dropped = entries_from((r.parsed or {}).get("findings", []), story)
        log[f"{story.release}/{story.persona}"] = dropped
        return entries

    generate.dropped = log
    return generate
