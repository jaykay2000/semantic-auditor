"""core: search results, fare detail, checkout, confirmation page, confirmation email. (The PDF is in northbound.pdf.)

Calm and factual. Core says nothing about scarcity, urgency or when to book.
"""
from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse

from ..catalogue import hotel_by_id, money, when
from ..models import Message
from . import BaseFeature


class Feature(BaseFeature):
    id = "core"
    DEFAULTS = {"change_window_hours": 24, "upgrade_fee_cents": 3000, "hotels": False}
    COPY = {
        "core.hotel.summary": "{hotel_name} in {hotel_city}. Check-in {check_in}, {nights} nights.",
        "core.hotel.summary.nostay": "{hotel_name} in {hotel_city}. No stay dates are selected.",
    }

    def routes(self, app, env):
        if not self.settings["hotels"]:  # the hotel page exists only in releases that turn hotels on
            return

        @app.get("/hotel/{hotel_id}", response_class=HTMLResponse)
        def hotel_detail(request: Request, hotel_id: str):
            hotel = hotel_by_id(hotel_id)
            if hotel is None:
                raise HTTPException(404, f"No such hotel {hotel_id!r}")
            ctx = env.ctx_for(request, hotel=hotel)
            return env.page(request, "hotel.html", ctx, "hotel_detail")

    # ---- helpers
    def _fare_params(self, ctx, fare):
        q = ctx.rt.quote(fare, ctx.traveller.party)
        return {"fare_name": fare.name, "total": money(q["total"]), "amount": money(q["total"])}

    # ---- hooks
    def messages_for(self, surface: str, ctx) -> list[Message]:
        t, rt = ctx.traveller, ctx.rt
        common = ctx.common_params()
        out: list[Message] = []
        if surface == "search_results":
            out.append(self.msg(ctx, "core.results", surface, "page", slot="summary", n=len(ctx.fares), **common))
            for fare in ctx.fares:
                out.append(self.msg(ctx, "core.results.fare", surface, "page", slot="fare_row",
                                    action={"method": "get", "url": f"/fare/{fare.id}", "label": "View fare"},
                                    **self._fare_params(ctx, fare)))
        elif surface == "fare_detail":
            fare = ctx.fare
            out.append(self.msg(ctx, "core.fare.summary", surface, "page", slot="summary",
                                action={"method": "get", "url": f"/checkout/{fare.id}", "label": "Continue to checkout"},
                                **common, **self._fare_params(ctx, fare)))
            out.append(self.msg(ctx, f"core.fare.policy.{fare.kind}", surface, "page"))
        elif surface == "checkout":
            fare = ctx.fare
            reason = rt.blocked_reason(ctx, fare)
            if reason == "already_booked":
                out.append(self.msg(ctx, "core.checkout.already", surface, "page", slot="summary"))
            elif reason == "sold_out":
                out.append(self.msg(ctx, "core.checkout.soldout", surface, "page", slot="summary"))
            else:
                q = rt.quote(fare, t.party)
                out.append(self.msg(ctx, "core.checkout.fare", surface, "page", slot="line",
                                    fare_name=fare.name, amount=money(q["fare"])))
                out.append(self.msg(ctx, "core.checkout.taxes", surface, "page", slot="line",
                                    amount=money(q["taxes"])))
                out.append(self.msg(ctx, "core.checkout.total", surface, "page", slot="total",
                                    amount=money(q["total"])))
                out.append(self.msg(ctx, f"core.fare.policy.{fare.kind}", surface, "page"))
        elif surface == "hotel_detail":
            h, stay = ctx.hotel, t.stay
            if stay is None:
                out.append(self.msg(ctx, "core.hotel.summary.nostay", surface, "page", slot="summary",
                                    component="hotel", hotel_name=h["name"], hotel_city=h["city"]))
            else:
                out.append(self.msg(ctx, "core.hotel.summary", surface, "page", slot="summary", component="hotel",
                                    hotel_name=h["name"], hotel_city=h["city"], check_in=when(stay.check_in_at),
                                    nights=stay.nights))
        elif surface == "confirmation":
            b = ctx.booking
            out.append(self.msg(ctx, "core.confirmed", surface, "page", slot="summary", booking_id=b.id, **common))
            ends, within = rt.change_window(b)
            if b.fare_kind == "refundable":
                out.append(self.msg(ctx, "core.confirmed.fare_refundable", surface, "page"))
            elif within:
                out.append(self.msg(ctx, "core.confirmed.fare_window", surface, "page", until=when(ends),
                                    action={"method": "post", "url": f"/booking/{b.id}/upgrade",
                                            "label": "Switch to refundable fare", "fields": {}}))
            else:
                out.append(self.msg(ctx, "core.confirmed.fare_closed", surface, "page"))
            for c in b.charges:
                out.append(self.msg(ctx, "core.confirmed.charge", surface, "page", slot="line",
                                    label=c.label, amount=money(c.amount_cents)))
            out.append(self.msg(ctx, "core.confirmed.total", surface, "page", slot="total",
                                total=money(b.total_cents)))
        return out

    def on_action(self, action: str, ctx, data):
        if action == "book":  # booking just happened: confirmation email, to the traveller, now
            b = ctx.rt.bookings[data["booking_id"]]
            ctx.send_email(self.id, "core.email.confirmation", booking_id=b.id, total=money(b.total_cents),
                           **ctx.common_params())
        return None
