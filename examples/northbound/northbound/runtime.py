"""The Northbound runtime: simulated clock, job queue, state, outbox, message log, booking services.

One Runtime per app. Features (northbound.features) get a Ctx; they never touch globals.
"""
from __future__ import annotations

import html
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from . import catalogue
from .catalogue import city, fare_by_id, fares_for, money, party_label, when
from .clock import D0, Job, JobQueue, SimClock, iso, parse_duration, run_until
from .config import Config
from .copy import COPY, render
from .features import BaseFeature, load_feature
from .models import Booking, Charge, Fare, Message, Stay, Traveller, Trip
from .releases import Release, load_release

DEFAULT_SEATS = 9
DEFAULT_ROOMS = 5
DEFAULT_FORECAST = {"drop": True, "window_days": 14}


@dataclass
class World:
    """Oracle state the test hooks can set: seats left per fare, rooms left per hotel, drop forecast per route.

    `bucket_seats` is the seat count a PRODUCT surface may show for a fare bucket; it defaults to the real
    inventory (`seats`) and the world hook can set it separately, so a release can show a count that differs
    from the inventory oracle.
    """
    seats: dict[str, int] = field(default_factory=dict)
    bucket_seats: dict[str, int] = field(default_factory=dict)
    rooms: dict[str, int] = field(default_factory=dict)
    forecasts: dict[str, dict[str, Any]] = field(default_factory=dict)

    def seats_left(self, fare_id: str) -> int:
        return self.seats.get(fare_id, DEFAULT_SEATS)

    def bucket_left(self, fare_id: str) -> int:
        return self.bucket_seats.get(fare_id, self.seats_left(fare_id))

    def rooms_left(self, hotel_id: str) -> int:
        return self.rooms.get(hotel_id, DEFAULT_ROOMS)

    def forecast(self, route: str) -> dict[str, Any]:
        return {"route": route, **self.forecasts.get(route, DEFAULT_FORECAST)}


class DuplicateTraveller(Exception):
    pass


class Runtime:
    def __init__(self, cfg: Config, release: Release | str | None = None):
        self.cfg = cfg
        self.release = release if isinstance(release, Release) else load_release(release or cfg.release)
        self.features: list[BaseFeature] = [
            load_feature(spec, self.release.settings) for spec in self.release.features]
        if not any(f.id == "core" for f in self.features):
            raise ValueError(f"release {self.release.name} must enable the core feature")
        self.copy: dict[str, str] = dict(COPY)
        for f in self.features:
            self.copy.update(f.COPY)
        self.copy.update(self.release.copy)
        self.reset()

    # ---- state -----------------------------------------------------------------------------------------
    def reset(self) -> None:
        self.clock = SimClock(D0)
        self.jobs = JobQueue()
        self.travellers: dict[str, Traveller] = {}
        self.bookings: dict[str, Booking] = {}
        self.world = World()
        self.log: list[dict[str, Any]] = []
        self.chats: dict[str, list[dict[str, Any]]] = {}
        self._fstate: dict[tuple[str, str], dict[str, Any]] = {}
        self._ids = 0
        self._bookings_made = 0
        for sub in ("email", "push"):
            d = self.cfg.outbox_dir / sub
            if d.exists():
                for f in d.glob("*.json"):
                    f.unlink()
            d.mkdir(parents=True, exist_ok=True)

    @property
    def now(self) -> datetime:
        return self.clock.now

    def next_id(self, prefix: str = "m") -> str:
        self._ids += 1
        return f"{prefix}{self._ids:06d}"

    def feature(self, fid: str) -> BaseFeature | None:
        return next((f for f in self.features if f.id == fid), None)

    def fstate(self, fid: str, traveller_id: str) -> dict[str, Any]:
        return self._fstate.setdefault((fid, traveller_id), {})

    def ctx(self, traveller: Traveller | None = None, **extra: Any) -> "Ctx":
        return Ctx(self, traveller, **extra)

    # ---- travellers ------------------------------------------------------------------------------------
    def create_traveller(self, tid: str, name: str, party: int, flexible: bool, trip: Trip,
                         experiments: dict[str, Any] | None = None, stay: Stay | None = None) -> Traveller:
        if tid in self.travellers:
            raise DuplicateTraveller(tid)
        t = self.travellers[tid] = Traveller(tid, name, party, flexible, trip, dict(experiments or {}), stay)
        return t

    def booking_of(self, traveller_id: str) -> Booking | None:
        return next((b for b in self.bookings.values() if b.traveller_id == traveller_id), None)

    # ---- time and jobs ---------------------------------------------------------------------------------
    def advance(self, delta: timedelta) -> list[Job]:
        return self.run_until(self.now + delta)

    def run_until(self, target: datetime) -> list[Job]:
        return run_until(self.clock, self.jobs, target, self._run_job)

    def _run_job(self, job: Job) -> None:
        feature = self.feature(job.feature)
        if feature is None:  # the release no longer carries the feature: nothing can run the job
            return
        traveller = self.travellers.get(job.traveller_id) if job.traveller_id else None
        feature.on_job(job, self.ctx(traveller))

    # ---- actions ---------------------------------------------------------------------------------------
    def dispatch_action(self, action: str, ctx: "Ctx", data: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Offer an action to every feature, in release order. None = nobody handled it."""
        outcome: dict[str, Any] | None = None
        for f in self.features:
            result = f.on_action(action, ctx, data or {})
            if result is None:
                continue
            outcome = {**(outcome or {}), **result}
            if "error" in result:
                break
        return outcome

    def collect(self, surface: str, ctx: "Ctx", *, log: bool = True) -> list[Message]:
        msgs = [m for f in self.features for m in f.messages_for(surface, ctx)]
        if log:
            self.record(msgs)
        return msgs

    def record(self, msgs: list[Message]) -> None:
        for m in msgs:
            m.id = self.next_id()
            self.log.append(m.log_row())

    # ---- booking services ------------------------------------------------------------------------------
    def quote(self, fare: Fare, party: int) -> dict[str, Any]:
        return {"quote_id": f"q-{fare.id}-{party}", "fare": fare.unit_cents * party,
                "taxes": fare.taxes_cents * party, "total": (fare.unit_cents + fare.taxes_cents) * party}

    def blocked_reason(self, ctx: "Ctx", fare: Fare) -> str | None:
        if ctx.booking is not None:
            return "already_booked"
        if self.world.seats_left(fare.id) < ctx.traveller.party:
            return "sold_out"
        return None

    def change_window(self, booking: Booking) -> tuple[datetime, bool]:
        hours = self.feature("core").settings["change_window_hours"]
        ends = booking.booked_at + timedelta(hours=hours)
        return ends, self.now <= ends

    def create_booking(self, ctx: "Ctx", fare: Fare) -> Booking:
        reason = self.blocked_reason(ctx, fare)
        if reason:
            raise ValueError(reason)
        t = ctx.traveller
        self._bookings_made += 1
        bid = f"NB{self._bookings_made:04d}"
        q = self.quote(fare, t.party)
        txn = f"txn-{bid}"
        booking = Booking(bid, t.id, fare.id, fare.kind, t.party, self.now, t.trip.departure_at,
                          fare.origin, fare.destination)
        booking.charges = [
            Charge(f"{bid}-c1", "fare", f"{fare.name} x {t.party}", q["fare"], txn, q["quote_id"]),
            Charge(f"{bid}-c2", "taxes_and_fees", "Taxes and fees", q["taxes"], txn, q["quote_id"]),
        ]
        self.world.seats[fare.id] = self.world.seats_left(fare.id) - t.party
        self.bookings[bid] = booking
        self.dispatch_action("book", ctx, {"booking_id": bid})
        return booking

    def upgrade_booking(self, ctx: "Ctx") -> str | None:
        """Switch to a refundable fare inside the change window. Returns an error code or None."""
        b = ctx.booking
        if b is None or b.fare_kind != "non_refundable":
            return "not_applicable"
        if not self.change_window(b)[1]:
            return "window_closed"
        fee = self.feature("core").settings["upgrade_fee_cents"]
        b.fare_kind = "refundable"
        b.charges.append(Charge(f"{b.id}-c{len(b.charges) + 1}", "upgrade_to_refundable",
                                "Switch to refundable fare", fee, f"txn-{b.id}-upgrade", None))
        self.dispatch_action("upgrade", ctx, {"booking_id": b.id})
        return None

    # ---- sinks -----------------------------------------------------------------------------------------
    def _write_sink(self, kind: str, msg: Message, doc: dict[str, Any]) -> None:
        path = self.cfg.outbox_dir / kind / f"{msg.id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- oracles ---------------------------------------------------------------------------------------
    def oracle_booking(self, traveller_id: str) -> dict[str, Any]:
        t = self.travellers[traveller_id]
        b = self.booking_of(traveller_id)
        if b is None:
            return self._with_extras(self.ctx(t), {
                "traveller": traveller_id, "status": "not_booked", "booking_id": None, "fare_type": None,
                "fare_id": None, "departure_at": iso(t.trip.departure_at), "booked_at": None,
                "change_window_ends": None, "within_change_window": False, "party": t.party,
                "charges": [], "total_cents": 0, "currency": "EUR"})
        ends, within = self.change_window(b)
        return self._with_extras(self.ctx(t), {
            "traveller": traveller_id, "status": "booked", "booking_id": b.id, "fare_type": b.fare_kind,
            "fare_id": b.fare_id, "departure_at": iso(b.departure_at), "booked_at": iso(b.booked_at),
            "change_window_ends": iso(ends), "within_change_window": within, "party": b.party,
            "charges": [c.as_dict() for c in b.charges], "total_cents": b.total_cents, "currency": "EUR"})

    def _with_extras(self, ctx: "Ctx", doc: dict[str, Any]) -> dict[str, Any]:
        """Let features add charges (their own lines) and extra fields to the booking oracle."""
        for f in self.features:
            extra = f.oracle_extras(ctx)
            if not extra:
                continue
            extra = dict(extra)
            doc["charges"] = list(doc["charges"]) + list(extra.pop("charges", []))
            doc["total_cents"] = sum(c["amount_cents"] for c in doc["charges"])
            doc.update(extra)
        return doc


@dataclass
class Ctx:
    """What a feature hook sees: the runtime, the current traveller, and the page's fare (if any)."""
    rt: Runtime
    traveller: Traveller | None = None
    fare: Fare | None = None
    fares: list[Fare] = field(default_factory=list)
    hotel: dict[str, str] | None = None  # the hotel page's hotel (see catalogue.hotel_by_id)

    @property
    def now(self) -> datetime:
        return self.rt.now

    @property
    def booking(self) -> Booking | None:
        return self.rt.booking_of(self.traveller.id) if self.traveller else None

    def state_for(self, feature_id: str) -> dict[str, Any]:
        """Per-traveller scratch state, private to the feature that asks."""
        return self.rt.fstate(feature_id, self.traveller.id)

    def experiment(self, name: str, default: Any = None) -> Any:
        """The traveller's arm for experiment `name` (set by the persona hook), or `default`."""
        return self.traveller.experiments.get(name, default) if self.traveller else default

    def message(self, feature: str, key: str, surface: str, channel: str, *, slot: str = "notice",
                action: dict[str, Any] | None = None, component: str = "flight",
                more_actions: list[dict[str, Any]] | None = None, **params: Any) -> Message:
        t = self.traveller
        base = {"party": party_label(t.party) if t else "", "travellers": t.party if t else "",
                "upgrade_fee": money(self.rt.feature("core").settings["upgrade_fee_cents"])}
        text = render(self.rt.copy, key, **{**base, **params})
        return Message(key, feature, surface, channel, text, self.now, t.id if t else None, slot, action,
                       component=component, more_actions=list(more_actions or []))

    def common_params(self) -> dict[str, Any]:
        t = self.traveller
        return {"origin": t.trip.origin, "destination": t.trip.destination, "origin_city": city(t.trip.origin),
                "destination_city": city(t.trip.destination), "departure": when(t.trip.departure_at)}

    # ---- sinks and jobs
    def send_chat(self, feature: str, key: str, **params: Any) -> Message:
        """Post an in-app message into the traveller's chat (a proactive tip). Never an email or push."""
        msg = self.message(feature, key, "chat", "chat", **params)
        self.rt.record([msg])
        self.rt.chats.setdefault(self.traveller.id, []).append(
            {"who": "concierge", "text": msg.text, "message": msg})
        return msg

    def send_email(self, feature: str, key: str, **params: Any) -> Message:
        msg = self.message(feature, key, "inbox", "email", **params)
        self.rt.record([msg])
        subject_key = f"{key}.subject"
        subject = render(self.rt.copy, subject_key, **{**self.common_params(), **params}) \
            if subject_key in self.rt.copy else msg.text[:60]
        self.rt._write_sink("email", msg, {
            "message_id": msg.id, "to": self.traveller.email, "subject": subject, "sent_at": msg.shown_at_iso,
            "headers": {"X-Feature": feature, "X-Message-Key": key}, "text": msg.text,
            "html": f"<html><body><p>{html.escape(msg.text, quote=False)}</p></body></html>"})
        return msg

    def send_push(self, feature: str, key: str, **params: Any) -> Message:
        msg = self.message(feature, key, "device", "push", **params)
        self.rt.record([msg])
        title_key = f"{key}.title"
        title = render(self.rt.copy, title_key, **params) if title_key in self.rt.copy else "Northbound"
        self.rt._write_sink("push", msg, {
            "message_id": msg.id, "to": self.traveller.id, "title": title, "sent_at": msg.shown_at_iso,
            "headers": {"X-Feature": feature, "X-Message-Key": key}, "text": msg.text})
        return msg

    def schedule(self, feature: str, kind: str, *, delay: str | timedelta, payload: dict[str, Any] | None = None) -> Job:
        d = parse_duration(delay) if isinstance(delay, str) else delay
        return self.rt.jobs.schedule(self.now + d, feature, kind,
                                     self.traveller.id if self.traveller else None, payload)

    def cancel_jobs(self, feature: str) -> list[Job]:
        """Cancel this traveller's pending jobs for `feature`."""
        return self.rt.jobs.cancel(feature=feature, traveller_id=self.traveller.id if self.traveller else None)
