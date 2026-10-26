"""Releases are plugins: behaviour changes by settings, copy and feature modules, with no core edits."""
import pytest

from northbound.releases import Release, load_release, module_name, register_release

from nbhelpers import advance, log, outbox, persona


def test_2_3_is_the_default_release_and_module_names_map(client):
    assert client.rt.release.name == "2.3"
    assert [f.id for f in client.rt.features] == ["core", "price_watch", "concierge"]
    assert [module_name(n) for n in ("2.3", "2.4", "2.4.1", "bench-01")] == ["r2_3", "r2_4", "r2_4_1", "bench_01"]
    with pytest.raises(ValueError, match="unknown Northbound release"):
        load_release("9.9")


def test_a_release_without_price_watch_changes_behaviour_with_no_core_edit(make_client):
    c = make_client(load_release("2.3").derive("no-pw", remove=["price_watch"]))
    h = persona(c)
    page = c.get("/search", headers=h).text
    assert 'data-feature="price_watch"' not in page and 'data-feature="core"' in page
    assert c.post("/action/opt_in", headers=h).status_code == 404  # nobody handles it
    advance(c, "7d")
    assert outbox(c) == [] and c.get("/api/test/clock").json()["pending_jobs"] == []


def test_a_setting_changes_when_the_alert_is_sent(make_client):
    c = make_client(load_release("2.3").derive("slow-alert", settings={"price_watch": {"alert_delay": "90s"}}))
    h = persona(c)
    c.post("/action/opt_in", headers=h)
    advance(c, "89s")
    assert outbox(c) == []
    advance(c, "1s")
    (e,) = outbox(c)
    assert e["sent_at"] == "2026-11-02T10:01:30+00:00"


def test_stop_after_booking_is_a_setting(make_client):  # the cancel is configuration, not a hard-wired rule
    c = make_client(load_release("2.3").derive("keeps-going", settings={"price_watch": {"stop_after_booking": False}}))
    h = persona(c)
    c.post("/action/opt_in", headers=h)
    c.post("/checkout/LIS-BER-NR", headers=h)
    advance(c, "1h")
    assert [e["headers"]["X-Message-Key"] for e in outbox(c)] == ["core.email.confirmation", "pw.email.forecast"]


def test_copy_can_be_overridden_and_extended_per_release(make_client):
    c = make_client(load_release("2.3").derive("copy", copy={"core.results": "Found {n} flights.", "x.new": "new"}))
    h = persona(c)
    assert "Found 2 flights." in c.get("/search", headers=h).text
    assert c.rt.copy["x.new"] == "new"


def test_unsupported_price_watch_mode_fails_loudly(make_client):
    with pytest.raises(ValueError, match="not implemented"):
        make_client(load_release("2.3").derive("auto", settings={"price_watch": {"mode": "auto_enroll"}}))


def test_concierge_1_0_cannot_be_made_proactive_by_a_setting(make_client):
    with pytest.raises(ValueError, match="never proactive"):
        make_client(load_release("2.3").derive("pushy", settings={"concierge": {"proactive": True}}))


def test_release_must_keep_core(make_client):
    with pytest.raises(ValueError, match="core"):
        make_client(Release(name="no-core", features=["price_watch"]))


def test_a_new_feature_module_plugs_in_without_touching_core(make_client, tmp_path, monkeypatch):
    pkg = tmp_path / "plugins"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "banner_feature.py").write_text('''
from northbound.features import BaseFeature
class Feature(BaseFeature):
    id = "fare_lock"
    DEFAULTS = {"text_key": "fl.test"}
    COPY = {"fl.test": "A new feature says: {n} seats."}
    def messages_for(self, surface, ctx):
        if surface == "fare_detail":
            return [self.msg(ctx, self.settings["text_key"], surface, "banner", n=2)]
        return []
    def on_action(self, action, ctx, data):
        if action == "book":
            ctx.send_push(self.id, "fl.test", n=2)
''')
    monkeypatch.syspath_prepend(str(tmp_path))
    c = make_client(register_release(load_release("2.3").derive("plugin-test", add=["plugins.banner_feature"])))
    h = persona(c)
    page = c.get("/fare/LIS-BER-NR", headers=h).text
    assert 'data-feature="fare_lock"' in page and 'data-message-key="fl.test"' in page
    c.post("/checkout/LIS-BER-NR", headers=h)
    (push,) = outbox(c, "push")
    assert push["headers"] == {"X-Feature": "fare_lock", "X-Message-Key": "fl.test"}
    assert push["text"] == "A new feature says: 2 seats."
    assert {"fare_lock"} <= {r["feature"] for r in log(c)}
