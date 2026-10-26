"""Northbound 2.4: the narrative fixture. Three changes, each fine on its own; together they leave a traveller
with guidance the owner would not sign. The bugs are deliberate and live in SETTINGS, so 2.4.1 fixes them by
changing settings, not code.

  Fare Lock (new)              fl.banner / fl.banner.urgent / fl.banner.urgent_bare + the lock purchase
      urgent_targeting         "time_or_fixed_dates": fixed dates alone trigger the urgent variant (Hana)
      lock_fee_basis           "per_traveller": a couple pays 2 x the "EUR 9 total" the banner promised (Sam & Alex)
      (bucket seat count)      the banner shows the fare-bucket count, which the world hook sets apart from the
                               inventory (Omar)
  Price Watch auto-enroll      every searcher is enrolled; stop_after_booking False keeps the follow-ups coming
                               after booking (Maya's 12:00 email and 18:00 push)
  Concierge 2.0                proactive cg.upgrade, cg.regret on "good deal?" after a non-refundable booking
                               (regret_answer), cg.reconcile on "book now or wait?", and cg.reconcile inline on the
                               fare page for the experiment arm fare_detail_reconcile (Maya-R)

Experiment arms are per traveller, set with the persona hook: {"fl_urgent_copy": "bare"} and
{"fare_detail_reconcile": true}. The 2.3 opt-in card does not exist here: auto-enroll replaces it.
"""
from . import load_release, register_release

RELEASE = register_release(load_release("2.3").derive(
    "2.4",
    remove=["price_watch", "concierge"],
    add=["northbound.features.price_watch_v2", "fare_lock", "northbound.features.concierge_v2"],
    settings={
        "price_watch": {"mode": "auto_enroll", "forecast_email_delay": "1m", "followup_email_delay": "2h",
                        "push_delay": "8h", "stop_after_booking": False},
        "fare_lock": {"urgent_within_hours": 72, "urgent_targeting": "time_or_fixed_dates",
                      "lock_fee_cents": 900, "lock_fee_basis": "per_traveller", "lock_hours": 48,
                      "urgent_lock_hours": 12},
        "concierge": {"proactive": True, "upgrade_tip_delay": "2h54m", "regret_answer": True,
                      "reconcile_answer": True, "fare_detail_reconcile": "experiment"},
    },
))
