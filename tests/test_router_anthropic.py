"""The Anthropic provider (official SDK): request translation, reply mapping, pricing and the router's usual
bookkeeping. Offline: the SDK client is replaced by a fake, no network call is made."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from semaudit.bench.judge import SCHEMA
from semaudit.models import router as R


def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def test_reader_schema_has_no_type_lists_after_translation():
    out = R._anyof_types(SCHEMA)
    nodes = list(_walk(out))
    assert not any(isinstance(n.get("type"), list) for n in nodes)
    assert all(n.get("additionalProperties") is False for n in nodes if n.get("type") == "object")
    label = out["properties"]["findings"]["items"]["properties"]["label"]
    assert label == {"anyOf": [{"type": "string", "enum": ["conflict", "unexplained_tradeoff"]}, {"type": "null"}]}
    decision = out["properties"]["findings"]["items"]["properties"]["target"]["properties"]["decision"]
    assert decision == {"anyOf": [{"type": "string"}, {"type": "null"}]}


def test_params_translation():
    body = {"model": "claude-opus-5-5", "seed": 7, "reasoning_effort": "minimal", "max_completion_tokens": 64000,
            "messages": [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "findings", "schema": SCHEMA,
                                                                       "strict": True}}}
    p = R.anthropic_params("claude-opus-5-5", body)
    assert p["system"] == "S" and p["messages"] == [{"role": "user", "content": "U"}]
    assert "seed" not in p and "thinking" not in p and p["max_tokens"] == 64000
    assert p["output_config"]["effort"] == "low"
    assert p["output_config"]["format"]["type"] == "json_schema"
    assert p["output_config"]["format"]["schema"] == R._anyof_types(SCHEMA)


def test_tools_are_refused():
    with pytest.raises(R.ModelError, match="not supported"):
        R.anthropic_params("claude-opus-5-5", {"messages": [{"role": "user", "content": "x"}], "tools": [{}]})


@pytest.mark.parametrize("stop,finish", [("end_turn", "stop"), ("max_tokens", "length"), ("refusal", "content_filter")])
def test_reply_mapping(stop, finish):
    msg = {"id": "m1", "model": "claude-opus-5-5", "stop_reason": stop,
           "content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": '{"findings": []}'}],
           "usage": {"input_tokens": 1000, "cache_read_input_tokens": 200, "output_tokens": 50}}
    raw = R.anthropic_to_chat(msg)
    assert raw["choices"][0]["message"]["content"] == '{"findings": []}'
    assert raw["choices"][0]["finish_reason"] == finish
    assert raw["usage"] == {"prompt_tokens": 1200, "completion_tokens": 50}


class _FakeStream:
    def __init__(self, reply):
        self.reply = reply

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return SimpleNamespace(model_dump=lambda: self.reply)


def _fake_sdk(monkeypatch, replies, seen):
    import anthropic

    class Client:
        def __init__(self, api_key=None, timeout=None, max_retries=None):
            seen.append({"api_key": api_key})
            self.messages = SimpleNamespace(stream=self._stream)

        def _stream(self, **params):
            seen.append(params)
            return _FakeStream(replies.pop(0))
    monkeypatch.setattr(anthropic, "Anthropic", Client)


def _reply(text, stop="end_turn"):
    return {"id": "m", "model": "claude-opus-5-5", "stop_reason": stop, "content": [{"type": "text", "text": text}],
            "usage": {"input_tokens": 1_000_000, "output_tokens": 100_000}}


def test_router_end_to_end_prices_caches_and_logs(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    seen = []
    _fake_sdk(monkeypatch, [_reply('{"findings": []}')], seen)
    r = R.Router(root=tmp_path, max_usd=80)
    r.roles["interpreter"] = {"provider": "anthropic", "model": "claude-opus-5-5"}
    res = r.complete("interpreter", [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}],
                     schema=SCHEMA, schema_name="findings", fresh=True)
    assert res.parsed == {"findings": []}
    assert res.cost_usd == pytest.approx(4.0 + 2.0)          # 1M in at $4 + 0.1M out at $20
    assert r.spent_usd == pytest.approx(6.0)
    assert seen[0] == {"api_key": "k"} and seen[1]["output_config"]["format"]["type"] == "json_schema"
    assert len(list((tmp_path / ".semaudit-cache").glob("*.json"))) == 1
    row = json.loads((tmp_path / "runs" / "ledger.jsonl").read_text().splitlines()[-1])
    assert row["model"] == "claude-opus-5-5" and row["priced"] and not row["cached"]


def test_cache_key_differs_from_other_providers(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    seen = []
    _fake_sdk(monkeypatch, [_reply('{"findings": []}'), _reply('{"findings": []}')], seen)
    r = R.Router(root=tmp_path, max_usd=80)
    r.roles["a"] = {"provider": "anthropic", "model": "claude-opus-5-5"}
    r.complete("a", [{"role": "user", "content": "U"}])
    second = r.complete("a", [{"role": "user", "content": "U"}])
    assert second.cached                                          # same request -> cache hit, no second call
    assert len([s for s in seen if "messages" in s]) == 1


def test_unreadable_schema_reply_is_retried_then_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    seen = []
    _fake_sdk(monkeypatch, [_reply("not json"), _reply("still not json")], seen)
    r = R.Router(root=tmp_path, max_usd=80)
    r.roles["a"] = {"provider": "anthropic", "model": "claude-opus-5-5"}
    with pytest.raises(R.UnreadableReply):
        r.complete("a", [{"role": "user", "content": "U"}], schema=SCHEMA, fresh=True)
    assert len([s for s in seen if "messages" in s]) == 2
    assert not list((tmp_path / ".semaudit-cache").glob("*.json"))   # never cached
    assert r.spent_usd == pytest.approx(12.0)                         # both unusable calls are counted


def test_cap_stops_before_the_next_call(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    seen = []
    _fake_sdk(monkeypatch, [_reply('{"findings": []}')], seen)
    r = R.Router(root=tmp_path, max_usd=5)
    r.roles["a"] = {"provider": "anthropic", "model": "claude-opus-5-5"}
    r.complete("a", [{"role": "user", "content": "U1"}], fresh=True)   # $6 spent, over the $5 cap
    with pytest.raises(R.ModelError, match="budget exhausted"):
        r.complete("a", [{"role": "user", "content": "U2"}], fresh=True)
