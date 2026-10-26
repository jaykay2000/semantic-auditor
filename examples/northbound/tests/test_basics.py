"""Personas and auth, the simulated clock, the job queue, config."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from nbhelpers import advance, persona, set_clock

D0 = "2026-11-02T10:00:00+00:00"


def test_persona_creation_and_three_ways_to_authenticate(client):
    r = client.post("/api/test/personas", json={
        "id": "sam", "name": "Sam", "travellers": 2, "flexible": True,
        "trip": {"origin": "lis", "destination": "ber", "departure_at": "2026-12-14T08:00:00Z"}})
    body = r.json()
    assert r.status_code == 200 and body["traveller_id"] == "sam"
    assert body["auth"]["cookie"] == "nb_traveller=sam" and body["auth"]["header"] == "X-Traveller: sam"
    assert body["departure_at"] == "2026-12-14T08:00:00+00:00"

    assert client.get("/search").status_code == 401  # nobody
    assert client.get("/search", headers={"X-Traveller": "sam"}).status_code == 200  # header
    assert client.get("/search", params={"traveller": "sam"}).status_code == 200  # query
    client.cookies.set("nb_traveller", "sam")
    assert client.get("/search").status_code == 200  # cookie
    assert "Sam" in client.get("/search").text
    client.cookies.clear()
    assert client.get("/search", headers={"X-Traveller": "nobody"}).status_code == 401


def test_persona_validation(client):
    persona(client, "maya")
    again = client.post("/api/test/personas", json={"id": "maya", "trip": {
        "origin": "LIS", "destination": "BER", "departure_at": "2026-12-14T08:00:00Z"}})
    assert again.status_code == 409
    bad_party = client.post("/api/test/personas", json={"id": "x", "travellers": 3, "trip": {
        "origin": "LIS", "destination": "BER", "departure_at": "2026-12-14T08:00:00Z"}})
    assert bad_party.status_code == 422
    naive = client.post("/api/test/personas", json={"id": "y", "trip": {
        "origin": "LIS", "destination": "BER", "departure_at": "2026-12-14T08:00:00"}})
    assert naive.status_code == 422  # no zone, no guessing
    assert client.post("/api/test/personas", json={"id": "z"}).status_code == 422


def test_clock_starts_at_d0_and_a_30s_advance_moves_exactly_30s(client):
    assert client.get("/api/test/clock").json()["now"] == D0
    assert advance(client, "30s")["now"] == "2026-11-02T10:00:30+00:00"
    assert advance(client, "30s")["now"] == "2026-11-02T10:01:00+00:00"  # seconds accumulate, never rounded
    assert advance(client, "1d2h")["now"] == "2026-11-03T12:01:00+00:00"
    assert client.rt.now == datetime(2026, 11, 3, 12, 1, 0, tzinfo=timezone.utc)


def test_clock_set_keeps_seconds_and_converts_offsets_to_utc(client):
    assert set_clock(client, "2026-11-02T10:06:07Z")["now"] == "2026-11-02T10:06:07+00:00"
    assert set_clock(client, "2026-11-02T11:06:07+01:00")["now"] == "2026-11-02T10:06:07+00:00"


@pytest.mark.parametrize("body", [{"advance": "soon"}, {"advance": ""}, {"advance": "1w"}, {"advance": "-5m"},
                                  {"set": "2026-11-02T10:00:00"}, {"set": "tomorrow"}, {}])
def test_clock_rejects_bad_input(client, body):
    assert client.post("/api/test/clock", json=body).status_code == 422
    assert client.get("/api/test/clock").json()["now"] == D0  # unchanged


def test_jobs_run_in_due_order_with_the_clock_at_their_due_time(client, tmp_path, monkeypatch):
    pkg = tmp_path / "fakepkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "order_feature.py").write_text('''
from northbound.features import BaseFeature
SEEN = []
class Feature(BaseFeature):
    id = "order"
    def on_action(self, action, ctx, data):
        if action == "search":
            ctx.schedule(self.id, "second", delay="2h")   # scheduled first, due last
            ctx.schedule(self.id, "first", delay="1h30m")
            ctx.schedule(self.id, "third", delay="2h")    # ties keep scheduling order
    def on_job(self, job, ctx):
        SEEN.append((job.kind, ctx.now.isoformat()))
''')
    monkeypatch.syspath_prepend(str(tmp_path))
    from northbound.releases import load_release
    base = load_release("2.3")
    from conftest import Config, create_app, TestClient
    app = create_app(Config(outbox_dir=tmp_path / "o"), base.derive("order", add=["fakepkg.order_feature"]))
    cl = TestClient(app)
    h = persona(cl)
    cl.get("/search", headers=h)
    out = advance(cl, "3h")
    assert [j["kind"] for j in out["jobs_run"]] == ["first", "second", "third"]
    import fakepkg.order_feature as m
    assert m.SEEN == [("first", "2026-11-02T11:30:00+00:00"), ("second", "2026-11-02T12:00:00+00:00"),
                      ("third", "2026-11-02T12:00:00+00:00")]
    assert cl.get("/api/test/clock").json()["pending_jobs"] == []


def test_reset_wipes_state_outbox_and_clock(client):
    h = persona(client)
    client.post("/action/opt_in", headers=h)
    advance(client, "2m")
    assert list((client.outbox / "email").glob("*.json"))
    client.post("/api/test/reset")
    assert client.get("/api/test/clock").json() == {"now": D0, "pending_jobs": []}
    assert not list((client.outbox / "email").glob("*.json"))
    assert client.get("/api/test/messages").json()["messages"] == []
    assert client.get("/search", headers=h).status_code == 401  # travellers wiped too


def test_message_log_is_labelled_debug_only(client):
    body = client.get("/api/test/messages").json()
    assert body["debug_only"] is True


def test_release_name_is_read_in_exactly_one_place():
    root = Path(__file__).resolve().parent.parent / "northbound"
    offenders = []
    for path in root.rglob("*.py"):
        text = path.read_text()
        if path.name != "config.py" and ("os.environ" in text or "getenv" in text or "NORTHBOUND_RELEASE" in text):
            offenders.append(str(path.relative_to(root)))
    assert offenders == []
