"""Northbound 2.3: the base release. Core booking, Price Watch 1.0 (opt-in, before booking only), Concierge 1.0."""
from . import Release

RELEASE = Release(
    name="2.3",
    features=["core", "price_watch", "concierge"],
    settings={
        "core": {"change_window_hours": 24, "upgrade_fee_cents": 3000},
        "price_watch": {"mode": "opt_in", "alert_delay": "30s", "stop_after_booking": True},
        "concierge": {"proactive": False},
    },
    copy={},
)
