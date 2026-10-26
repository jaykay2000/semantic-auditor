"""NC6: Maya on 2.3 opts in to Price Watch at search, gets the forecast alert, books. Nothing competes."""
from northbound.copy import COPY

from nbhelpers import advance, log, log_tuple, outbox, persona, set_clock

T = "2026-11-02T10:0{}:{}+00:00"


def run_nc6(client):
    client.post("/api/test/world", json={"forecast": {"LIS-BER": {"drop": True, "window_days": 14}}})
    h = persona(client, "maya", party=1)  # departs D0 + 42 d - 2 h
    assert client.get("/search", headers=h).status_code == 200  # 10:00:00
    advance(client, "30s")  # 10:00:30
    assert client.post("/action/opt_in", headers=h, data={"next": "/search"}, follow_redirects=False).status_code == 303
    forecast_step = advance(client, "30s")  # 10:01:00: alert is due exactly now (opt-in + 30 s)
    set_clock(client, "2026-11-02T10:03:00Z")
    assert client.get("/fare/LIS-BER-NR", headers=h).status_code == 200
    set_clock(client, "2026-11-02T10:06:00Z")
    booked = client.post("/checkout/LIS-BER-NR", headers=h, follow_redirects=True)
    assert booked.status_code == 200
    return h, forecast_step


def test_nc6_produces_exactly_the_expected_message_log(client):
    h, forecast_step = run_nc6(client)
    assert [j["kind"] for j in forecast_step["jobs_run"]] == ["forecast_alert"]
    assert [log_tuple(r) for r in log(client, "maya")] == [
        # 10:00:00 search results
        (T.format(0, "00"), "core", "search_results", "page", "core.results"),
        (T.format(0, "00"), "core", "search_results", "page", "core.results.fare"),
        (T.format(0, "00"), "core", "search_results", "page", "core.results.fare"),
        (T.format(0, "00"), "price_watch", "search_results", "card", "pw.card.optin"),
        # 10:01:00 the forecast alert email: opt-in (10:00:30) + 30 s
        (T.format(1, "00"), "price_watch", "inbox", "email", "pw.email.forecast"),
        # 10:03:00 fare detail
        (T.format(3, "00"), "core", "fare_detail", "page", "core.fare.summary"),
        (T.format(3, "00"), "core", "fare_detail", "page", "core.fare.policy.non_refundable"),
        # 10:06:00 books: the confirmation email, then the confirmation page
        (T.format(6, "00"), "core", "inbox", "email", "core.email.confirmation"),
        (T.format(6, "00"), "core", "confirmation", "page", "core.confirmed"),
        (T.format(6, "00"), "core", "confirmation", "page", "core.confirmed.fare_window"),
        (T.format(6, "00"), "core", "confirmation", "page", "core.confirmed.charge"),
        (T.format(6, "00"), "core", "confirmation", "page", "core.confirmed.charge"),
        (T.format(6, "00"), "core", "confirmation", "page", "core.confirmed.total"),
    ]


def test_nc6_forecast_email_file_has_the_pw_card_copy_and_both_headers(client):
    run_nc6(client)
    emails = outbox(client, "email")
    forecast = [e for e in emails if e["headers"]["X-Message-Key"] == "pw.email.forecast"]
    assert len(forecast) == 1
    e = forecast[0]
    assert e["headers"] == {"X-Feature": "price_watch", "X-Message-Key": "pw.email.forecast"}
    assert e["sent_at"] == "2026-11-02T10:01:00+00:00"
    assert e["to"] == "maya@example.test"
    assert e["text"] == COPY["pw.card"] == ("Prices on your dates are likely to drop over the next two weeks. "
                                           "We suggest waiting; we'll tell you when to book.")
    assert e["subject"] == "Price Watch: forecast for LIS to BER"
    assert e["text"] in e["html"] and e["message_id"] in {r["id"] for r in log(client)}
    assert (client.outbox / "email" / f"{e['message_id']}.json").exists()
    # the confirmation email: same sink, core's headers
    conf = [e for e in emails if e["headers"]["X-Message-Key"] == "core.email.confirmation"]
    assert len(conf) == 1 and conf[0]["headers"]["X-Feature"] == "core" and conf[0]["sent_at"] == T.format(6, "00")
    assert "Booked." in conf[0]["text"] and "NB0001" in conf[0]["text"]
    assert not list((client.outbox / "push").glob("*.json"))  # 2.3 sends no push


def test_nc6_state_after_booking_and_no_competing_directive(client):
    h, _ = run_nc6(client)
    ob = client.get("/api/oracle/booking", params={"traveller": "maya"}).json()
    assert ob["status"] == "booked" and ob["fare_type"] == "non_refundable"
    assert ob["departure_at"] == "2026-12-14T08:00:00+00:00" and ob["booked_at"] == T.format(6, "00")
    features = {r["feature"] for r in log(client)}
    assert "fare_lock" not in features  # Fare Lock does not exist in 2.3
    assert not any(k.startswith("fl.") for k in (r["message_key"] for r in log(client)))
    # nothing from Price Watch, ever again
    before = len(log(client))
    advance(client, "30d")
    assert [r for r in log(client)[before:] if r["feature"] == "price_watch"] == []
    assert client.get("/api/test/clock").json()["pending_jobs"] == []
