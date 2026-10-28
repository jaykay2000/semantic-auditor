"""Extract what each message tells the user: kind, directive fields and claims.

One model call per story (all its messages batched), constrained to the contract's
vocabulary and rubric. The model sees raw text only; nothing is pre-labelled.
"""

from __future__ import annotations

import json

from semaudit.contract.schema import Contract
from semaudit.models.router import Router
from semaudit.story.model import Extraction, Story


def extraction_schema(contract: Contract, observed: set[str] = frozenset()) -> dict:
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
            "claims": {"type": "array", "items": _claim_schema(contract, observed)},
        },
    }
    return {"type": "object", "additionalProperties": False, "required": ["messages"],
            "properties": {"messages": {"type": "array", "items": item}}}


DATETIME = "datetime"      # a fact whose contract `unit` is this states a moment, not an amount


def temporal_facts(contract: Contract, observed: set[str] = frozenset()) -> set[str]:
    """Date/time facts: those the contract declares (unit: datetime) plus those whose MEASURED oracle values are
    dates/times (`observed`, from the captured stories). An owner who never declares a unit still gets a
    readable comparison, because the measurement decides, not the authoring."""
    return {f.id for f in contract.facts if f.unit == DATETIME} | (set(observed) & {f.id for f in contract.facts})


def observed_temporal(stories) -> set[str]:
    """Facts whose measured value is a date/time in any story (static truth or any oracle snapshot)."""
    from semaudit.relate.claims import is_temporal
    out = set()
    for s in stories:
        for name, v in list(s.truth.items()) + [kv for snap in s.snapshots for kv in snap["truth"].items()]:
            if is_temporal(v):
                out.add(name.split("@", 1)[0])
    return out


def _claim_schema(contract: Contract, observed: set[str] = frozenset()) -> dict:
    """An amount claim is a number. When any fact is a date/time (declared, or measured as one) claims also get
    `when`, so they can carry a moment. Otherwise the original schema, unchanged, so extractions and cached
    answers for such contracts are not disturbed."""
    props = {"type": {"type": "string", "enum": [f.id for f in contract.facts] or ["none"]},
             "value": {"type": "number"}, "unit": {"type": "string"}}
    if not temporal_facts(contract, observed):
        return {"type": "object", "additionalProperties": False, "required": ["type", "value", "unit"],
                "properties": props}
    props.update(value={"type": ["number", "null"]}, when={"type": ["string", "null"]})
    return {"type": "object", "additionalProperties": False, "required": ["type", "value", "unit", "when"],
            "properties": props}


PROMPT = "Classify every message below independently, using the rubric. Return one entry per id.\n"

DATETIME_PROMPT = ("Claims: a claim that states an amount or count goes in `value` (with its `unit`), and `when` "
                   "is null. A claim that states a date or time goes in `when` as ISO 8601, exactly as precise as the message "
                   "(YYYY-MM-DD for a date only, YYYY-MM-DDTHH:MM for a date and time, with a UTC offset only if the "
                   "message gives a time zone), and `value` is null. If the message gives a time but not its date, or "
                   "a relative time (\"tomorrow\", \"in 2 hours\"), set `when` null: it cannot be read on its own.\n")


def _prompt(contract: Contract, observed: set[str] = frozenset()) -> str:
    return PROMPT + (DATETIME_PROMPT if temporal_facts(contract, observed) else "")


def normalize(x: Extraction, contract: Contract) -> Extraction:
    """Code over model where the contract decides: an action that belongs to exactly one decision implies
    that decision. A contradicting model decision is overruled and recorded (never silently kept)."""
    owners = [d.id for d in contract.decisions if x.action in d.actions]
    if len(owners) == 1 and x.decision != owners[0]:
        return x.model_copy(update={"decision": owners[0], "normalized": f"decision {x.decision} -> {owners[0]}"})
    return x


def extract_story(story: Story, contract: Contract, router: Router, *, fresh: bool = False,
                  role: str = "extractor") -> dict[str, Extraction]:
    observed = observed_temporal([story])
    msgs = story.messages()
    listing = [{"id": m.id, "feature": m.feature, "channel": m.channel, "text": m.text} for m in msgs]
    prompt = (_prompt(contract, observed) + json.dumps(listing, ensure_ascii=False, indent=1))
    r = router.complete(role, [{"role": "system", "content": contract.rubric},
                               {"role": "user", "content": prompt}],
                        schema=extraction_schema(contract, observed), schema_name="extraction", fresh=fresh)
    out = {row["id"]: normalize(Extraction(**{k: v for k, v in row.items() if k != "id"}), contract)
           for row in r.parsed["messages"]}
    missing = {m.id for m in msgs} - set(out)
    if missing:
        raise ValueError(f"extraction missing ids: {sorted(missing)}")
    return out


def extract_unique(messages: list[dict], contract: Contract, router: Router, *, fresh: bool = False,
                   role: str = "extractor", batch: int = 25,
                   observed: set[str] = frozenset()) -> dict[tuple[str, str, str], Extraction]:
    """Extract each distinct (feature, channel, text) once, in batches. Identical text gets an identical answer.

    The rubric classifies every message independently, so a message's extraction never depends on which
    story it appears in; deduplicating across stories is the same task at a fraction of the cost.
    """
    uniq = sorted({(m["feature"] or "", m["channel"] or "", m["text"]) for m in messages})
    out: dict[tuple[str, str, str], Extraction] = {}
    for i in range(0, len(uniq), batch):
        chunk = uniq[i:i + batch]
        listing = [{"id": f"m{j}", "feature": f, "channel": c, "text": t} for j, (f, c, t) in enumerate(chunk)]
        prompt = (_prompt(contract, observed) + json.dumps(listing, ensure_ascii=False, indent=1))
        r = router.complete(role, [{"role": "system", "content": contract.rubric},
                                   {"role": "user", "content": prompt}],
                            schema=extraction_schema(contract, observed), schema_name="extraction", fresh=fresh)
        rows = {row["id"]: row for row in r.parsed["messages"]}
        missing = [x["id"] for x in listing if x["id"] not in rows]
        if missing:
            raise ValueError(f"extraction missing ids: {missing}")
        for x, key in zip(listing, chunk):
            out[key] = normalize(Extraction(**{k: v for k, v in rows[x["id"]].items() if k != "id"}), contract)
    return out
