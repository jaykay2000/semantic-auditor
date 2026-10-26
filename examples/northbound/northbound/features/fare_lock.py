"""fare_lock: Fare Lock. Hold a fare for a fee; an inventory notice on the fare page; an urgent variant for imminent trips.

Surfaces
  fare_detail   banner  fl.banner (suggest: lock it) | fl.banner.urgent (book now, or lock) |
                        fl.banner.urgent_bare (experiment arm: book now, no explanation).
                        Hidden once the traveller has booked or holds a lock on this fare.
  checkout      line    fl.checkout.lock, the lock fee actually charged, while a lock is held on this fare.
  hotel_detail  banner  fl.hotel.urgent when check-in is within `hotel_urgent_within_hours` (only with
                        `hotels: True`, 2.4.1; the page itself is mounted by core).
Endpoint
  POST /fare/<id>/lock  buy the lock: one charge `fare_lock` (own line in the booking oracle, same quote id as the
                        fare), then redirect to the checkout page. The lock holds `lock_hours` (`urgent_lock_hours`
                        when the traveller was in the urgent variant when buying).

Settings (every behaviour a release can change is one of these)
  urgent_within_hours   72      the time test:  departure - now <= this (exact timestamps, never rounded)
  urgent_targeting      "time_only" | "time_or_fixed_dates"
                        2.4 ships "time_or_fixed_dates": departure within the window OR the trip has fixed dates
                        (traveller.flexible is False). Fixed dates alone then trigger the urgent variant.
  lock_fee_cents        900     what the banner calls "EUR 9 total, for your whole booking"
  lock_fee_basis        "per_booking" | "per_traveller"
                        2.4 ships "per_traveller": a couple is charged twice the fee the banner promised.
  lock_hours            48      urgent_lock_hours 12
  urgent_copy_experiment "fl_urgent_copy"  the experiment name; arm "bare" shows fl.banner.urgent_bare
  hotels                False   turn on the hotel_detail banner (2.4.1)
  hotel_urgent_within_hours 72
The seat count in the banner is the fare BUCKET count (world.bucket_left), which defaults to the inventory but
can be set separately by the world hook.
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

from ..catalogue import money, plural
from ..clock import iso
from ..models import Charge
from . import BaseFeature


class Feature(BaseFeature):
    id = "fare_lock"
    DEFAULTS = {"urgent_within_hours": 72, "urgent_targeting": "time_only", "lock_fee_cents": 900,
                "lock_fee_basis": "per_booking", "lock_hours": 48, "urgent_lock_hours": 12,
                "urgent_copy_experiment": "fl_urgent_copy", "hotels": False, "hotel_urgent_within_hours": 72}
    COPY = {
        "fl.banner": "{seats} left at this fare. Lock it for {lock_hours} h for {fee} total, for your whole booking.",
        "fl.banner.urgent": ("Departing soon: only {seats} left at this fare. Book now, or lock it for "
                             "{lock_hours} h for {fee} total if your plans might change."),
        "fl.banner.urgent_bare": "Only {seats} left. Book now.",
        "fl.checkout.lock": "Fare Lock ({lock_hours} h): {amount}",
        "fl.hotel.urgent": ("Checking in soon: only {rooms} left at this rate. Book now, or hold it for "
                            "{lock_hours} h for {fee} total if your plans might change."),
    }

    def __init__(self, settings=None):
        super().__init__(settings)
        if self.settings["urgent_targeting"] not in ("time_only", "time_or_fixed_dates"):
            raise ValueError(f"fare_lock urgent_targeting {self.settings['urgent_targeting']!r} is not implemented")
        if self.settings["lock_fee_basis"] not in ("per_booking", "per_traveller"):
            raise ValueError(f"fare_lock lock_fee_basis {self.settings['lock_fee_basis']!r} is not implemented")

    # ---- decisions
    def is_urgent(self, ctx) -> bool:
        """The product team's targeting for the urgent variant."""
        t = ctx.traveller
        soon = t.trip.departure_at - ctx.now <= timedelta(hours=self.settings["urgent_within_hours"])
        if self.settings["urgent_targeting"] == "time_or_fixed_dates":
            return soon or not t.flexible
        return soon

    def lock_fee_cents(self, ctx) -> int:
        fee = self.settings["lock_fee_cents"]
        return fee * ctx.traveller.party if self.settings["lock_fee_basis"] == "per_traveller" else fee

    def held_lock(self, ctx, fare_id: str | None = None) -> dict | None:
        lock = ctx.state_for(self.id).get("lock")
        if lock is None or ctx.now >= lock["held_until"]:
            return None
        return lock if fare_id is None or lock["fare_id"] == fare_id else None

    def _lock_action(self, fare, label):
        return {"method": "post", "url": f"/fare/{fare.id}/lock", "label": label, "fields": {}}

    # ---- hooks
    def messages_for(self, surface, ctx):
        s = self.settings
        if surface == "fare_detail":
            fare = ctx.fare
            seats = ctx.rt.world.bucket_left(fare.id)
            if ctx.booking is not None or self.held_lock(ctx, fare.id) or seats < 1:
                return []
            params = {"seats": plural(seats, "seat"), "fee": money(s["lock_fee_cents"])}
            checkout = {"method": "get", "url": f"/checkout/{fare.id}", "label": "Book now"}
            if not self.is_urgent(ctx):
                return [self.msg(ctx, "fl.banner", surface, "banner", lock_hours=s["lock_hours"], **params,
                                 action=self._lock_action(fare, "Lock this fare"))]
            if ctx.experiment(s["urgent_copy_experiment"]) == "bare":
                return [self.msg(ctx, "fl.banner.urgent_bare", surface, "banner", seats=params["seats"],
                                 action=checkout)]
            return [self.msg(ctx, "fl.banner.urgent", surface, "banner", lock_hours=s["urgent_lock_hours"],
                             **params, action=checkout,
                             more_actions=[self._lock_action(fare, "Lock this fare")])]
        if surface == "checkout":
            lock = self.held_lock(ctx, ctx.fare.id)
            if lock and ctx.booking is None:
                return [self.msg(ctx, "fl.checkout.lock", surface, "page", slot="line",
                                 lock_hours=lock["hours"], amount=money(lock["amount_cents"]))]
            return []
        if surface == "hotel_detail" and s["hotels"]:
            stay = ctx.traveller.stay
            if stay is None or stay.check_in_at - ctx.now > timedelta(hours=s["hotel_urgent_within_hours"]):
                return []
            return [self.msg(ctx, "fl.hotel.urgent", surface, "banner", slot="notice", component="hotel",
                             rooms=plural(ctx.rt.world.rooms_left(ctx.hotel["id"]), "room"),
                             lock_hours=s["urgent_lock_hours"], fee=money(s["lock_fee_cents"]))]
        return []

    def routes(self, app, env):
        @app.post("/fare/{fare_id}/lock")
        def buy_lock(request: Request, fare_id: str):
            fare = env.need_fare(fare_id)
            ctx = env.ctx_for(request, fare=fare)
            if ctx.booking is not None:
                raise HTTPException(409, "already_booked")
            if self.held_lock(ctx):
                raise HTTPException(409, "already_locked")
            seats = ctx.rt.world.bucket_left(fare.id)
            if seats < 1:
                raise HTTPException(409, "sold_out")
            hours = self.settings["urgent_lock_hours"] if self.is_urgent(ctx) else self.settings["lock_hours"]
            n = ctx.rt.next_id("lock")
            amount = self.lock_fee_cents(ctx)
            st = ctx.state_for(self.id)
            st["lock"] = {"id": n, "fare_id": fare.id, "hours": hours, "amount_cents": amount,
                          "bought_at": ctx.now, "held_until": ctx.now + timedelta(hours=hours),
                          "charge": Charge(f"{n}-c1", "fare_lock", f"Fare Lock ({hours} h)", amount,
                                           f"txn-{n}", ctx.rt.quote(fare, ctx.traveller.party)["quote_id"])}
            return RedirectResponse(f"/checkout/{fare.id}", status_code=303)

    def oracle_extras(self, ctx):
        lock = ctx.state_for(self.id).get("lock")
        if lock is None:
            return {"fare_lock": None}
        return {"charges": [lock["charge"].as_dict()],
                "fare_lock": {"fare_id": lock["fare_id"], "bought_at": iso(lock["bought_at"]),
                              "held_until": iso(lock["held_until"]), "hours": lock["hours"],
                              "held": ctx.now < lock["held_until"]}}
