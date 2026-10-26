"""Oracles: booking (status, charges, change window computed from the sim clock), inventory, forecast."""
from nbhelpers import advance, persona, set_clock


def oracle(client, tid="maya"):
    return client.get("/api/oracle/booking", params={"traveller": tid}).json()


def test_booking_oracle_before_and_after_booking(client):
    h = persona(client)
    before = oracle(client)
    assert before["status"] == "not_booked" and before["charges"] == [] and before["within_change_window"] is False
    assert before["departure_at"] == "2026-12-14T08:00:00+00:00"

    set_clock(client, "2026-11-02T10:06:00Z")
    client.post("/checkout/LIS-BER-NR", headers=h)
    after = oracle(client)
    assert after["status"] == "booked" and after["fare_type"] == "non_refundable" and after["party"] == 1
    assert [(c["what"], c["amount_cents"]) for c in after["charges"]] == [("fare", 12900), ("taxes_and_fees", 2400)]
    assert all(c["currency"] == "EUR" and c["transaction"] == "txn-NB0001" for c in after["charges"])
    assert after["total_cents"] == 15300
    assert after["booked_at"] == "2026-11-02T10:06:00+00:00"
    assert after["change_window_ends"] == "2026-11-03T10:06:00+00:00"


def test_change_window_is_24h_from_booking_computed_from_the_clock(client):
    h = persona(client)
    set_clock(client, "2026-11-02T10:06:00Z")
    client.post("/checkout/LIS-BER-NR", headers=h)
    assert oracle(client)["within_change_window"] is True
    advance(client, "23h59m59s")
    assert oracle(client)["within_change_window"] is True
    advance(client, "1s")  # exactly 24 h: still inside (inclusive)
    assert oracle(client)["within_change_window"] is True
    advance(client, "1s")
    assert oracle(client)["within_change_window"] is False


def test_party_size_changes_the_totals(client):  # NC4: persona-specific facts
    solo = persona(client, "solo", party=1)
    family = persona(client, "family", party=4)
    client.post("/checkout/LIS-BER-NR", headers=solo)
    client.post("/checkout/LIS-BER-NR", headers=family)
    assert oracle(client, "solo")["total_cents"] == 15300
    assert oracle(client, "family")["total_cents"] == 4 * 15300
    assert oracle(client, "family")["party"] == 4


def test_upgrade_inside_the_window_adds_a_30_euro_charge_and_after_it_is_refused(client):
    a, b = persona(client, "a"), persona(client, "b")
    client.post("/checkout/LIS-BER-NR", headers=a)
    client.post("/checkout/LIS-BER-NR", headers=b)
    assert client.post("/booking/NB0001/upgrade", headers=a, follow_redirects=False).status_code == 303
    ob = oracle(client, "a")
    assert ob["fare_type"] == "refundable" and ob["charges"][-1]["what"] == "upgrade_to_refundable"
    assert ob["charges"][-1]["amount_cents"] == 3000 and ob["total_cents"] == 15300 + 3000
    advance(client, "24h1s")
    assert client.post("/booking/NB0002/upgrade", headers=b).status_code == 409
    assert oracle(client, "b")["fare_type"] == "non_refundable" and oracle(client, "b")["total_cents"] == 15300


def test_inventory_oracle_follows_world_and_bookings(client):
    assert client.get("/api/oracle/inventory", params={"fare": "LIS-BER-NR"}).json() == {"fare": "LIS-BER-NR", "seats_left": 9}
    client.post("/api/test/world", json={"seats": {"LIS-BER-NR": 2}})
    h = persona(client, party=2)
    assert client.get("/api/oracle/inventory", params={"fare": "LIS-BER-NR"}).json()["seats_left"] == 2
    client.post("/checkout/LIS-BER-NR", headers=h)
    assert client.get("/api/oracle/inventory", params={"fare": "LIS-BER-NR"}).json()["seats_left"] == 0
    assert client.get("/api/oracle/inventory", params={"fare": "nonsense"}).status_code == 404


def test_sold_out_blocks_checkout(client):
    client.post("/api/test/world", json={"seats": {"LIS-BER-NR": 1}})
    h = persona(client, party=2)
    page = client.get("/checkout/LIS-BER-NR", headers=h)
    assert "core.checkout.soldout" in page.text and "Book this fare" not in page.text
    assert client.post("/checkout/LIS-BER-NR", headers=h).status_code == 409
    assert oracle(client)["status"] == "not_booked"


def test_one_booking_per_traveller(client):
    h = persona(client)
    client.post("/checkout/LIS-BER-NR", headers=h)
    again = client.post("/checkout/LIS-BER-RF", headers=h)
    assert again.status_code == 409 and "core.checkout.already" in again.text


def test_forecast_oracle(client):
    assert client.get("/api/oracle/forecast", params={"route": "LIS-BER"}).json() == {
        "route": "LIS-BER", "drop": True, "window_days": 14}
    client.post("/api/test/world", json={"forecast": {"LIS-BER": {"drop": False, "window_days": 14}}})
    assert client.get("/api/oracle/forecast", params={"route": "lis-ber"}).json()["drop"] is False


def test_oracle_unknown_traveller_is_404(client):
    assert client.get("/api/oracle/booking", params={"traveller": "ghost"}).status_code == 404


def test_refundable_fare_costs_more(client):
    h = persona(client)
    client.post("/checkout/LIS-BER-RF", headers=h)
    ob = oracle(client)
    assert ob["fare_type"] == "refundable" and ob["total_cents"] == 21300
