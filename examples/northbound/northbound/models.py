"""Plain data classes shared by the runtime and the features."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .clock import iso


@dataclass
class Trip:
    origin: str
    destination: str
    departure_at: datetime

    @property
    def route(self) -> str:
        return f"{self.origin}-{self.destination}"


@dataclass
class Stay:
    """A hotel stay the traveller is looking at (created by the persona hook)."""
    hotel_id: str
    check_in_at: datetime
    nights: int = 2
    rooms: int = 1


@dataclass
class Traveller:
    id: str
    name: str
    party: int  # number of travellers on the booking: 1, 2 or 4
    flexible: bool
    trip: Trip
    experiments: dict[str, Any] = field(default_factory=dict)  # experiment arm per traveller: {"name": arm}
    stay: Stay | None = None

    @property
    def email(self) -> str:
        return f"{self.id}@example.test"


@dataclass
class Fare:
    id: str  # e.g. LIS-BER-NR
    route: str  # e.g. LIS-BER
    kind: str  # non_refundable | refundable
    name: str
    unit_cents: int  # per traveller, before taxes and fees
    taxes_cents: int  # per traveller

    @property
    def origin(self) -> str:
        return self.route.split("-")[0]

    @property
    def destination(self) -> str:
        return self.route.split("-")[1]


@dataclass
class Charge:
    id: str
    what: str  # fare | taxes_and_fees | upgrade_to_refundable | fare_lock
    label: str
    amount_cents: int
    transaction: str
    quote_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"charge_id": self.id, "what": self.what, "label": self.label,
                "amount_cents": self.amount_cents, "currency": "EUR",
                "transaction": self.transaction, "quote_id": self.quote_id}


@dataclass
class Booking:
    id: str
    traveller_id: str
    fare_id: str
    fare_kind: str
    party: int
    booked_at: datetime
    departure_at: datetime
    origin: str
    destination: str
    charges: list[Charge] = field(default_factory=list)

    @property
    def total_cents(self) -> int:
        return sum(c.amount_cents for c in self.charges)


@dataclass
class Message:
    """One thing the product tells a traveller. Rendered through ONE template macro, or sent to a sink."""
    key: str
    feature: str
    surface: str  # search_results | fare_detail | checkout | confirmation | chat | inbox | device | itinerary
    channel: str  # page | card | banner | chat | email | push | pdf
    text: str
    shown_at: datetime
    traveller_id: str | None = None
    slot: str = "notice"
    action: dict[str, Any] | None = None  # {"url", "label", "method": "get"|"post", "fields": {...}}
    id: str | None = None  # assigned when the message is logged
    component: str = "flight"  # flight | hotel: what the message is about
    more_actions: list[dict[str, Any]] = field(default_factory=list)  # secondary actions, same shape as `action`

    @property
    def shown_at_iso(self) -> str:
        return iso(self.shown_at)

    def log_row(self) -> dict[str, Any]:
        return {"id": self.id, "traveller": self.traveller_id, "feature": self.feature, "surface": self.surface,
                "channel": self.channel, "message_key": self.key, "shown_at": self.shown_at_iso, "text": self.text,
                "component": self.component}
