"""price_watch: Price Watch 1.0. Opt-in alerts, before booking only.

A card on search results offers to watch prices. After the traveller opts in, ONE forecast alert email is
scheduled (alert_delay after opt-in). When the traveller books, every Price Watch job for them is cancelled
(stop_after_booking), so nothing from this feature is ever sent after booking.

Settings: mode ("opt_in" is the only mode this module implements; a release that needs another mode, such as
auto-enrolment, extends or replaces this module), alert_delay ("30s"), stop_after_booking (True).
"""
from __future__ import annotations

from . import BaseFeature


class Feature(BaseFeature):
    id = "price_watch"
    DEFAULTS = {"mode": "opt_in", "alert_delay": "30s", "stop_after_booking": True}
    MODES = ("opt_in",)  # a subclass (price_watch_v2) widens this; this module implements opt-in only

    def __init__(self, settings=None):
        super().__init__(settings)
        if self.settings["mode"] not in self.MODES:
            raise ValueError(f"price_watch mode {self.settings['mode']!r} is not implemented by this module")

    def messages_for(self, surface, ctx):
        if surface != "search_results" or ctx.booking is not None:  # before booking only
            return []
        if ctx.state_for(self.id).get("opted_in"):
            return [self.msg(ctx, "pw.card.watching", surface, "card")]
        return [self.msg(ctx, "pw.card.optin", surface, "card",
                         action={"method": "post", "url": "/action/opt_in", "label": "Turn on Price Watch",
                                 "fields": {"next": "/search"}})]

    def on_action(self, action, ctx, data):
        if action == "opt_in":
            if ctx.booking is not None:
                return {"error": "already_booked"}
            st = ctx.state_for(self.id)
            if not st.get("opted_in"):
                st["opted_in"] = True
                ctx.schedule(self.id, "forecast_alert", delay=self.settings["alert_delay"])
            return {"opted_in": True}
        if action == "book" and self.settings["stop_after_booking"]:
            ctx.cancel_jobs(self.id)
        return None

    def on_job(self, job, ctx):
        if job.kind != "forecast_alert":
            return
        t = ctx.traveller
        drop = ctx.rt.world.forecast(t.trip.route)["drop"]
        ctx.send_email(self.id, "pw.email.forecast" if drop else "pw.email.forecast.nodrop", **ctx.common_params())
