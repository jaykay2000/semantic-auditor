"""Providers, prices and the spending cap (router)."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import httpx  # noqa: E402
import pytest  # noqa: E402

from semaudit.models import router as R  # noqa: E402


class _Resp:
    status_code = 200

    def __init__(self, model):
        self._model = model

    def json(self):
        return {"model": self._model, "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 100}}


def _router(tmp_path, monkeypatch, provider, model, max_usd=1.0):
    monkeypatch.setenv("META_MODEL_API_KEY", "k")
    monkeypatch.setenv("BASETEN_API_KEY", "k")
    calls = []

    def post(url, json=None, headers=None, timeout=None):
        calls.append((url, json))
        return _Resp(json["model"])
    monkeypatch.setattr(httpx, "post", post)
    r = R.Router(root=tmp_path, max_usd=max_usd)
    r.roles["t"] = {"provider": provider, "model": model}
    return r, calls


def test_baseten_call_goes_to_baseten_and_is_priced(tmp_path, monkeypatch):
    r, calls = _router(tmp_path, monkeypatch, "baseten", "meta-models/muse-spark-open-1026")
    res = r.complete("t", [{"role": "user", "content": "hi"}])
    assert calls[0][0] == "https://inference.baseten.co/v1/chat/completions"
    assert res.cost_usd == pytest.approx((1000 * 1.25 + 100 * 4.25) / 1e6)
    assert r.spent_usd == pytest.approx(res.cost_usd)


def test_unpriced_model_is_refused_under_a_cap(tmp_path, monkeypatch):
    r, calls = _router(tmp_path, monkeypatch, "baseten", "some-unpriced-model")
    with pytest.raises(R.ModelError, match="no price"):
        r.complete("t", [{"role": "user", "content": "hi"}])
    assert calls == []


def test_unpriced_model_allowed_without_a_cap(tmp_path, monkeypatch):
    r, calls = _router(tmp_path, monkeypatch, "baseten", "some-unpriced-model", max_usd=None)
    r.complete("t", [{"role": "user", "content": "hi"}])
    assert len(calls) == 1


def test_meta_cache_key_unchanged_and_other_providers_keyed_apart(tmp_path, monkeypatch):
    msgs = [{"role": "user", "content": "hi"}]
    r, _ = _router(tmp_path, monkeypatch, "meta", "muse-spark-1.3")
    r.complete("t", msgs)
    plain = hashlib.sha256(json.dumps({"model": "muse-spark-1.3", "messages": msgs}, sort_keys=True).encode()).hexdigest()
    assert (tmp_path / ".semaudit-cache" / f"{plain}.json").exists()   # existing cached answers still hit
    r.roles["t"] = {"provider": "baseten", "model": "muse-spark-1.3"}  # same body, other host: not a hit
    R.PRICES_PER_MTOK.setdefault("muse-spark-1.3", (1.25, 4.25))
    res = r.complete("t", msgs)
    assert not res.cached


class _Seq:
    """Replies in order: each item is (content, finish_reason)."""
    def __init__(self, replies):
        self.replies, self.bodies = list(replies), []

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.bodies.append(json)
        content, fin = self.replies.pop(0)

        class Resp:
            status_code = 200

            def json(self_inner):
                return {"choices": [{"message": {"content": content}, "finish_reason": fin}],
                        "usage": {"prompt_tokens": 1000, "completion_tokens": 32768}}
        return Resp()


def _schema_router(tmp_path, monkeypatch, replies):
    monkeypatch.setenv("BASETEN_API_KEY", "k")
    seq = _Seq(replies)
    monkeypatch.setattr(httpx, "post", seq)
    r = R.Router(root=tmp_path, max_usd=5.0)
    r.roles["t"] = {"provider": "baseten", "model": "meta-models/muse-spark-open-1026"}
    return r, seq


SCHEMA = {"type": "object", "properties": {"a": {"type": "number"}}}


def test_whitespace_runaway_is_retried_counted_and_not_cached(tmp_path, monkeypatch):
    r, seq = _schema_router(tmp_path, monkeypatch, [('{"a": ' + " " * 500, "length"), ('{"a": 1}', "stop")])
    res = r.complete("t", [{"role": "user", "content": "x"}], schema=SCHEMA)
    assert res.parsed == {"a": 1}
    assert len(seq.bodies) == 2 and seq.bodies[1]["seed"] != seq.bodies[0].get("seed")
    one = (1000 * 1.25 + 32768 * 4.25) / 1e6
    assert r.spent_usd == pytest.approx(2 * one)              # the unusable reply was charged, so it is counted
    cached = list((tmp_path / ".semaudit-cache").glob("*.json"))
    assert len(cached) == 1 and json.loads(cached[0].read_text())["choices"][0]["message"]["content"] == '{"a": 1}'


def test_unreadable_twice_raises_model_error_and_caches_nothing(tmp_path, monkeypatch):
    r, seq = _schema_router(tmp_path, monkeypatch, [("{", "length"), ("{", "length")])
    with pytest.raises(R.ModelError, match="not JSON"):
        r.complete("t", [{"role": "user", "content": "x"}], schema=SCHEMA)
    assert not (tmp_path / ".semaudit-cache").exists() or not list((tmp_path / ".semaudit-cache").glob("*.json"))


def test_baseten_reply_length_is_capped(tmp_path, monkeypatch):
    r, seq = _schema_router(tmp_path, monkeypatch, [('{"a": 1}', "stop")])
    r.complete("t", [{"role": "user", "content": "x"}], schema=SCHEMA)
    assert seq.bodies[0]["max_completion_tokens"] == 16000
