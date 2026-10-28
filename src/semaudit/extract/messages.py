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
    required = ["type", "value", "unit"]
    if temporal_facts(contract, observed):
        props.update(value={"type": ["number", "null"]}, when={"type": ["string", "null"]})
        required.append("when")
    if displayed_facts(contract):
        props["precision"] = {"type": ["number", "null"]}
        required.append("precision")
    if word_facts(contract):
        props["value"] = {"type": ["number", "null"]}
        props["word"] = {"type": ["string", "null"],
                         "enum": sorted({w for f in contract.facts for w in f.words} | {"unknown"}) + [None]}
        required.append("word")
    if contract_roles(contract):
        props["role"] = {"type": ["string", "null"], "enum": list(ROLES) + [None]}
        required.append("role")
    for name, values in key_fields(contract).items():
        props[name] = ({"type": ["string", "null"], "enum": sorted(values | {"unknown"}) + [None]} if values
                       else {"type": ["string", "null"]})
        required.append(name)
    return {"type": "object", "additionalProperties": False, "required": required, "properties": props}


ROLES = ("as_is", "proposed", "change", "limit")


def word_facts(contract) -> list:
    return [f for f in contract.facts if f.words]


def word_prompt(contract) -> str:
    facts = word_facts(contract)
    if not facts:
        return ""
    return ("Claims: some facts state a word, not an amount. For a claim of one of these, put the word in `word` "
            "and set `value` null ('unknown' when the message does not say which); for every other claim set "
            "`word` null.\n" + "".join(f"- {f.id}: one of {', '.join(f.words)}\n" for f in facts))


def contract_roles(contract) -> bool:
    app = getattr(contract, "app", None)
    return bool(getattr(app, "claim_roles", False))


ROLE_PROMPT = ("Claims: `role` says what the figure is. 'as_is': the user's figure as it stands now, or a result the "
               "product states about them now (their balance, rate, score, date today). 'proposed': a figure they "
               "would have or should reach if they act or if something changes (a target, a what-if, a projection "
               "under a change: \"bring your balance to $3,000\", \"you would finish in 2031\"). 'change': the size "
               "of a change or a gap, including room left below a cap (\"$150/mo more\", \"save $900 a year\", "
               "\"two years sooner\", \"$800 of room left this year\"). 'limit': a cap or allowance itself "
               "(\"a credit limit of $5,000\", \"the most you can put in is $6,000\"). A message's `around` text "
               "is only there to read a short block: never take claims from it.\n")


def key_fields(contract: Contract) -> dict[str, set[str]]:
    """Every key field a family fact declares -> the values allowed for it (union over facts; empty: free text).
    A field free in any fact is free everywhere, so no fact's values are refused."""
    values: dict[str, set[str]] = {}
    free: set[str] = set()
    for k in (k for f in contract.facts for k in f.key):
        values.setdefault(k.field, set()).update(k.values)
        if not k.values:
            free.add(k.field)
    return {n: (set() if n in free else v) for n, v in values.items()}


def displayed_facts(contract: Contract) -> set[str]:
    """Facts the contract matches at the precision the message shows (`match: displayed`)."""
    return {f.id for f in contract.facts if f.match == "displayed"}


PROMPT = "Classify every message below independently, using the rubric. Return one entry per id.\n"

DATETIME_PROMPT = ("Claims: a claim that states an amount or count goes in `value` (with its `unit`), and `when` "
                   "is null. A claim that states a date or time goes in `when` as ISO 8601, exactly as precise as the message "
                   "(YYYY-MM-DD for a date only, YYYY-MM-DDTHH:MM for a date and time, with a UTC offset only if the "
                   "message gives a time zone), and `value` is null. If the message gives a time but not its date, or "
                   "a relative time (\"tomorrow\", \"in 2 hours\"), set `when` null: it cannot be read on its own.\n")


PRECISION_PROMPT = ("Claims: `precision` is the size of the last digit the message shows for the value, so a rounded "
                    "figure can be checked at the precision it was shown: \"$1.2M\" -> value 1200000, precision 100000; "
                    "\"$250K\" -> 250000, 1000; \"$1,184,000\" -> 1184000, 1; \"15.6 months\" -> 15.6, 0.1; \"age 52\" -> "
                    "52, 1; \"22%\" -> 22, 1. Use null when the claim has no value.\n")


def key_prompt(contract: Contract) -> str:
    keyed = [f for f in contract.facts if f.key]
    if not keyed:
        return ""
    lines = ["Claims: some facts are families of different quantities. For a claim of one of these facts, also set "
             "the fields below to say which quantity it is ('unknown' when the message does not say); for any other "
             "claim, set them null."]
    for f in keyed:
        parts = [f"`{k.field}` ({k.describe + ': ' if k.describe else ''}"
                 f"{'one of ' + ', '.join(k.values) if k.values else 'short text'})" for k in f.key]
        lines.append(f"- {f.id}: " + "; ".join(parts))
    return "\n".join(lines) + "\n"


def _prompt(contract: Contract, observed: set[str] = frozenset()) -> str:
    return (PROMPT + (DATETIME_PROMPT if temporal_facts(contract, observed) else "")
            + (PRECISION_PROMPT if displayed_facts(contract) else "") + key_prompt(contract)
            + (ROLE_PROMPT if contract_roles(contract) else "") + word_prompt(contract))


def message_key(m) -> tuple:
    """The extraction cache key of a message (an Event or a listing dict): identical text in an identical reading
    context gets an identical answer."""
    g = (lambda k: m.get(k)) if isinstance(m, dict) else (lambda k: getattr(m, k))
    return (g("feature") or "", g("channel") or "", g("text"), g("around") or "")


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
    listing = [{"id": m.id, "feature": m.feature, "channel": m.channel, "text": m.text,
                **({"around": m.around} if m.around else {})} for m in msgs]
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
    uniq = sorted({message_key(m) for m in messages})
    out: dict[tuple[str, str, str, str], Extraction] = {}
    for i in range(0, len(uniq), batch):
        chunk = uniq[i:i + batch]
        listing = [{"id": f"m{j}", "feature": f, "channel": c, "text": t, **({"around": a} if a else {})}
                   for j, (f, c, t, a) in enumerate(chunk)]
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
