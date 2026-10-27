"""Model side of the relation layer: label a P2 candidate against the owner's rule.

The model sees the whole story in time order, the candidate pair(s), the pair type
from the contract and the coherence rule. It returns a label and, if it claims the
tradeoff was explained, which message did so; code then checks that message's timing.
"""

from __future__ import annotations

import json
import random

from semaudit.contract.schema import Contract
from semaudit.models.router import Router
from semaudit.relate.rules import PairCandidate
from semaudit.story.model import Story

LABEL_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["label", "reconciling_event_id", "rationale"],
    "properties": {
        "label": {"type": "string", "enum": ["conflict", "unexplained_tradeoff", "explained_tradeoff", "compatible"]},
        "reconciling_event_id": {"type": "string"},
        "rationale": {"type": "string"},
    },
}

INSTRUCTIONS = """You judge one candidate under the product owner's coherence rule.
Labels:
- conflict: the two recommendations are INCOMPATIBLE actions and no message reconciles them for the user.
- unexplained_tradeoff: the actions are COMPATIBLE but have a material tradeoff, and no message explains it.
- explained_tradeoff: some message shown to the user addresses BOTH recommendations and helps the user weigh
  them (for example by saying which applies in which situation), shown while both were live and before the
  user decided. Give that message's id in reconciling_event_id.
- compatible: there is no material tradeoff for this user.
A message that explains only its OWN tradeoff (e.g. "buy now, or reserve it if your plans might change") does
NOT reconcile another feature's advice. Use the pair type given; do not reclassify incompatible as tradeoff.
Use "" for reconciling_event_id when no message reconciles them. Judge only from the story given."""


def story_view(story: Story) -> list[dict]:
    rows = []
    for e in sorted(story.events, key=lambda e: e.at):
        row = {"id": e.id, "at": e.at.isoformat(), "kind": e.kind}
        if e.kind == "message":
            row.update(feature=e.feature, channel=e.channel, text=e.text)
        else:
            row.update(user_action=e.action)
        rows.append(row)
    return rows


def model_interpreter(router: Router, *, fresh: bool = False, rng: random.Random | None = None,
                      role: str = "interpreter"):
    rng = rng or random.Random(0)

    def interpret(story: Story, cand: PairCandidate, contract: Contract) -> dict:
        pairs = [list(p) for p in cand.pairs]
        for p in pairs:
            rng.shuffle(p)                     # A/B order must not matter
        rng.shuffle(pairs)
        payload = {
            "rule": contract.rule(cand.rule).text,
            "decision": cand.decision,
            "pair_type": cand.pair_kind,
            "what_is_at_stake": cand.material,
            "candidate_pairs": [[{"id": e.id, "feature": e.feature, "text": e.text} for e in p] for p in pairs],
            "persona": story.persona,
            "story_in_time_order": story_view(story),
        }
        r = router.complete(role, [{"role": "system", "content": INSTRUCTIONS},
                                   {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=1)}],
                            schema=LABEL_SCHEMA, schema_name="p2_label", fresh=fresh)
        out = dict(r.parsed)
        out["reconciling_event_id"] = out["reconciling_event_id"] or None
        return out

    return interpret


def stub_always(label: str):
    """Falsifiability control: an interpreter that ignores the story. W1b must fail with it."""
    def interpret(story, cand, contract):
        return {"label": label, "reconciling_event_id": None, "rationale": f"stub:{label}"}
    return interpret
