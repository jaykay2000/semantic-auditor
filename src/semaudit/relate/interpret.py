"""Model side of the relation layer: label a P2 candidate against the owner's rule.

The model sees the whole story in time order, the candidate pair(s) with each message's
recommended action, the pair type from the contract and the coherence rule. It returns a
label and, if it claims the pair was reconciled, which message did so and which of the
pair's actions that message addresses; code then checks the timing and that the message
addresses BOTH actions of a candidate pair (see rules.reconciler_addresses_pair).
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
    "required": ["label", "reconciling_event_id", "addresses_actions", "rationale"],
    "properties": {
        "label": {"type": "string", "enum": ["conflict", "unexplained_tradeoff", "explained_tradeoff", "compatible"]},
        "reconciling_event_id": {"type": "string"},
        "addresses_actions": {"type": "array", "items": {"type": "string"}},
        "rationale": {"type": "string"},
    },
}

INSTRUCTIONS = """You judge one candidate under the product owner's coherence rule.
Labels:
- conflict: the two recommendations are INCOMPATIBLE actions and no message reconciles them for the user.
- unexplained_tradeoff: the actions are COMPATIBLE but have a material tradeoff, and no message explains it.
- explained_tradeoff: some message shown to the user resolves THIS pair: it refers to EACH of the pair's two
  recommended actions (the "action" of each candidate message) and tells the user how to choose between them
  for their situation, shown while both were live and before the user decided. For an INCOMPATIBLE pair it
  must tell the user which of the two to follow, or explicitly withdraw one. Give that message's id in
  reconciling_event_id, and in addresses_actions list which of the pair's actions it addresses.
- compatible: there is no material tradeoff for this user.
A message that explains a DIFFERENT pair of options, or only one side of this pair, does not reconcile it
(e.g. a message weighing "wait" against "reserve" does not reconcile "wait" against "buy now"). A message that
explains only its OWN tradeoff (e.g. "buy now, or reserve it if your plans might change") does NOT reconcile
another feature's advice. Use the pair type given; do not reclassify incompatible as tradeoff.
Use "" for reconciling_event_id and [] for addresses_actions when no message reconciles them.
Judge only from the story given."""


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
            "candidate_pairs": [[{"id": e.id, "feature": e.feature, "action": e.extraction.action, "text": e.text}
                                 for e in p] for p in pairs],
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
        return {"label": label, "reconciling_event_id": None, "addresses_actions": [], "rationale": f"stub:{label}"}
    return interpret
