"""price_watch (2.0): the same feature id, now also with `mode: auto_enroll`.

Every traveller who searches is enrolled (no opt-in card). The search results show the forecast card
(`pw.card` when the forecast says drop, `pw.card.nodrop` otherwise, before booking only). Then, per enrolled
traveller, relative to the search:

    forecast_email_delay (1m)   pw.email.forecast  (pw.email.forecast.nodrop when the forecast says no drop)
    followup_email_delay (2h)   pw.email.after     (only when the forecast says drop)
    push_delay (8h)             pw.push.moving     (only when the forecast says drop)

`stop_after_booking` decides whether booking cancels the pending jobs. 2.4 ships it False (the follow-ups keep
coming after the traveller has booked); 2.4.1 turns it on by setting. `mode: opt_in` still works exactly as in
Price Watch 1.0 (this class extends it).
"""
from __future__ import annotations

from . import price_watch


class Feature(price_watch.Feature):
    DEFAULTS = {**price_watch.Feature.DEFAULTS, "forecast_email_delay": "1m", "followup_email_delay": "2h",
                "push_delay": "8h"}
    MODES = ("opt_in", "auto_enroll")
    COPY = {
        "pw.email.after": "Keep waiting to book. We'll tell you when prices drop.",
        "pw.email.after.subject": "Price Watch: update for {origin} to {destination}",
        "pw.push.moving": "Prices on {origin}→{destination} are moving.",
        "pw.push.moving.title": "Price Watch",
    }

    def _auto(self) -> bool:
        return self.settings["mode"] == "auto_enroll"

    def _drop(self, ctx) -> bool:
        return ctx.rt.world.forecast(ctx.traveller.trip.route)["drop"]

    def messages_for(self, surface, ctx):
        if not self._auto():
            return super().messages_for(surface, ctx)
        if surface != "search_results" or ctx.booking is not None:  # before booking only
            return []
        return [self.msg(ctx, "pw.card" if self._drop(ctx) else "pw.card.nodrop", surface, "card")]

    def on_action(self, action, ctx, data):
        if not self._auto():
            return super().on_action(action, ctx, data)
        if action == "search" and ctx.booking is None:
            st = ctx.state_for(self.id)
            if not st.get("enrolled"):
                st["enrolled"] = True
                ctx.schedule(self.id, "forecast_email", delay=self.settings["forecast_email_delay"])
                ctx.schedule(self.id, "followup_email", delay=self.settings["followup_email_delay"])
                ctx.schedule(self.id, "moving_push", delay=self.settings["push_delay"])
        elif action == "book" and self.settings["stop_after_booking"]:
            ctx.cancel_jobs(self.id)
        return None

    def on_job(self, job, ctx):
        if not self._auto():
            return super().on_job(job, ctx)
        drop, common = self._drop(ctx), ctx.common_params()
        if job.kind == "forecast_email":
            ctx.send_email(self.id, "pw.email.forecast" if drop else "pw.email.forecast.nodrop", **common)
        elif job.kind == "followup_email" and drop:
            ctx.send_email(self.id, "pw.email.after", **common)
        elif job.kind == "moving_push" and drop:
            ctx.send_push(self.id, "pw.push.moving", **common)
