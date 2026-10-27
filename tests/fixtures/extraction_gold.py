"""Hand-authored gold extraction for every Northbound message key (W6 acceptance).

Authored from examples/northbound/README.md and contract/rubric.md, never from model output. Extends the
W1b gold (tests/fixtures/stories/build.py GOLD) to the core, 2.3 and alias keys that real captures contain.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "stories"))
from build import GOLD as STORY_GOLD  # noqa: E402

INFO = {"message_kind": "information", "decision": "none", "action": "none", "strength": "inform",
        "urgency_cue": "none", "explains_own_tradeoff": False, "claims": []}


def info(*claims):
    return {**INFO, "claims": list(claims)}


FEE30 = {"type": "fee_total", "value": 30, "unit": "EUR"}

BY_KEY = {
    **STORY_GOLD,
    # aliases: the same wording, sent by email
    "pw.email.forecast": STORY_GOLD["pw.card"],
    "pw.email.forecast.nodrop": STORY_GOLD["pw.card.nodrop"],
    # Price Watch 1.0 (2.3)
    "pw.card.optin": {"message_kind": "directive", "decision": "when_to_book", "action": "set_alert",
                      "strength": "suggest", "urgency_cue": "none", "explains_own_tradeoff": False, "claims": []},
    "pw.card.watching": info(),                         # a promise to notify is not a recommendation
    # Concierge answers and greeting
    "cg.greeting": info(),
    "cg.answer.when": info(),
    "cg.answer.deal.booked": info(),                    # states what was charged; a fare price is not a fee
    # core: facts about the booking; prices and totals are not fee claims
    "core.results": info(), "core.results.fare": info(), "core.fare.summary": info(),
    "core.checkout.fare": info(), "core.checkout.taxes": info(), "core.checkout.total": info(),
    "core.confirmed": info(), "core.confirmed.charge": info(), "core.confirmed.total": info(),
    "core.email.confirmation": info(), "core.hotel.summary": info(),
    "core.fare.policy.non_refundable": info(FEE30),     # a policy about after booking: information
    "core.confirmed.fare_window": {"message_kind": "directive", "decision": "fare_type",   # available now: an offer
                                   "action": "upgrade_to_refundable", "strength": "suggest", "urgency_cue": "none",
                                   "explains_own_tradeoff": False, "claims": [FEE30]},
}

# Where one key renders different numbers in different releases or for different parties.
BY_TEXT = {
    "Fare Lock (48 h): €9": {**STORY_GOLD["fl.checkout.lock"],
                             "claims": [{"type": "fee_total", "value": 9, "unit": "EUR"}]},
}

# Hero and boundary directives: W6 requires these to be exactly right, every time.
HERO = {"pw.card", "pw.email.forecast", "pw.email.after", "fl.banner", "fl.banner.urgent", "fl.banner.urgent_bare",
        "fl.hotel.urgent", "fl.checkout.lock", "cg.reconcile", "cg.regret", "cg.upgrade"}

FIELDS = ("message_kind", "decision", "action", "strength", "explains_own_tradeoff")


UNITS = re.compile(r"(\d+) (?:seats?|rooms?) left|has (\d+) seats?")


def gold_for(key: str, text: str) -> dict | None:
    """Gold for this rendering. Seat and room counts are taken from the text itself (they vary by persona)."""
    g = BY_TEXT.get(text) or BY_KEY.get(key)
    if g is None:
        return None
    m = UNITS.search(text)
    if m:
        n = int(m[1] or m[2])
        g = {**g, "claims": [{**c, "value": n} if c["type"] == "units_left" else c for c in g["claims"]]}
    return g
