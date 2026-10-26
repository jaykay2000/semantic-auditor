"""The marker sweep: every message element carries data-feature + data-message-key + data-shown-at, every key
exists in the copy table, every feature id is in the contract, and no message text sits outside the macro."""
import io
from pathlib import Path

import pdfplumber
import yaml

from nbhelpers import advance, parse, persona, set_clock

FEATURES = {f["id"] for f in yaml.safe_load(
    (Path(__file__).resolve().parent.parent / "contract" / "features.yaml").read_text())}
CHROME_TAGS = {"h1", "h2", "h3", "label", "button", "a"}
QUESTIONS = ["What is my booking status?", "Can I get a refund?", "Did I get a good deal?",
             "Book now or wait?", "What is Price Watch?", "tell me a joke"]


def check_page(client, url, headers, *, exact=True, expect_status=(200,), method="get"):
    n = len(client.rt.log)
    r = getattr(client, method)(url, headers=headers, follow_redirects=True)
    assert r.status_code in expect_status, (url, r.status_code)
    p = parse(r.text)
    logged = [(row["feature"], row["message_key"]) for row in client.rt.log[n:]]
    marked = [(a.get("data-feature"), a.get("data-message-key")) for _, a in p.markers]
    for tag, a in p.markers + p.msg_class_elements:
        assert a.get("data-feature"), (url, tag, a)
        assert a.get("data-message-key"), (url, tag, a)
        assert a.get("data-shown-at"), (url, tag, a)
        assert a["data-feature"] in FEATURES, (url, a)
        assert a["data-message-key"] in client.rt.copy, (url, a)
    for text, stack in p.text_nodes:  # nothing the product says may bypass the macro
        ok = any("data-message-key" in a or t in CHROME_TAGS or "user-turn" in (a.get("class") or "").split()
                 for t, a in stack)
        assert ok, (url, text)
    if exact:
        assert sorted(marked) == sorted(logged), (url, marked, logged)  # what is shown == what is logged
    else:
        assert not (set(logged) - set(marked)), (url, logged, marked)
    return r, len(marked)


def sweep(client, headers, booking_id=None):
    shown = 0
    for url in ["/search", "/fare/LIS-BER-NR", "/fare/LIS-BER-RF", "/checkout/LIS-BER-NR", "/checkout/LIS-BER-RF"]:
        shown += check_page(client, url, headers)[1]
    for q in QUESTIONS:
        client.post("/api/concierge", headers=headers, json={"text": q})
    shown += check_page(client, "/concierge", headers, exact=False)[1]
    if booking_id:
        shown += check_page(client, f"/booking/{booking_id}", headers)[1]
    return shown


def test_unbooked_traveller_sweep(client):
    h = persona(client)
    assert sweep(client, h) >= 12
    client.post("/action/opt_in", headers=h)
    check_page(client, "/search", headers=h)  # the "watching" variant
    client.post("/api/test/world", json={"seats": {"LIS-BER-NR": 0}})
    check_page(client, "/checkout/LIS-BER-NR", headers=h)  # the sold-out variant


def test_booked_traveller_sweep_including_blocked_and_closed_variants(client):
    h = persona(client)
    client.post("/checkout/LIS-BER-NR", headers=h)
    assert sweep(client, h, "NB0001") >= 18
    check_page(client, "/checkout/LIS-BER-RF", headers=h)  # "already booked" variant
    advance(client, "25h")
    check_page(client, "/booking/NB0001", headers=h)  # window-closed variant
    h2 = persona(client, "kai")
    client.post("/checkout/LIS-BER-RF", headers=h2)
    check_page(client, "/booking/NB0002", headers=h2)  # refundable variant


def test_the_sweep_would_catch_an_unmarked_message(client):  # guard on the guard
    h = persona(client)
    html = client.get("/search", headers=h).text.replace('data-message-key="pw.card.optin"', "")
    p = parse(html)
    bad = [a for _, a in p.msg_class_elements if not a.get("data-message-key")]
    assert len(bad) == 1


def test_every_copy_key_in_a_log_exists_in_the_table(client):
    h = persona(client)
    sweep(client, h)
    assert {r["message_key"] for r in client.rt.log} <= set(client.rt.copy)


def test_itinerary_pdf_has_keys_in_metadata_and_extractable_text(client):
    h = persona(client)
    set_clock(client, "2026-11-02T10:06:00Z")
    client.post("/checkout/LIS-BER-NR", headers=h)
    r = client.get("/booking/NB0001/itinerary.pdf", headers=h)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:5] == b"%PDF-"
    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        keys = {k.strip() for k in pdf.metadata["Keywords"].split(",")}
        text = " ".join(page.extract_text() for page in pdf.pages)
    assert keys == {"core.pdf.itinerary", "core.pdf.charge", "core.pdf.total"} and keys <= set(client.rt.copy)
    assert "Booked: NB0001" in text and "Lisbon (LIS) to Berlin (BER)" in text
    assert "Total charged: €153" in text and "Taxes and fees: €24" in text
    rows = [row for row in client.rt.log if row["channel"] == "pdf"]  # logged like every other message
    assert {row["message_key"] for row in rows} == keys
    assert {row["shown_at"] for row in rows} == {"2026-11-02T10:06:00+00:00"}


def test_pages_are_for_the_owner_only(client):
    h = persona(client, "a")
    other = persona(client, "b")
    client.post("/checkout/LIS-BER-NR", headers=h)
    assert client.get("/booking/NB0001/itinerary.pdf", headers=other).status_code == 404
    assert client.get("/booking/NB0001", headers=other).status_code == 404


def test_concierge_answers_are_deterministic_and_never_proactive(client):
    h = persona(client)
    first = [client.post("/api/concierge", headers=h, json={"text": q}).json()["message_key"] for q in QUESTIONS]
    second = [client.post("/api/concierge", headers=h, json={"text": q}).json()["message_key"] for q in QUESTIONS]
    assert first == second == ["cg.answer.status.none", "cg.answer.refund", "cg.answer.deal.none", "cg.answer.when",
                               "cg.answer.price_watch", "cg.answer.fallback"]
    client.post("/checkout/LIS-BER-NR", headers=h)
    advance(client, "10d")
    assert [r for r in client.rt.log if r["feature"] == "concierge" and r["channel"] != "chat"] == []
    assert "cg.regret" not in {r["message_key"] for r in client.rt.log}  # 2.3 never second-guesses
    assert client.post("/api/concierge", headers=h, json={"text": "  "}).status_code == 422
