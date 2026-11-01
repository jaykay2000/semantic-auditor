"""Providers from semaudit.toml (`[providers.<name>]`): any OpenAI-compatible endpoint, offline against a mocked httpx.

Pins: the call goes to the configured base_url with the configured key env; a built-in cannot be redefined; an
unpriced model stays unpriced (never $0), even when a built-in provider prices a model of the same name; a missing key names its env var; an unreadable or non-schema reply from
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
    assert row["priced"] is False and row["cost_usd"] is None and row["provider"] == "myhost"
    assert len(list((tmp_path / ".semaudit-cache").glob("*.json"))) == 1


def test_a_config_price_prices_the_model(tmp_path, monkeypatch):
    monkeypatch.setenv("MYHOST_API_KEY", "k")
    monkeypatch.setattr(httpx, "post", _Replies(["x"]))
    r = R.Router(root=_cfg(tmp_path, TOML + '[providers.myhost.prices]\n"my-model" = [0.5, 1.5]\n'), max_usd=1)
    res = r.complete("check_judge", [{"role": "user", "content": "hi"}])
    assert res.cost_usd == pytest.approx((1000 * 0.5 + 100 * 1.5) / 1e6)


# A model name that a built-in provider prices (Baseten's Muse Spark Open), served through a config provider
SAME_NAME = TOML.replace('model = "my-model"', 'model = "meta-models/muse-spark-open-1026"')


def test_a_config_provider_never_inherits_a_built_in_price(tmp_path, monkeypatch):
    monkeypatch.setenv("MYHOST_API_KEY", "k")
    post = _Replies(["x"])
    monkeypatch.setattr(httpx, "post", post)
    res = R.Router(root=_cfg(tmp_path, SAME_NAME)).complete("check_judge", [{"role": "user", "content": "hi"}])
    assert R.PRICES_PER_MTOK["meta-models/muse-spark-open-1026"] is not None     # Baseten's price exists
    assert res.cost_usd is None                                                    # but is not this provider's
    row = json.loads((tmp_path / "runs" / "ledger.jsonl").read_text().splitlines()[-1])
    assert row["priced"] is False and row["provider"] == "myhost"
    with pytest.raises(R.ModelError, match="no price"):                            # and a cap refuses it
        R.Router(root=_cfg(tmp_path, SAME_NAME), max_usd=1).complete("check_judge", [{"role": "user", "content": "x"}])
    assert len(post.calls) == 1


def test_a_config_provider_prices_a_built_in_model_name_its_own_way(tmp_path, monkeypatch):
    monkeypatch.setenv("MYHOST_API_KEY", "k")
    monkeypatch.setattr(httpx, "post", _Replies(["x"]))
    text = SAME_NAME + '[providers.myhost.prices]\n"meta-models/muse-spark-open-1026" = [0.1, 0.2]\n'
    r = R.Router(root=_cfg(tmp_path, text), max_usd=1)
    res = r.complete("check_judge", [{"role": "user", "content": "hi"}])
    assert res.cost_usd == pytest.approx((1000 * 0.1 + 100 * 0.2) / 1e6)
    assert r.prices["meta-models/muse-spark-open-1026"] == R.PRICES_PER_MTOK["meta-models/muse-spark-open-1026"]


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
    assert len(rows) == 6 and not any(r["cached"] for r in rows)
    assert all(r["discarded"] is True and r["discard_reason"] == "unreadable" for r in rows)
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


# ---------- the ledger marks discarded replies; totals are unchanged ----------

def _spent_as_the_bench_scripts_sum_it(rows):
    """scripts/w13b_bench.py and w13c_postfix.py `_spent()`: every uncached row's cost_usd."""
    return sum(r["cost_usd"] or 0 for r in rows if not r["cached"])


def test_a_discarded_reply_is_marked_and_totals_are_the_same_in_old_and_new_format(tmp_path, monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", "k")
    monkeypatch.setattr(httpx, "post", _Replies(["not json", '{"ok": 1}', '{"ok": 1}']))
    r = R.Router(root=tmp_path)
    r.roles["t"] = {"provider": "baseten", "model": "meta-models/muse-spark-open-1026"}
    schema = {"type": "object", "properties": {"ok": {"type": "integer"}}, "required": ["ok"],
              "additionalProperties": False}
    r.complete("t", [{"role": "user", "content": "a"}], schema=schema, fresh=True)   # 1 discarded + 1 kept
    r.complete("t", [{"role": "user", "content": "a"}], schema=schema)                # cache hit
    r.complete("t", [{"role": "user", "content": "b"}], schema=schema, fresh=True)   # kept
    new = [json.loads(x) for x in (tmp_path / "runs" / "ledger.jsonl").read_text().splitlines()]
    assert [x.get("discarded", False) for x in new] == [True, False, False, False]
    assert new[0]["discard_reason"] == "unreadable" and new[0]["digest"] == new[1]["digest"]
    assert all("discard_reason" not in x for x in new[1:])                            # normal rows unchanged
    assert all("provider" not in x for x in new)                                      # built-in rows: no new field
    old = [{k: v for k, v in x.items() if k not in ("discarded", "discard_reason")} for x in new]
    assert _spent_as_the_bench_scripts_sum_it(old) == _spent_as_the_bench_scripts_sum_it(new)
    assert _spent_as_the_bench_scripts_sum_it(new) == pytest.approx(r.spent_usd)
    assert r.spent_usd == pytest.approx(3 * (1000 * 1.25 + 100 * 4.25) / 1e6)       # the discarded call is charged


# ---------- R2-01: a hostile or careless endpoint cannot exfiltrate the key through SRA's own files or errors ----------

SECRET = "sk-test-SENTINEL-0123456789"


class _Reflect:
    """An endpoint that echoes the bearer value it received: in the reply body, or in a non-200 error."""

    def __init__(self, status=200):
        self.status = status

    def __call__(self, url, json=None, headers=None, timeout=None):
        got = headers["Authorization"].removeprefix("Bearer ")
        body = {"choices": [{"message": {"content": '{"echo": "' + got + '"}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1}, "debug": {"auth": got}}
        return SimpleNamespace(status_code=self.status, json=lambda: body, text=f"invalid credentials: {got}")


def _everything_written(tmp_path):
    files = list((tmp_path / ".semaudit-cache").glob("*.json")) + list((tmp_path / "runs").glob("*.jsonl"))
    return "".join(p.read_text() for p in files)


def test_a_key_reflected_in_the_reply_is_never_cached_logged_or_returned(tmp_path, monkeypatch):
    monkeypatch.setenv("MYHOST_API_KEY", SECRET)
    monkeypatch.setattr(httpx, "post", _Reflect())
    res = R.Router(root=_cfg(tmp_path)).complete("check_judge", [{"role": "user", "content": "hi"}])
    written = _everything_written(tmp_path)
    assert written and SECRET not in written and R.REDACTED in written         # the cache file holds the reply
    assert SECRET not in res.content and SECRET not in json.dumps(res.raw)


def test_a_key_reflected_in_an_error_is_redacted_from_the_error(tmp_path, monkeypatch):
    monkeypatch.setenv("MYHOST_API_KEY", SECRET)
    monkeypatch.setattr(httpx, "post", _Reflect(status=401))
    with pytest.raises(R.ModelError) as e:
        R.Router(root=_cfg(tmp_path)).complete("check_judge", [{"role": "user", "content": "hi"}])
    assert SECRET not in str(e.value) and R.REDACTED in str(e.value)
    assert SECRET not in _everything_written(tmp_path)


@pytest.mark.parametrize("url", ["http://llm.example.test/v1", "http://10.0.0.5:8000/v1", "http://127.0.0.1.evil.test/v1"])
def test_plain_http_to_a_non_loopback_host_is_refused(tmp_path, url):
    with pytest.raises(R.ConfigError, match="https"):
        R.Router(root=_cfg(tmp_path, f'[providers.p]\nbase_url = "{url}"\nkey_env = "K"\n'))


@pytest.mark.parametrize("url", ["http://127.0.0.1:8000/v1", "http://localhost:11434/v1", "http://[::1]:8000/v1",
                                 "https://llm.example.test/v1"])
def test_https_or_a_loopback_host_is_accepted(tmp_path, url):
    r = R.Router(root=_cfg(tmp_path, f'[providers.p]\nbase_url = "{url}"\nkey_env = "K"\n'))
    assert r.providers["p"]["base_url"] == url.rstrip("/")
