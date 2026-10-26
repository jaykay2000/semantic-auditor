"""Extract what each message tells the user: kind, directive fields and claims.

One model call per story (all its messages batched), constrained to the contract's
vocabulary and rubric. The model sees raw text only; nothing is pre-labelled.
"""

from __future__ import annotations

import json

from semaudit.contract.schema import Contract
from semaudit.models.router import Router
from semaudit.story.model import Extraction, Story


def extraction_schema(contract: Contract) -> dict:
    decisions = sorted({d.id for d in contract.decisions} | {"none"})
    actions = sorted(set(contract.actions()) | {"none", "other"})
    item = {
        "type": "object", "additionalProperties": False,
        "required": ["id", "message_kind", "decision", "action", "strength", "urgency_cue",
                     "explains_own_tradeoff", "claims"],
        "properties": {
            "id": {"type": "string"},
            "message_kind": {"type": "string", "enum": ["information", "directive", "retrospective"]},
            "decision": {"type": "string", "enum": decisions},
            "action": {"type": "string", "enum": actions},
            "strength": {"type": "string", "enum": ["inform", "suggest", "urge", "require"]},
            "urgency_cue": {"type": "string", "enum": ["U-a", "U-b", "U-c", "none"]},
            "explains_own_tradeoff": {"type": "boolean"},
            "claims": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["type", "value", "unit"],
                "properties": {"type": {"type": "string", "enum": ["units_left", "fee_total", "fee_per_traveller"]},
                               "value": {"type": "number"}, "unit": {"type": "string"}}}},
        },
    }
    return {"type": "object", "additionalProperties": False, "required": ["messages"],
            "properties": {"messages": {"type": "array", "items": item}}}


def extract_story(story: Story, contract: Contract, router: Router, *, fresh: bool = False,
                  role: str = "extractor") -> dict[str, Extraction]:
    msgs = story.messages()
    listing = [{"id": m.id, "feature": m.feature, "channel": m.channel, "text": m.text} for m in msgs]
    prompt = ("Classify every message below independently, using the rubric. Return one entry per id.\n"
              + json.dumps(listing, ensure_ascii=False, indent=1))
    r = router.complete(role, [{"role": "system", "content": contract.rubric},
                               {"role": "user", "content": prompt}],
                        schema=extraction_schema(contract), schema_name="extraction", fresh=fresh)
    out = {row["id"]: Extraction(**{k: v for k, v in row.items() if k != "id"}) for row in r.parsed["messages"]}
    missing = {m.id for m in msgs} - set(out)
    if missing:
        raise ValueError(f"extraction missing ids: {sorted(missing)}")
    return out
