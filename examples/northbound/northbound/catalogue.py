"""Fares, cities and formatting. Static: prices do not move in Northbound."""
from __future__ import annotations

from datetime import datetime

from .models import Fare

CITIES = {"LIS": "Lisbon", "BER": "Berlin", "MAD": "Madrid", "AMS": "Amsterdam", "CDG": "Paris", "FCO": "Rome",
          "LHR": "London", "OSL": "Oslo"}

NON_REFUNDABLE_CENTS = 12_900  # per traveller
REFUNDABLE_CENTS = 18_900
TAXES_CENTS = 2_400  # per traveller
UPGRADE_FEE_CENTS = 3_000  # flat, per booking (also the core setting upgrade_fee_cents)

_KINDS = {
    "NR": ("non_refundable", "Non-refundable fare", NON_REFUNDABLE_CENTS),
    "RF": ("refundable", "Refundable fare", REFUNDABLE_CENTS),
}


HOTELS = {"LIS-H1": ("Hotel Alfama", "LIS"), "BER-H1": ("Hotel Mitte", "BER")}


def hotel_by_id(hotel_id: str) -> dict[str, str] | None:
    h = HOTELS.get(hotel_id.upper())
    return {"id": hotel_id.upper(), "name": h[0], "city_code": h[1], "city": CITIES[h[1]]} if h else None


def plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def city(code: str) -> str:
    return CITIES.get(code, code)


def fares_for(origin: str, destination: str) -> list[Fare]:
    route = f"{origin}-{destination}"
    return [Fare(f"{route}-{suffix}", route, kind, name, cents, TAXES_CENTS)
            for suffix, (kind, name, cents) in _KINDS.items()]


def fare_by_id(fare_id: str) -> Fare | None:
    parts = fare_id.upper().split("-")
    if len(parts) != 3 or parts[2] not in _KINDS or not (parts[0].isalpha() and parts[1].isalpha()):
        return None
    return next(f for f in fares_for(parts[0], parts[1]) if f.id.endswith("-" + parts[2]))


def money(cents: int) -> str:
    if cents % 100 == 0:
        return f"€{cents // 100:,}"
    return f"€{cents / 100:,.2f}"


def party_label(n: int) -> str:
    return f"{n} traveller" + ("" if n == 1 else "s")


def when(d: datetime) -> str:
    return d.strftime("%a %d %b %Y, %H:%M UTC")
