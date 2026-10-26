"""concierge: Concierge 1.0. Answers questions in a chat with deterministic templates. Never proactive.

No LLM, no randomness: the first matching keyword rule wins. Setting `proactive` must stay False here; a
release that wants proactive tips replaces this module.
"""
from __future__ import annotations

import re

from ..catalogue import money
from . import BaseFeature

# (answer key, keywords) in priority order
RULES = [
    ("deal", ["deal", "cheap", "good price"]),
    ("when", ["when to book", "book now", "or wait", "should i wait"]),
    ("refund", ["refund", "cancel", "change", "switch", "refundable"]),
    ("price_watch", ["price watch", "alert", "forecast", "drop"]),
    ("status", ["booking", "booked", "status", "confirmation"]),
]


class Feature(BaseFeature):
    id = "concierge"
    DEFAULTS = {"proactive": False}

    def __init__(self, settings=None):
        super().__init__(settings)
        if self.settings["proactive"]:
            raise ValueError("Concierge 1.0 is never proactive")

    def messages_for(self, surface, ctx):
        if surface == "chat":
            return [self.msg(ctx, "cg.greeting", surface, "chat")]
        return []

    @staticmethod
    def classify(question: str) -> str:
        q = re.sub(r"\s+", " ", question.lower())
        return next((name for name, words in RULES if any(w in q for w in words)), "fallback")

    def concierge_reply(self, question, ctx):
        topic, b = self.classify(question), ctx.booking
        if topic == "deal":
            return self.msg(ctx, "cg.answer.deal.booked" if b else "cg.answer.deal.none", "chat", "chat",
                            total=money(b.total_cents) if b else "")
        if topic == "status":
            if b is None:
                return self.msg(ctx, "cg.answer.status.none", "chat", "chat")
            return self.msg(ctx, "cg.answer.status.booked", "chat", "chat", booking_id=b.id,
                            **ctx.common_params())
        key = {"when": "cg.answer.when", "refund": "cg.answer.refund", "price_watch": "cg.answer.price_watch",
               "fallback": "cg.answer.fallback"}[topic]
        return self.msg(ctx, key, "chat", "chat")
