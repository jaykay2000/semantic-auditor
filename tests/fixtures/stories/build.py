"""Hand-authored W1b stories and their expected status vectors.

This file IS the authored fixture: every story and every expected entry below is written
by hand from examples/northbound/README.md. Nothing here is computed by the code under
test. Run it to (re)write the JSON files beside it:  python3 tests/fixtures/stories/build.py
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
D0 = datetime(2026, 11, 2, 10, 0, 0, tzinfo=timezone.utc)

COPY = {
    "pw.card": "Prices on your dates are likely to drop over the next two weeks. We suggest waiting; we'll tell you when to book.",
    "pw.email.after": "Keep waiting to book. We'll tell you when prices drop.",
    "pw.push.moving": "Prices on LIS→BER are moving.",
    "pw.card.nodrop": "Our forecast: prices on this trip are unlikely to drop before departure.",
    "fl.banner": "2 seats left at this fare. Lock it for 48 h for €9 total, for your whole booking.",
    "fl.banner.urgent": ("Departing soon: only 2 seats left at this fare. Book now, or lock it for 12 h "
                         "for €9 total if your plans might change."),
    "fl.banner.urgent_bare": "Only 2 seats left. Book now.",
    "fl.checkout.lock": "Fare Lock (48 h): €18",
    "fl.hotel.urgent": ("Checking in soon: only 1 room left at this rate. Book now, or hold it for 12 h "
                        "for €9 total if your plans might change."),
    "cg.regret": "You should have booked a refundable fare.",
    "cg.reconcile": ("Prices on your dates are likely to drop, but this fare has 2 seats left. If you can move "
                     "your dates, wait for the alert; if not, locking protects this price."),
    "cg.upgrade": "You can still switch to a refundable fare for €30 until tomorrow 10:06.",
}

P2 = "fare_lock|price_watch@when_to_book"


def t(minutes=0, seconds=0, days=0, hours=0):
    return (D0 + timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)).isoformat()


def msg(id, at, feature, surface, channel, key, component="flight", user_initiated=False):
    return {"id": id, "at": at, "kind": "message", "feature": feature, "surface": surface, "channel": channel,
            "component": component, "copy_key": key, "text": COPY[key], "user_initiated": user_initiated}


def act(id, at, action, **effects):
    return {"id": id, "at": at, "kind": "user_action", "action": action, "effects": effects}


def ok(rule, subject):
    return {"rule": rule, "subject": subject, "status": "passed"}


def bad(rule, subject, label=None, conditions=None):
    e = {"rule": rule, "subject": subject, "status": "violated"}
    if label:
        e["label"] = label
    if conditions:
        e["conditions"] = conditions
    return e


def exc(rule, subject, conditions):
    return {"rule": rule, "subject": subject, "status": "excepted", "conditions": conditions}


ALL_MET = [["a", "met"], ["b", "met"], ["c", "met"], ["scope", "met"]]
SEARCH = act("a_search", t(), "search")
PW_CARD = msg("pw_card", t(seconds=5), "price_watch", "search_results", "card", "pw.card")
PW_EMAIL = msg("pw_email", t(minutes=1), "price_watch", "inbox", "email", "pw.card")
PW_NODROP = msg("pw_nodrop", t(seconds=5), "price_watch", "search_results", "card", "pw.card.nodrop")
# W5: Northbound 2.4 emails every searcher the forecast at +1 min, the no-drop wording included (information).
PW_NODROP_EMAIL = msg("pw_email", t(minutes=1), "price_watch", "inbox", "email", "pw.card.nodrop")
FL_BANNER = msg("fl_banner", t(minutes=3), "fare_lock", "fare_detail", "banner", "fl.banner")
FL_URGENT = msg("fl_urgent", t(minutes=3), "fare_lock", "fare_detail", "banner", "fl.banner.urgent")
BOOK = act("a_book", t(minutes=6), "book", booking_status="booked")


def story(id, persona, departure, oracles, events, expected, release="2.4", reconciler=None):
    return {"story": {"id": id, "release": release, "persona": persona,
                      "trip": {"departure_at": departure, "change_window_hours": 24},
                      "truth": oracles, "events": events},
            "expected": expected, "gold_reconciler": reconciler}


MAYA_EVENTS = [SEARCH, PW_CARD, PW_EMAIL, FL_BANNER, BOOK,
               msg("pw_after", t(hours=2), "price_watch", "inbox", "email", "pw.email.after"),
               msg("cg_upgrade", t(hours=3), "concierge", "chat", "chat", "cg.upgrade"),
               msg("pw_push", t(hours=8), "price_watch", "device", "push", "pw.push.moving"),
               act("a_ask", t(days=2, minutes=-58), "ask"),
               msg("cg_regret", t(days=2, minutes=-58, seconds=10), "concierge", "chat", "chat", "cg.regret",
                   user_initiated=True)]
MAYA_COMMON = [ok("U1", "fl_banner"), ok("U3", "pw_card"), ok("U3", "pw_email"), ok("U3", "fl_banner"),
               bad("U3", "pw_after"), ok("U3", "cg_upgrade"), bad("U4", "cg_regret"), bad("P3", "story")]

STORIES = {
    "maya": story("maya", "maya", t(days=42, hours=-2), {"units_left": 2}, MAYA_EVENTS,
                  MAYA_COMMON + [bad("P2", P2, label="unexplained_tradeoff")]),
    "maya_r": story("maya_r", "maya", t(days=42, hours=-2), {"units_left": 2},
                    MAYA_EVENTS + [msg("cg_inline", t(minutes=3, seconds=5), "concierge", "fare_detail", "card",
                                       "cg.reconcile")],
                    MAYA_COMMON + [ok("U1", "cg_inline"), ok("U3", "cg_inline"),
                                   {"rule": "P2", "subject": P2, "status": "passed", "label": "explained_tradeoff"}],
                    reconciler="cg_inline"),
    "lena": story("lena", "lena", t(days=42, hours=-2), {"units_left": 2},
                  [SEARCH, PW_CARD, PW_EMAIL, FL_BANNER, act("a_ask", t(minutes=4), "ask"),
                   msg("cg_answer", t(minutes=4, seconds=10), "concierge", "chat", "chat", "cg.reconcile",
                       user_initiated=True),
                   act("a_leave", t(minutes=6), "leave")],
                  [ok("U1", "fl_banner"), ok("U1", "cg_answer"), ok("U3", "pw_card"), ok("U3", "pw_email"),
                   ok("U3", "fl_banner"), ok("U3", "cg_answer"),
                   {"rule": "P2", "subject": P2, "status": "passed", "label": "explained_tradeoff"},
                   ok("P3", "story")],
                  reconciler="cg_answer"),
    "raj": story("raj", "raj", t(hours=30), {"units_left": 2}, [SEARCH, PW_NODROP, PW_NODROP_EMAIL, FL_URGENT],
                 [ok("U1", "fl_urgent"), ok("U3", "fl_urgent"), exc("P1", "fl_urgent", ALL_MET), ok("P3", "story")]),
    "raj_x": story("raj_x", "raj", t(hours=30), {"units_left": 2},
                   [SEARCH, PW_NODROP, PW_NODROP_EMAIL, msg("fl_bare", t(minutes=3), "fare_lock", "fare_detail", "banner",
                                           "fl.banner.urgent_bare")],
                   [ok("U1", "fl_bare"), ok("U3", "fl_bare"),
                    bad("P1", "fl_bare", conditions=[["a", "met"], ["b", "met"], ["c", "not_met"], ["scope", "met"]]),
                    ok("P3", "story")]),
    "raj_72h": story("raj_72h", "raj", t(minutes=3, hours=72), {"units_left": 2}, [SEARCH, PW_NODROP, PW_NODROP_EMAIL, FL_URGENT],
                     [ok("U1", "fl_urgent"), ok("U3", "fl_urgent"), exc("P1", "fl_urgent", ALL_MET),
                      ok("P3", "story")]),
    "raj_72h_30s": story("raj_72h_30s", "raj", t(minutes=3, seconds=30, hours=72), {"units_left": 2},
                         [SEARCH, PW_NODROP, PW_NODROP_EMAIL, FL_URGENT],
                         [ok("U1", "fl_urgent"), ok("U3", "fl_urgent"),
                          bad("P1", "fl_urgent", conditions=[["a", "not_met"], ["b", "met"], ["c", "met"], ["scope", "met"]]),
                          ok("P3", "story")]),
    "raj_72h_1m": story("raj_72h_1m", "raj", t(minutes=4, hours=72), {"units_left": 2},
                        [SEARCH, PW_NODROP, PW_NODROP_EMAIL, FL_URGENT],
                        [ok("U1", "fl_urgent"), ok("U3", "fl_urgent"),
                         bad("P1", "fl_urgent", conditions=[["a", "not_met"], ["b", "met"], ["c", "met"], ["scope", "met"]]),
                         ok("P3", "story")]),
    "kai": story("kai", "kai", t(hours=30), {"units_left": 2}, [SEARCH, PW_CARD, PW_EMAIL, FL_URGENT],
                 [ok("U1", "fl_urgent"), ok("U3", "pw_card"), ok("U3", "pw_email"), ok("U3", "fl_urgent"), exc("P1", "fl_urgent", ALL_MET),
                  bad("P2", P2, label="conflict"), ok("P3", "story")]),
    "hana": story("hana", "hana", t(days=181), {"units_left": 2}, [SEARCH, PW_NODROP, PW_NODROP_EMAIL, FL_URGENT],
                  [ok("U1", "fl_urgent"), ok("U3", "fl_urgent"),
                   bad("P1", "fl_urgent", conditions=[["a", "not_met"], ["b", "met"], ["c", "met"], ["scope", "met"]]),
                   ok("P3", "story")]),
    "omar": story("omar", "omar", t(hours=20), {"units_left": 9}, [SEARCH, PW_NODROP, PW_NODROP_EMAIL, FL_URGENT],
                  [bad("U1", "fl_urgent"), ok("U3", "fl_urgent"),
                   bad("P1", "fl_urgent", conditions=[["a", "met"], ["b", "not_met"], ["c", "met"], ["scope", "met"]]),
                   ok("P3", "story")]),
    "sam_alex": story("sam_alex", "sam_alex", t(days=42, hours=-2), {"units_left": 2, "fee_total": 18},
                      [SEARCH, PW_CARD, PW_EMAIL, FL_BANNER, act("a_buy_lock", t(minutes=4), "buy_lock", lock="held"),
                       msg("fl_checkout", t(minutes=4, seconds=5), "fare_lock", "checkout", "page", "fl.checkout.lock")],
                      [ok("U1", "fl_banner"), bad("U2", "fl_banner"), ok("U2", "fl_checkout"), ok("U3", "pw_card"),
                       ok("U3", "pw_email"), ok("U3", "fl_banner"), bad("P2", P2, label="unexplained_tradeoff"),
                       ok("P3", "story")]),
    "theo": story("theo", "theo", t(days=42, hours=-2), {"units_left": 2},
                  [act("a_open", t(minutes=5), "open_fare"),
                   msg("fl_banner", t(minutes=5, seconds=5), "fare_lock", "fare_detail", "banner", "fl.banner"),
                   BOOK, msg("cg_upgrade", t(hours=3), "concierge", "chat", "chat", "cg.upgrade")],
                  [ok("U1", "fl_banner"), ok("U3", "fl_banner"), ok("U3", "cg_upgrade"), ok("P3", "story")]),
    "rina": story("rina", "rina", t(hours=30), {"units_left": 1},
                  [act("a_open_hotel", t(), "open_hotel"),
                   msg("fl_hotel", t(seconds=5), "fare_lock", "hotel_detail", "banner", "fl.hotel.urgent",
                       component="hotel")],
                  [ok("U1", "fl_hotel"), ok("U3", "fl_hotel"),
                   bad("P1", "fl_hotel", conditions=[["a", "met"], ["b", "met"], ["c", "met"], ["scope", "not_met"]]),
                   ok("P3", "story")], release="2.4.1"),
    "maya_23": story("maya_23", "maya", t(days=42, hours=-2), {"units_left": 2},
                     [SEARCH, act("a_optin", t(seconds=30), "opt_in"),
                      msg("pw_alert", t(minutes=1), "price_watch", "inbox", "email", "pw.card"),
                      act("a_open", t(minutes=3), "open_fare"), BOOK],
                     [ok("U3", "pw_alert"), ok("P3", "story")], release="2.3"),
}

# Gold extraction per copy key: used ONLY by the offline test of the code layer, never by the model.
GOLD = {
    "pw.card": {"message_kind": "directive", "decision": "when_to_book", "action": "wait_for_drop",
                "strength": "suggest", "urgency_cue": "none", "explains_own_tradeoff": False, "claims": []},
    "pw.email.after": {"message_kind": "directive", "decision": "when_to_book", "action": "wait_for_drop",
                       "strength": "suggest", "urgency_cue": "none", "explains_own_tradeoff": False, "claims": []},
    "pw.push.moving": {"message_kind": "information", "decision": "none", "action": "none", "strength": "inform",
                       "urgency_cue": "none", "explains_own_tradeoff": False, "claims": []},
    "pw.card.nodrop": {"message_kind": "information", "decision": "none", "action": "none", "strength": "inform",
                       "urgency_cue": "none", "explains_own_tradeoff": False, "claims": []},
    "fl.banner": {"message_kind": "directive", "decision": "when_to_book", "action": "lock_fare",
                  "strength": "suggest", "urgency_cue": "none", "explains_own_tradeoff": False,
                  "claims": [{"type": "units_left", "value": 2, "unit": "seats"},
                             {"type": "fee_total", "value": 9, "unit": "EUR"}]},
    "fl.banner.urgent": {"message_kind": "directive", "decision": "when_to_book", "action": "book_now",
                         "strength": "urge", "urgency_cue": "U-a", "explains_own_tradeoff": True,
                         "claims": [{"type": "units_left", "value": 2, "unit": "seats"},
                                    {"type": "fee_total", "value": 9, "unit": "EUR"}]},
    "fl.banner.urgent_bare": {"message_kind": "directive", "decision": "when_to_book", "action": "book_now",
                              "strength": "urge", "urgency_cue": "U-c", "explains_own_tradeoff": False,
                              "claims": [{"type": "units_left", "value": 2, "unit": "seats"}]},
    "fl.checkout.lock": {"message_kind": "information", "decision": "none", "action": "none", "strength": "inform",
                         "urgency_cue": "none", "explains_own_tradeoff": False,
                         "claims": [{"type": "fee_total", "value": 18, "unit": "EUR"}]},
    "fl.hotel.urgent": {"message_kind": "directive", "decision": "when_to_book", "action": "book_now",
                        "strength": "urge", "urgency_cue": "U-a", "explains_own_tradeoff": True,
                        "claims": [{"type": "units_left", "value": 1, "unit": "rooms"},
                                   {"type": "fee_total", "value": 9, "unit": "EUR"}]},
    "cg.regret": {"message_kind": "retrospective", "decision": "fare_type", "action": "choose_refundable",
                  "strength": "inform", "urgency_cue": "none", "explains_own_tradeoff": False, "claims": []},
    "cg.reconcile": {"message_kind": "directive", "decision": "when_to_book", "action": "conditional",
                     "strength": "suggest", "urgency_cue": "none", "explains_own_tradeoff": True,
                     "claims": [{"type": "units_left", "value": 2, "unit": "seats"}]},
    "cg.upgrade": {"message_kind": "directive", "decision": "fare_type", "action": "upgrade_to_refundable",
                   "strength": "suggest", "urgency_cue": "none", "explains_own_tradeoff": False,  # README: suggest
                   "claims": [{"type": "fee_total", "value": 30, "unit": "EUR"}]},
}

if __name__ == "__main__":
    for name, s in STORIES.items():
        (HERE / f"{name}.json").write_text(json.dumps(s, indent=1, ensure_ascii=False))
    (HERE / "copy_gold.json").write_text(json.dumps(GOLD, indent=1, ensure_ascii=False))
    print(f"wrote {len(STORIES)} stories + copy_gold.json")
