"""Price Watch 1.0: opt-in, one alert, before booking only; booking stops every job."""
from nbhelpers import advance, log, outbox, persona, set_clock


def pw_rows(client):
    return [r for r in log(client) if r["feature"] == "price_watch"]


def test_booking_cancels_price_watch_jobs(client):
    h = persona(client)
    client.get("/search", headers=h)
    client.post("/action/opt_in", headers=h)
    assert len(client.get("/api/test/clock").json()["pending_jobs"]) == 1  # the alert, due at +30 s
    client.post("/checkout/LIS-BER-NR", headers=h)  # books before the alert is due
    assert client.get("/api/test/clock").json()["pending_jobs"] == []
    advance(client, "7d")
    assert [r for r in pw_rows(client) if r["channel"] in ("email", "push")] == []
    assert [e for e in outbox(client) if e["headers"]["X-Feature"] == "price_watch"] == []


def test_without_booking_the_alert_does_arrive(client):  # the positive control for the test above
    h = persona(client)
    client.post("/action/opt_in", headers=h)
    advance(client, "7d")
    sent = [e for e in outbox(client) if e["headers"]["X-Feature"] == "price_watch"]
    assert len(sent) == 1 and sent[0]["sent_at"] == "2026-11-02T10:00:30+00:00"  # opt-in at 10:00:00 + 30 s


def test_opting_in_twice_schedules_one_alert(client):
    h = persona(client)
    client.post("/action/opt_in", headers=h)
    client.post("/action/opt_in", headers=h)
    advance(client, "1h")
    assert len([e for e in outbox(client) if e["headers"]["X-Feature"] == "price_watch"]) == 1


def test_opt_in_after_booking_is_refused_and_the_card_is_gone(client):
    h = persona(client)
    client.post("/checkout/LIS-BER-NR", headers=h)
    r = client.post("/action/opt_in", headers=h)
    assert r.status_code == 409
    assert client.get("/api/test/clock").json()["pending_jobs"] == []
    assert "data-feature=\"price_watch\"" not in client.get("/search", headers=h).text  # before booking only


def test_card_offers_then_confirms_opt_in(client):
    h = persona(client)
    assert "pw.card.optin" in client.get("/search", headers=h).text
    client.post("/action/opt_in", headers=h)
    page = client.get("/search", headers=h).text
    assert "pw.card.watching" in page and "pw.card.optin" not in page


def test_forecast_says_no_drop(client):
    client.post("/api/test/world", json={"forecast": {"LIS-BER": {"drop": False}}})
    h = persona(client)
    client.post("/action/opt_in", headers=h)
    advance(client, "1m")
    (e,) = [e for e in outbox(client) if e["headers"]["X-Feature"] == "price_watch"]
    assert e["headers"]["X-Message-Key"] == "pw.email.forecast.nodrop"
    assert e["text"] == "Our forecast: prices on this trip are unlikely to drop before departure."
