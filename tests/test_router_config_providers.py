"""Providers from semaudit.toml (`[providers.<name>]`): any OpenAI-compatible endpoint, offline against a mocked httpx.

Pins: the call goes to the configured base_url with the configured key env; a built-in cannot be redefined; an
unpriced model stays unpriced (never $0); a missing key names its env var; an unreadable or non-schema reply from
such a provider is retried and counted, and drives the re-check to not_measurable, never PASS or fix_confirmed;
and the built-in providers send byte-for-byte what they sent before (tests/fixtures/router_golden.json, recorded
before the change by scripts/router_golden.py).
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import router_golden  # noqa: E402
import test_imported_checks as ic  # noqa: E402

from semaudit.decide import memory  # noqa: E402
from semaudit.imported import recheck as rc  # noqa: E402
from semaudit.models import router as R  # noqa: E402

TOML = """
[roles.check_judge]
provider = "myhost"
model = "my-model"

[providers.myhost]
base_url = "https://llm.example.test/v1/"
key_env = "MYHOST_API_KEY"
max_completion_tokens = 4000
"""


def _cfg(tmp_path, text=TOML):
    (tmp_path / "semaudit.toml").write_text(text)
    return tmp_path


class _Replies:
    """httpx.post stand-in: records each call and answers with the next content string."""

    def __init__(self, contents):
        self.contents, self.calls = list(contents), []

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        content = self.contents.pop(0)
        return SimpleNamespace(status_code=200, json=lambda: {
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 100}})


def test_built_in_providers_send_exactly_what_they_sent_before():
    golden = json.loads((ROOT / "tests" / "fixtures" / "router_golden.json").read_text())
    assert router_golden.capture() == golden


def test_a_config_provider_gets_the_call_at_its_url_with_its_key(tmp_path, monkeypatch):
    monkeypatch.setenv("MYHOST_API_KEY", "secret-123")
    post = _Replies(['{"ok": 1}'])
    monkeypatch.setattr(httpx, "post", post)
    r = R.Router(root=_cfg(tmp_path))
    res = r.complete("check_judge", [{"role": "user", "content": "hi"}])
    (call,) = post.calls
    assert call["url"] == "https://llm.example.test/v1/chat/completions"
    assert call["headers"] == {"Authorization": "Bearer secret-123"}
    assert call["json"]["model"] == "my-model" and call["json"]["max_completion_tokens"] == 4000
    assert res.cost_usd is None                                          # unpriced: never $0
    row = json.loads((tmp_path / "runs" / "ledger.jsonl").read_text().splitlines()[-1])
    assert row["priced"] is False and row["cost_usd"] is None
    assert len(list((tmp_path / ".semaudit-cache").glob("*.json"))) == 1


def test_a_config_price_prices_the_model(tmp_path, monkeypatch):
    monkeypatch.setenv("MYHOST_API_KEY", "k")
    monkeypatch.setattr(httpx, "post", _Replies(["x"]))
    r = R.Router(root=_cfg(tmp_path, TOML + '[providers.myhost.prices]\n"my-model" = [0.5, 1.5]\n'), max_usd=1)
    res = r.complete("check_judge", [{"role": "user", "content": "hi"}])
    assert res.cost_usd == pytest.approx((1000 * 0.5 + 100 * 1.5) / 1e6)


def test_an_unpriced_config_model_is_refused_under_a_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("MYHOST_API_KEY", "k")
    post = _Replies(["x"])
    monkeypatch.setattr(httpx, "post", post)
    r = R.Router(root=_cfg(tmp_path), max_usd=1)
    with pytest.raises(R.ModelError, match="no price"):
        r.complete("check_judge", [{"role": "user", "content": "hi"}])
    assert post.calls == []


def test_a_missing_key_names_its_env_var_and_sends_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("MYHOST_API_KEY", raising=False)
    post = _Replies(["x"])
    monkeypatch.setattr(httpx, "post", post)
    r = R.Router(root=_cfg(tmp_path))
    with pytest.raises(R.ModelError, match="MYHOST_API_KEY is not set") as e:
        r.complete("check_judge", [{"role": "user", "content": "hi"}])
    assert "myhost" in str(e.value) and post.calls == []


@pytest.mark.parametrize("name", ["meta", "baseten", "anthropic"])
def test_a_built_in_cannot_be_redefined(tmp_path, name):
    with pytest.raises(R.ConfigError, match="built-in"):
        R.Router(root=_cfg(tmp_path, f'[providers.{name}]\nbase_url = "https://evil.test/v1"\nkey_env = "X"\n'))


@pytest.mark.parametrize("table,match", [
    ('base_url = "ftp://x"\nkey_env = "K"', "base_url"),
    ('base_url = "https://x.test"\nkey_env = "sk-live-abc123"', "key_env"),
    ('base_url = "https://x.test"\nkey_env = "K"\napi_key = "sk"', "unknown keys"),
    ('base_url = "https://x.test"\nkey_env = "K"\nmax_completion_tokens = -1', "positive"),
    ('base_url = "https://x.test"\nkey_env = "K"\n[providers.p.prices]\n"muse-spark-1.3" = [0, 0]', "built-in price"),
    ('base_url = "https://x.test"\nkey_env = "K"\n[providers.p.prices]\n"m" = [1]', "USD per million"),
])
def test_bad_provider_tables_are_refused(tmp_path, table, match):
    with pytest.raises(R.ConfigError, match=match):
        R.Router(root=_cfg(tmp_path, "[providers.p]\n" + table + "\n"))


def test_a_role_on_an_unknown_provider_fails_clearly(tmp_path):
    r = R.Router(root=_cfg(tmp_path, '[roles.check_judge]\nprovider = "nowhere"\nmodel = "m"\n'))
    with pytest.raises(R.ModelError, match="'nowhere' is neither built in"):
        r.complete("check_judge", [{"role": "user", "content": "hi"}])


# ---------- a bad reply from a config provider, driven through the re-check ----------

GOOD = json.dumps({"outcome": "pass", "why": "adds up", "cited": [{"event_id": "m1", "quote": "Total $15.00"}],
                   "record": [{"field": "total", "value": "15.00"}]})


def _recheck(tmp_path, monkeypatch, contents):
    monkeypatch.setenv("MYHOST_API_KEY", "k")
    post = _Replies(contents)
    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(rc, "replay_status", lambda *a, **k: {"status": "succeeded", "reasons": [], "notes": []})
    monkeypatch.setattr(rc, "_story", lambda *a, **k: ic._story())
    monkeypatch.setattr(rc, "record_at", lambda *a, **k: {"record": {"total": 15.0}})
    router = R.Router(root=_cfg(tmp_path))
    res = rc.recheck(ic._check(), ic._ep(), ic.C, ic.SPEC, router, judgments=3, approved=False)
    return res, post


def test_the_path_works_end_to_end_with_good_replies(tmp_path, monkeypatch):
    res, post = _recheck(tmp_path, monkeypatch, [GOOD] * 3)
    assert res["assertion"]["outcome"] == "pass" and res["evidence"]["status"] == "verified"
    assert res["models"]["judging"] == "my-model" and len(post.calls) == 3


def test_unreadable_replies_are_retried_counted_and_never_pass(tmp_path, monkeypatch):
    res, post = _recheck(tmp_path, monkeypatch, ["not json"] * 6)
    assert len(post.calls) == 6                                           # 3 readings x (1 + 1 retry)
    assert res["assertion"]["outcome"] == "not_measurable"
    assert all(j.get("unreadable") for j in res["judgments"])
    rows = [json.loads(x) for x in (tmp_path / "runs" / "ledger.jsonl").read_text().splitlines()]
    # every discarded reply is a ledger row (the router truncates the digest to 16 characters, so the
    # ":unreadable" suffix it appends does not survive into the row; known, and the same for every provider)
    assert len(rows) == 6 and not any(r["cached"] for r in rows)
    base = {**res, "assertion": {"outcome": "fail"}, "evidence": {"status": "verified"}}
    assert memory.check_status(base, res)[0] == "not_confirmed"


@pytest.mark.parametrize("reply", ['{"verdict": "pass"}', '{"outcome": "PASS", "why": "", "cited": [], "record": []}',
                                   json.dumps({**json.loads(GOOD), "extra": "x"})])
def test_non_schema_replies_never_pass(tmp_path, monkeypatch, reply):
    res, post = _recheck(tmp_path, monkeypatch, [reply] * 3)
    assert res["assertion"]["outcome"] == "not_measurable"
    assert all(j.get("nonschema") for j in res["judgments"])
    base = {**res, "assertion": {"outcome": "fail"}, "evidence": {"status": "verified"}}
    assert memory.check_status(base, res)[0] == "not_confirmed"
