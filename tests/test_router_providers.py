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
