"""Northbound 2.4.1: the memory fixture. Fixes for the issues the owner marked *fix*; Fare Lock extends to hotels.

THE OWNER'S FIX LIST IS `APPLIED_FIXES` BELOW. Each fix is one named setting group in `FIXES`; to change the
owner's disposition of an issue, add or remove its name in `APPLIED_FIXES` (one line). Removing a name restores
the 2.4 behaviour for that issue and nothing else.

Everything else from 2.4 stays (urgent targeting by fixed dates, the bucket count, cg.regret, the proactive
upgrade tip ...). Fare Lock to hotels is NOT a fix: it is a new surface (`hotel_detail`, component hotel) with
`fl.hotel.urgent`, outside the scope of the exception the owner approved for flight fare detail and checkout.
"""
from . import load_release, register_release

FIXES = {
    "price_watch_stops_after_booking": {"price_watch": {"stop_after_booking": True}},
    "lock_fee_per_booking": {"fare_lock": {"lock_fee_basis": "per_booking"}},
    "reconcile_on_fare_detail_for_everyone": {"concierge": {"fare_detail_reconcile": "everyone"}},
}

APPLIED_FIXES = [  # <- the owner's final "fix" dispositions
    "price_watch_stops_after_booking",
    "lock_fee_per_booking",
    "reconcile_on_fare_detail_for_everyone",
]

HOTELS = {"core": {"hotels": True}, "fare_lock": {"hotels": True, "hotel_urgent_within_hours": 72}}


def _settings():
    merged: dict[str, dict] = {}
    for group in [FIXES[name] for name in APPLIED_FIXES] + [HOTELS]:
        for fid, vals in group.items():
            merged.setdefault(fid, {}).update(vals)
    return merged


RELEASE = register_release(load_release("2.4").derive("2.4.1", settings=_settings()))
