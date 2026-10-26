"""concierge (2.0): the same feature id; answers questions AND speaks first.

Proactive tips (setting `proactive`): after a non-refundable booking, `upgrade_tip_delay` later, if the change
window is still open and the traveller has not already switched, the concierge posts `cg.upgrade` in the chat
(in-app only: never an email or push). The default delay is 2h54m so the tip for a 10:06 booking lands at 13:00.

Answer templates (extends Concierge 1.0's keyword rules; everything else is answered by the 1.0 code):
  "Did I get a good deal?" after a non-refundable booking -> cg.regret            (setting `regret_answer`)
  "Book now or wait?" while a Price Watch drop forecast AND a Fare Lock offer are both live -> cg.reconcile
                                                                                   (setting `reconcile_answer`)
Inline reconcile on the fare-detail page, below the Fare Lock banner (setting `fare_detail_reconcile`):
  "off"            never
  "experiment"     only travellers whose experiment arm `fare_detail_reconcile` is true (2.4)
  "everyone"       every traveller (2.4.1)
A reconcile is only shown while both offers are live: not booked, the forecast says drop, and a Fare Lock feature
with seats in the bucket is enabled. All messages carry data-feature="concierge".
"""
from __future__ import annotations

from ..catalogue import money, plural
from . import BaseFeature, concierge


class Feature(concierge.Feature):
    DEFAULTS = {"proactive": True, "upgrade_tip_delay": "2h54m", "regret_answer": True, "reconcile_answer": True,
                "fare_detail_reconcile": "experiment", "reconcile_experiment": "fare_detail_reconcile"}
    COPY = {
        "cg.regret": "You should have booked a refundable fare.",
        "cg.reconcile": ("Prices on your dates are likely to drop, but this fare has {seats} left. If you can "
                         "move your dates, wait for the alert; if not, locking protects this price."),
        "cg.upgrade": "You can still switch to a refundable fare for €30 until tomorrow 10:05.",
    }

    def __init__(self, settings=None):  # Concierge 1.0 refuses to be proactive; 2.0 is the release that is
        BaseFeature.__init__(self, settings)
        if self.settings["fare_detail_reconcile"] not in ("off", "experiment", "everyone"):
            raise ValueError(f"concierge fare_detail_reconcile {self.settings['fare_detail_reconcile']!r} "
                             "is not implemented")

    # ---- the two live offers
    def _live_offers(self, ctx):
        """The bucket seat count when a Price Watch drop forecast and a Fare Lock offer are both live, else None."""
        if ctx.booking is not None or ctx.rt.feature("fare_lock") is None or ctx.rt.feature("price_watch") is None:
            return None
        if not ctx.rt.world.forecast(ctx.traveller.trip.route)["drop"]:
            return None
        fare_id = f"{ctx.traveller.trip.route}-NR"
        seats = ctx.rt.world.bucket_left(fare_id)
        return plural(seats, "seat") if seats >= 1 else None

    def _reconcile(self, ctx, surface, channel, **kw):
        seats = self._live_offers(ctx)
        return None if seats is None else self.msg(ctx, "cg.reconcile", surface, channel, seats=seats, **kw)

    # ---- hooks
    def messages_for(self, surface, ctx):
        if surface == "fare_detail":
            mode = self.settings["fare_detail_reconcile"]
            if mode == "everyone" or (mode == "experiment" and ctx.experiment(self.settings["reconcile_experiment"])):
                m = self._reconcile(ctx, surface, "card")
                return [m] if m else []
            return []
        return super().messages_for(surface, ctx)

    def on_action(self, action, ctx, data):
        if action == "book" and self.settings["proactive"] and ctx.booking.fare_kind == "non_refundable":
            ctx.schedule(self.id, "upgrade_tip", delay=self.settings["upgrade_tip_delay"])
        return None

    def on_job(self, job, ctx):
        b = ctx.booking
        if job.kind == "upgrade_tip" and b is not None and b.fare_kind == "non_refundable" \
                and ctx.rt.change_window(b)[1]:
            ctx.send_chat(self.id, "cg.upgrade")

    def concierge_reply(self, question, ctx):
        topic, b = self.classify(question), ctx.booking
        if topic == "deal" and b is not None and b.fare_kind == "non_refundable" and self.settings["regret_answer"]:
            return self.msg(ctx, "cg.regret", "chat", "chat")
        if topic == "when" and self.settings["reconcile_answer"]:
            m = self._reconcile(ctx, "chat", "chat")
            if m:
                return m
        return super().concierge_reply(question, ctx)
