"""Northbound 2.4 and 2.4.1: one test per README persona. Each drives the scenario through the hooks and the real
routes on simulated time (the times are build.py's) and asserts exactly what the app showed or sent, plus the
oracle values the expected results rest on. Nothing here judges a rule: that is the auditor's job.

Message times are the instant of the request or job: build.py adds a 5 s / 10 s "render" gap after some actions
(a card at 10:00:05 after a 10:00:00 search); the app has no render latency, so its rows are 5 s / 10 s earlier.
"""
from datetime import datetime, timedelta, timezone

import pytest

from nbhelpers import advance, log, outbox, parse, persona, set_clock

D0 = datetime(2026, 11, 2, 10, 0, 0, tzinfo=timezone.utc)
NR = "LIS-BER-NR"


def t(minutes=0, seconds=0, days=0, hours=0):
    return D0 + timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)


def iso(d):
    return d.isoformat()


def at(client, when):
    set_clock(client, iso(when))


def row(when, feature, surface, channel, key, component="flight"):
    return (iso(when), feature, surface, channel, key, component)


def shown(client, tid):
    """Every message the app showed or sent to `tid`, in order; core page chrome left out (tested elsewhere)."""
    return [(r["shown_at"], r["feature"], r["surface"], r["channel"], r["message_key"], r["component"])
            for r in log(client, tid) if r["feature"] != "core"]


def oracle(client, tid):
    return client.get("/api/oracle/booking", params={"traveller": tid}).json()


def seats(client, fare=NR):
    return client.get("/api/oracle/inventory", params={"fare": fare}).json()["seats_left"]


def text_of(client, key):
    return next(r["text"] for r in client.rt.log if r["message_key"] == key)


@pytest.fixture
def c24(make_client):
    return make_client("2.4")


@pytest.fixture
def c241(make_client):
    return make_client("2.4.1")


def world(client, seats_=2, drop=True, **extra):
    r = client.post("/api/test/world", json={"seats": {NR: seats_}, "forecast": {"LIS-BER": {"drop": drop}}, **extra})
    assert r.status_code == 200, r.text


def maya_script(client, h, ask_at=t(days=2, minutes=-58)):
    """Maya: 10:00 search, 10:03 fare, 10:06 books non-refundable without a lock, D2 09:02 asks about the deal."""
    assert client.get("/search", headers=h).status_code == 200
    at(client, t(minutes=3))
    assert client.get(f"/fare/{NR}", headers=h).status_code == 200
    at(client, t(minutes=6))
    assert client.post(f"/checkout/{NR}", headers=h).status_code == 200
    at(client, ask_at)
    return client.post("/api/concierge", headers=h, json={"text": "Did I get a good deal?"}).json()


# ---------------------------------------------------------------------------------------------- 2.4 personas
def test_maya(c24):
    world(c24)
    h = persona(c24, "maya")
    answer = maya_script(c24, h)
    assert answer["message_key"] == "cg.regret" and answer["text"] == "You should have booked a refundable fare."
    assert shown(c24, "maya") == [
        row(t(), "price_watch", "search_results", "card", "pw.card"),
        row(t(minutes=1), "price_watch", "inbox", "email", "pw.email.forecast"),
        row(t(minutes=3), "fare_lock", "fare_detail", "banner", "fl.banner"),
        row(t(hours=2), "price_watch", "inbox", "email", "pw.email.after"),  # after booking: the seeded bug
        row(t(hours=3), "concierge", "chat", "chat", "cg.upgrade"),  # 10:06 + 2h54m; in-app only
        row(t(hours=8), "price_watch", "device", "push", "pw.push.moving"),
        row(t(days=2, minutes=-58), "concierge", "chat", "chat", "cg.regret"),
    ]
    assert [e["headers"]["X-Message-Key"] for e in outbox(c24)] == [
        "pw.email.forecast", "core.email.confirmation", "pw.email.after"]
    assert [e["sent_at"] for e in outbox(c24)] == [iso(t(minutes=1)), iso(t(minutes=6)), iso(t(hours=2))]
    assert [e["headers"]["X-Message-Key"] for e in outbox(c24, "push")] == ["pw.push.moving"]
    assert outbox(c24, "push")[0]["text"] == "Prices on LIS→BER are moving."
    assert text_of(c24, "pw.email.after") == "Keep waiting to book. We'll tell you when prices drop."
    assert text_of(c24, "fl.banner") == ("2 seats left at this fare. Lock it for 48 h for €9 total, "
                                         "for your whole booking.")
    ob = oracle(c24, "maya")
    assert ob["status"] == "booked" and ob["fare_type"] == "non_refundable"
    assert ob["departure_at"] == iso(t(days=42, hours=-2)) and ob["booked_at"] == iso(t(minutes=6))
    assert [x["what"] for x in ob["charges"]] == ["fare", "taxes_and_fees"] and ob["fare_lock"] is None
    assert ob["within_change_window"] is False  # D2: the window closed at D1 10:06
    assert seats(c24) == 1


def test_maya_r(c24):
    world(c24)
    h = persona(c24, "maya", experiments={"fare_detail_reconcile": True})
    maya_script(c24, h)
    assert shown(c24, "maya") == [
        row(t(), "price_watch", "search_results", "card", "pw.card"),
        row(t(minutes=1), "price_watch", "inbox", "email", "pw.email.forecast"),
        row(t(minutes=3), "fare_lock", "fare_detail", "banner", "fl.banner"),
        row(t(minutes=3), "concierge", "fare_detail", "card", "cg.reconcile"),  # inline, below the banner
        row(t(hours=2), "price_watch", "inbox", "email", "pw.email.after"),
        row(t(hours=3), "concierge", "chat", "chat", "cg.upgrade"),
        row(t(hours=8), "price_watch", "device", "push", "pw.push.moving"),
        row(t(days=2, minutes=-58), "concierge", "chat", "chat", "cg.regret"),
    ]
    assert text_of(c24, "cg.reconcile") == (
        "Prices on your dates are likely to drop, but this fare has 2 seats left. If you can move your dates, "
        "wait for the alert; if not, locking protects this price.")


def test_the_inline_reconcile_sits_below_the_banner_on_the_page(c24):
    world(c24)
    h = persona(c24, "maya", experiments={"fare_detail_reconcile": True})
    p = parse(c24.get(f"/fare/{NR}", headers=h).text)
    keys = [a["data-message-key"] for _, a in p.markers]
    assert keys.index("fl.banner") < keys.index("cg.reconcile")
    other = persona(c24, "plain")  # no arm: no inline reconcile in 2.4
    assert "cg.reconcile" not in c24.get(f"/fare/{NR}", headers=other).text


def test_lena(c24):
    world(c24)
    h = persona(c24, "lena")
    c24.get("/search", headers=h)
    at(c24, t(minutes=3))
    c24.get(f"/fare/{NR}", headers=h)
    at(c24, t(minutes=4))
    r = c24.post("/api/concierge", headers=h, json={"text": "Book now or wait?"}).json()
    assert r["message_key"] == "cg.reconcile" and r["feature"] == "concierge"
    advance(c24, "2m")  # she leaves without booking
    assert shown(c24, "lena") == [
        row(t(), "price_watch", "search_results", "card", "pw.card"),
        row(t(minutes=1), "price_watch", "inbox", "email", "pw.email.forecast"),
        row(t(minutes=3), "fare_lock", "fare_detail", "banner", "fl.banner"),
        row(t(minutes=4), "concierge", "chat", "chat", "cg.reconcile"),
    ]
    assert oracle(c24, "lena")["status"] == "not_booked"
    assert c24.get("/api/oracle/forecast", params={"route": "LIS-BER"}).json()["drop"] is True and seats(c24) == 2


def test_the_book_now_or_wait_answer_needs_both_offers_live(c24):
    world(c24, drop=False)  # no drop forecast: nothing to reconcile, the 1.0 answer stands
    h = persona(c24, "lena")
    assert c24.post("/api/concierge", headers=h, json={"text": "Book now or wait?"}).json()["message_key"] == "cg.answer.when"
    world(c24, drop=True)
    c24.post(f"/checkout/{NR}", headers=h)  # booked: the offers are no longer live
    assert c24.post("/api/concierge", headers=h, json={"text": "Book now or wait?"}).json()["message_key"] == "cg.answer.when"


def urgent_script(client, h, departure_check=None):
    client.get("/search", headers=h)
    at(client, t(minutes=3))
    client.get(f"/fare/{NR}", headers=h)


def test_raj(c24):
    world(c24, drop=False)
    h = persona(c24, "raj", departure=iso(t(hours=30)), flexible=False)  # fixed dates, departs in 30 h
    urgent_script(c24, h)
    assert shown(c24, "raj") == [
        row(t(), "price_watch", "search_results", "card", "pw.card.nodrop"),
        row(t(minutes=1), "price_watch", "inbox", "email", "pw.email.forecast.nodrop"),
        row(t(minutes=3), "fare_lock", "fare_detail", "banner", "fl.banner.urgent"),
    ]
    assert text_of(c24, "fl.banner.urgent") == (
        "Departing soon: only 2 seats left at this fare. Book now, or lock it for 12 h for €9 total if your "
        "plans might change.")
    assert text_of(c24, "pw.card.nodrop") == "Our forecast: prices on this trip are unlikely to drop before departure."
    assert oracle(c24, "raj")["departure_at"] == iso(t(hours=30)) and seats(c24) == 2


def test_raj_x(c24):
    world(c24, drop=False)
    h = persona(c24, "raj", departure=iso(t(hours=30)), flexible=False, experiments={"fl_urgent_copy": "bare"})
    urgent_script(c24, h)
    assert shown(c24, "raj") == [
        row(t(), "price_watch", "search_results", "card", "pw.card.nodrop"),
        row(t(minutes=1), "price_watch", "inbox", "email", "pw.email.forecast.nodrop"),
        row(t(minutes=3), "fare_lock", "fare_detail", "banner", "fl.banner.urgent_bare"),
    ]
    assert text_of(c24, "fl.banner.urgent_bare") == "Only 2 seats left. Book now."
    assert "fl.banner.urgent\"" not in c24.get(f"/fare/{NR}", headers=h).text


@pytest.mark.parametrize("name, extra, gap", [
    ("raj_72h", timedelta(0), timedelta(hours=72)),
    ("raj_72h_30s", timedelta(seconds=30), timedelta(hours=72, seconds=30)),
    ("raj_72h_1m", timedelta(minutes=1), timedelta(hours=72, minutes=1)),
])
def test_raj_72h_boundaries(c24, name, extra, gap):
    """Fixed dates: the app's own targeting shows the urgent variant at every one of these; whether the exception
    applies at 72 h is for the auditor. The app only has to put the departure exactly `gap` after the banner."""
    world(c24, drop=False)
    departure = t(minutes=3) + timedelta(hours=72) + extra
    h = persona(c24, "raj", departure=iso(departure), flexible=False)
    urgent_script(c24, h)
    banner = [r for r in shown(c24, "raj") if r[4].startswith("fl.")]
    assert banner == [row(t(minutes=3), "fare_lock", "fare_detail", "banner", "fl.banner.urgent")]
    assert shown(c24, "raj")[:2] == [row(t(), "price_watch", "search_results", "card", "pw.card.nodrop"),
                                     row(t(minutes=1), "price_watch", "inbox", "email", "pw.email.forecast.nodrop")]
    shown_at = datetime.fromisoformat(banner[0][0])
    assert datetime.fromisoformat(oracle(c24, "raj")["departure_at"]) - shown_at == gap


@pytest.mark.parametrize("extra, key", [
    (timedelta(0), "fl.banner.urgent"),  # exactly 72 h: within the window (<=)
    (timedelta(seconds=30), "fl.banner"),  # 72 h 00 min 30 s: outside; no rounding or truncation
    (timedelta(minutes=1), "fl.banner"),
    (timedelta(microseconds=1), "fl.banner"),
    (timedelta(seconds=-1), "fl.banner.urgent"),
])
def test_the_app_compares_72h_exactly_for_a_flexible_traveller(c24, extra, key):
    world(c24)
    departure = t(minutes=3) + timedelta(hours=72) + extra
    h = persona(c24, "flex", departure=iso(departure), flexible=True)
    at(c24, t(minutes=3))
    c24.get(f"/fare/{NR}", headers=h)
    assert [r[4] for r in shown(c24, "flex")] == [key]


def test_kai(c24):
    world(c24, drop=True)
    h = persona(c24, "kai", departure=iso(t(hours=30)))  # flexible, departs in 30 h
    urgent_script(c24, h)
    assert shown(c24, "kai") == [
        row(t(), "price_watch", "search_results", "card", "pw.card"),
        row(t(minutes=1), "price_watch", "inbox", "email", "pw.email.forecast"),
        row(t(minutes=3), "fare_lock", "fare_detail", "banner", "fl.banner.urgent"),
    ]
    assert c24.get("/api/oracle/forecast", params={"route": "LIS-BER"}).json()["drop"] is True


def test_hana(c24):
    world(c24, drop=False)
    h = persona(c24, "hana", departure=iso(t(days=181)), flexible=False)  # fixed dates, six months out
    urgent_script(c24, h)
    assert shown(c24, "hana") == [
        row(t(), "price_watch", "search_results", "card", "pw.card.nodrop"),
        row(t(minutes=1), "price_watch", "inbox", "email", "pw.email.forecast.nodrop"),
        row(t(minutes=3), "fare_lock", "fare_detail", "banner", "fl.banner.urgent"),  # the OR: fixed dates alone
    ]
    # build.py: departure = D0 + 181 d, so 181 d - 3 min after the banner (4,343 h 57 min; the README says "about 4,380 h")
    assert datetime.fromisoformat(oracle(c24, "hana")["departure_at"]) - t(minutes=3) == timedelta(days=181, minutes=-3)


def test_omar(c24):
    world(c24, seats_=9, drop=False, bucket_seats={NR: 2})  # inventory 9, the fare bucket says 2
    h = persona(c24, "omar", departure=iso(t(hours=20)))
    urgent_script(c24, h)
    assert shown(c24, "omar") == [
        row(t(), "price_watch", "search_results", "card", "pw.card.nodrop"),
        row(t(minutes=1), "price_watch", "inbox", "email", "pw.email.forecast.nodrop"),
        row(t(minutes=3), "fare_lock", "fare_detail", "banner", "fl.banner.urgent"),
    ]
    assert "only 2 seats left" in text_of(c24, "fl.banner.urgent")
    assert seats(c24) == 9  # the inventory oracle is untouched by the bucket count


def test_the_bucket_count_defaults_to_inventory(c24):
    world(c24, seats_=4)
    h = persona(c24, "x")
    c24.get(f"/fare/{NR}", headers=h)
    assert text_of(c24, "fl.banner").startswith("4 seats left")


def test_sam_and_alex(c24):
    world(c24)
    h = persona(c24, "sam", party=2)
    c24.get("/search", headers=h)
    at(c24, t(minutes=3))
    c24.get(f"/fare/{NR}", headers=h)
    at(c24, t(minutes=4))
    r = c24.post(f"/fare/{NR}/lock", headers=h, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/checkout/{NR}"
    page = c24.get(f"/checkout/{NR}", headers=h)
    assert "Fare Lock (48 h): €18" in page.text
    assert shown(c24, "sam") == [
        row(t(), "price_watch", "search_results", "card", "pw.card"),
        row(t(minutes=1), "price_watch", "inbox", "email", "pw.email.forecast"),
        row(t(minutes=3), "fare_lock", "fare_detail", "banner", "fl.banner"),
        row(t(minutes=4), "fare_lock", "checkout", "page", "fl.checkout.lock"),
    ]
    assert "€9 total, for your whole booking" in text_of(c24, "fl.banner")
    ob = oracle(c24, "sam")
    (lock,) = [x for x in ob["charges"] if x["what"] == "fare_lock"]  # its own line in the booking oracle
    assert lock["amount_cents"] == 1800 and lock["quote_id"] == "q-LIS-BER-NR-2" and lock["transaction"].startswith("txn-")
    assert ob["status"] == "not_booked" and ob["total_cents"] == 1800
    assert ob["fare_lock"] == {"fare_id": NR, "bought_at": iso(t(minutes=4)), "held_until": iso(t(minutes=4, hours=48)),
                               "hours": 48, "held": True}
    assert c24.get(f"/fare/{NR}", headers=h).text.count("fl.banner") == 0  # nothing left to offer: the lock is held
    at(c24, t(minutes=4, hours=48))  # held 48 h; the window is exclusive at the end
    assert oracle(c24, "sam")["fare_lock"]["held"] is False


def test_the_lock_fee_for_a_solo_traveller_is_9_and_the_lock_can_only_be_bought_once(c24):
    world(c24)
    h = persona(c24, "solo")
    c24.post(f"/fare/{NR}/lock", headers=h)
    assert [x["amount_cents"] for x in oracle(c24, "solo")["charges"]] == [900]
    assert c24.post(f"/fare/{NR}/lock", headers=h).status_code == 409
    c24.post(f"/checkout/{NR}", headers=h)
    assert oracle(c24, "solo")["total_cents"] == 900 + 15300  # the lock stays its own line beside the booking
    assert c24.post(f"/fare/{NR}/lock", headers=persona(c24, "late")).status_code == 200
    c24.post(f"/checkout/{NR}", headers={"X-Traveller": "late"})
    assert c24.post(f"/fare/{NR}/lock", headers={"X-Traveller": "late"}).status_code == 409  # booked


def test_the_urgent_variant_holds_for_12_hours(c24):
    world(c24)
    h = persona(c24, "u", departure=iso(t(hours=30)))
    c24.post(f"/fare/{NR}/lock", headers=h)
    assert oracle(c24, "u")["fare_lock"]["hours"] == 12
    assert oracle(c24, "u")["fare_lock"]["held_until"] == iso(t(hours=12))
    assert "Fare Lock (12 h): €9" in c24.get(f"/checkout/{NR}", headers=h).text


def test_theo(c24):
    world(c24)
    h = persona(c24, "theo")
    at(c24, t(minutes=5))
    c24.get(f"/fare/{NR}", headers=h)  # a direct link: no search, so no Price Watch enrolment
    at(c24, t(minutes=6))
    c24.post(f"/checkout/{NR}", headers=h)
    assert c24.get("/api/test/clock").json()["pending_jobs"] == [
        {"id": "j00001", "due": iso(t(hours=3)), "feature": "concierge", "kind": "upgrade_tip", "traveller": "theo"}]
    at(c24, t(hours=3))
    assert shown(c24, "theo") == [
        row(t(minutes=5), "fare_lock", "fare_detail", "banner", "fl.banner"),
        row(t(hours=3), "concierge", "chat", "chat", "cg.upgrade"),
    ]
    assert text_of(c24, "cg.upgrade") == "You can still switch to a refundable fare for €30 until tomorrow 10:05."
    assert [e["headers"]["X-Message-Key"] for e in outbox(c24)] == ["core.email.confirmation"]  # in-app, not a contact
    assert outbox(c24, "push") == []
    ob = oracle(c24, "theo")
    assert ob["within_change_window"] is True and ob["change_window_ends"] == iso(t(minutes=6, days=1))
    chat = c24.get("/concierge", headers=h).text
    assert 'data-feature="concierge" data-message-key="cg.upgrade"' in chat


def test_the_upgrade_tip_is_skipped_once_the_traveller_has_switched_or_the_window_closed(make_client):
    c = make_client(make_client("2.4").rt.release.derive("tip-late", settings={"concierge": {"upgrade_tip_delay": "25h"}}))
    world(c)
    h = persona(c, "a")
    c.post(f"/checkout/{NR}", headers=h)
    advance(c, "26h")
    assert [r for r in shown(c, "a") if r[4] == "cg.upgrade"] == []  # the window (24 h) had closed
    c2 = make_client("2.4")
    world(c2)
    h2 = persona(c2, "b")
    c2.post(f"/checkout/{NR}", headers=h2)
    c2.post("/booking/NB0001/upgrade", headers=h2)
    advance(c2, "5h")
    assert [r for r in shown(c2, "b") if r[4] == "cg.upgrade"] == []


# ------------------------------------------------------------------------------- the rest of 2.4's contract
def test_the_2_3_opt_in_card_is_gone_and_auto_enroll_is_per_traveller_once(c24):
    world(c24)
    h = persona(c24, "maya")
    page = c24.get("/search", headers=h).text
    assert "pw.card.optin" not in page and "pw.card.watching" not in page and 'data-message-key="pw.card"' in page
    c24.get("/search", headers=h)  # searching again does not enrol again
    advance(c24, "9h")
    assert [e["headers"]["X-Message-Key"] for e in outbox(c24)] == ["pw.email.forecast", "pw.email.after"]
    assert c24.post("/action/opt_in", headers=h).status_code == 404  # there is no opt-in step any more


def test_a_booked_traveller_does_not_see_the_price_watch_card_but_followups_still_run_when_not_stopped(c24):
    world(c24)
    h = persona(c24, "maya")
    c24.get("/search", headers=h)
    c24.post(f"/checkout/{NR}", headers=h)
    assert 'data-feature="price_watch"' not in c24.get("/search", headers=h).text
    assert len(c24.get("/api/test/clock").json()["pending_jobs"]) == 4  # forecast email, follow-up, push, upgrade tip


def test_no_drop_forecast_sends_no_keep_waiting_followups(c24):
    world(c24, drop=False)
    h = persona(c24, "n")
    c24.get("/search", headers=h)
    advance(c24, "9h")
    assert [e["headers"]["X-Message-Key"] for e in outbox(c24)] == ["pw.email.forecast.nodrop"]
    assert outbox(c24, "push") == []


def test_hotels_do_not_exist_in_2_4(c24):
    h = persona(c24, "r")
    assert c24.get("/hotel/LIS-H1", headers=h).status_code == 404


def test_2_4_registry_and_feature_order(c24, c241):
    assert [f.id for f in c24.rt.features] == ["core", "price_watch", "fare_lock", "concierge"]
    assert c24.rt.release.name == "2.4" and c241.rt.release.name == "2.4.1"
    assert c24.rt.feature("price_watch").settings["stop_after_booking"] is False
    assert c241.rt.feature("price_watch").settings["stop_after_booking"] is True


# ----------------------------------------------------------------------------------------------- 2.4.1
HOTEL_STAY = {"hotel": "LIS-H1", "check_in_at": iso(t(hours=30)), "nights": 2, "rooms": 1}


def test_rina(c241):
    c241.post("/api/test/world", json={"rooms": {"LIS-H1": 1}})
    h = persona(c241, "rina", departure=iso(t(hours=30)), stay=HOTEL_STAY)
    r = c241.get("/hotel/LIS-H1", headers=h)
    assert r.status_code == 200
    assert shown(c241, "rina") == [row(t(), "fare_lock", "hotel_detail", "banner", "fl.hotel.urgent", "hotel")]
    assert text_of(c241, "fl.hotel.urgent") == (
        "Checking in soon: only 1 room left at this rate. Book now, or hold it for 12 h for €9 total if your "
        "plans might change.")
    assert c241.get("/api/oracle/inventory", params={"hotel": "LIS-H1"}).json() == {"hotel": "LIS-H1", "rooms_left": 1}
    p = parse(r.text)
    assert ("data-feature", "fare_lock") in [kv for _, a in p.markers for kv in a.items()]
    assert any(a.get("data-component") == "hotel" for _, a in p.markers)
    assert [(c["what"]) for c in oracle(c241, "rina")["charges"]] == []  # nothing is charged by looking


def test_the_hotel_banner_follows_check_in_exactly_and_the_oracle(c241):
    c241.post("/api/test/world", json={"rooms": {"LIS-H1": 3}})
    h = persona(c241, "a", stay={**HOTEL_STAY, "check_in_at": iso(t(hours=72))})
    c241.get("/hotel/LIS-H1", headers=h)
    h2 = persona(c241, "b", stay={**HOTEL_STAY, "check_in_at": iso(t(hours=72, seconds=1))})
    c241.get("/hotel/LIS-H1", headers=h2)
    h3 = persona(c241, "c")  # no stay selected
    assert "fl.hotel.urgent" in [r[4] for r in shown(c241, "a")] and shown(c241, "b") == []
    assert c241.get("/hotel/LIS-H1", headers=h3).status_code == 200 and shown(c241, "c") == []
    assert "only 3 rooms left" in text_of(c241, "fl.hotel.urgent")
    assert c241.get("/hotel/NOPE", headers=h).status_code == 404
    assert c241.get("/api/oracle/inventory", params={"hotel": "NOPE"}).status_code == 404
    assert c241.get("/api/oracle/inventory").status_code == 422


def test_maya_on_2_4_1(c241):
    world(c241)
    h = persona(c241, "maya")  # no experiment arm: the reconcile is for everyone now
    maya_script(c241, h)
    assert shown(c241, "maya") == [
        row(t(), "price_watch", "search_results", "card", "pw.card"),
        row(t(minutes=1), "price_watch", "inbox", "email", "pw.email.forecast"),
        row(t(minutes=3), "fare_lock", "fare_detail", "banner", "fl.banner"),
        row(t(minutes=3), "concierge", "fare_detail", "card", "cg.reconcile"),
        row(t(hours=3), "concierge", "chat", "chat", "cg.upgrade"),
        row(t(days=2, minutes=-58), "concierge", "chat", "chat", "cg.regret"),  # not a fix in 2.4.1
    ]
    assert [e["headers"]["X-Message-Key"] for e in outbox(c241)] == ["pw.email.forecast", "core.email.confirmation"]
    assert outbox(c241, "push") == [] and c241.get("/api/test/clock").json()["pending_jobs"] == []


def test_2_4_1_charges_a_couple_the_lock_fee_once_and_keeps_every_other_2_4_behaviour(c241):
    world(c241)
    h = persona(c241, "sam", party=2)
    c241.post(f"/fare/{NR}/lock", headers=h)
    assert [x["amount_cents"] for x in oracle(c241, "sam")["charges"]] == [900]
    hana = persona(c241, "hana", departure=iso(t(days=181)), flexible=False)  # fixed dates still urgent
    c241.get(f"/fare/{NR}", headers=hana)
    assert [r[4] for r in shown(c241, "hana")] == ["fl.banner.urgent", "cg.reconcile"]  # the reconcile is for everyone
    assert c241.rt.feature("fare_lock").settings["urgent_targeting"] == "time_or_fixed_dates"


def test_each_2_4_1_fix_is_one_named_entry_and_removing_it_restores_2_4(make_client, monkeypatch):
    from northbound.releases import r2_4_1
    assert set(r2_4_1.APPLIED_FIXES) == set(r2_4_1.FIXES)
    monkeypatch.setattr(r2_4_1, "APPLIED_FIXES", ["lock_fee_per_booking"])
    c = make_client(r2_4_1.load_release("2.4").derive("2.4.1-partial", settings=r2_4_1._settings()))
    assert c.rt.feature("fare_lock").settings["lock_fee_basis"] == "per_booking"
    assert c.rt.feature("price_watch").settings["stop_after_booking"] is False
    assert c.rt.feature("concierge").settings["fare_detail_reconcile"] == "experiment"
