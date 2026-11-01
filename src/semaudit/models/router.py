"""Model router: every model call in semaudit goes through `complete(role=...)`.

Roles map to (provider, model) in semaudit.toml. Calls are cached by content hash,
and every call (cached or not) is appended to a cost ledger.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

PROVIDERS = {
    "meta": {"base_url": "https://api.meta.ai/v1", "key_env": "META_MODEL_API_KEY"},
    "baseten": {"base_url": "https://inference.baseten.co/v1", "key_env": "BASETEN_API_KEY",
                # Muse Spark Open under a strict JSON schema can run away printing whitespace until the
                # server's 32,768-token limit ($0.14 a call, unreadable). Normal replies stay under ~5K tokens.
                "max_completion_tokens": 16000},
    # Anthropic API through the official SDK (not an OpenAI-compatible shim). The request is translated in
    # _fetch_anthropic and the reply mapped back to the chat-completions shape the rest of the router reads.
    "anthropic": {"key_env": "ANTHROPIC_API_KEY", "sdk": "anthropic", "max_completion_tokens": 64000},
}

UNREADABLE_RETRIES = 1    # a schema reply that is not JSON is retried this many times (another seed), never cached
# A role in semaudit.toml may override both: `max_completion_tokens` (a tighter cap, so a runaway fails sooner and
# costs less) and `unreadable_retries` (more fresh seeds before the reply is given up as unreadable). Neither changes
# what a readable reply must satisfy; a reply that is cut off is simply not JSON and is retried like any other.

# USD per million tokens (input, output). Standard mode only; unverified entries stay None
# so the ledger records "unpriced" rather than a misleading $0.
PRICES_PER_MTOK: dict[str, tuple[float, float] | None] = {
    "muse-spark-1.3": (1.25, 4.25),
    "muse-spark-1.2": (1.25, 4.25),
    "muse-spark-1.1": (1.25, 4.25),
    "meta-models/muse-spark-open-1026": (1.25, 4.25),   # Baseten hackathon model; third-party listing, not
                                                        # Baseten's own page (2026-10-28): confirm on the invoice
    "claude-opus-5-5": (4.0, 20.0),        # Anthropic list price, 2026-10 (Claude API skill: shared/models.md)
    "claude-sonnet-5-5": (2.0, 10.0),
    "muse-spark-1.3-contributor": None,
    "muse-spark-1.2-contributor": None,
}

DEFAULT_ROLES = {
    "interpreter": {"provider": "meta", "model": "muse-spark-1.3", "reasoning_effort": "medium"},
    "extractor": {"provider": "meta", "model": "muse-spark-1.3", "reasoning_effort": "low"},
    "cross_checker_extract": {"provider": "meta", "model": "muse-spark-1.2", "reasoning_effort": "low"},
    "cross_checker_interpret": {"provider": "meta", "model": "muse-spark-1.2", "reasoning_effort": "medium"},
    "defender": {"provider": "meta", "model": "muse-spark-1.2", "reasoning_effort": "medium"},
    "smoke": {"provider": "meta", "model": "muse-spark-1.3", "reasoning_effort": "minimal"},
}


def load_env(path: Path) -> None:
    """Fill os.environ from a KEY=VALUE file, without overriding non-empty values."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if value and not os.environ.get(key):
            os.environ[key] = value


@dataclass
class Result:
    role: str
    model: str
    content: str
    parsed: Any
    usage: dict
    cost_usd: float | None
    cached: bool
    latency_s: float
    raw: dict = field(repr=False, default_factory=dict)
    unreadable_attempts: int = 0          # replies discarded as not JSON before this one (each charged, logged)
    unreadable_cost_usd: float = 0.0


class ModelError(RuntimeError):
    pass


class UnreadableReply(ModelError):
    """A schema reply that was still not JSON after the retries (a runaway, or an answer longer than the cap).
    The caller can split its request."""


def _readable(raw: dict) -> bool:
    try:
        json.loads(raw["choices"][0]["message"].get("content") or "")
        return True
    except (ValueError, KeyError, IndexError):
        return False


class Router:
    def __init__(self, root: Path | None = None, config_path: Path | None = None,
                 max_usd: float | None = None, offline: bool = False):
        self.root = root or Path.cwd()
        load_env(self.root / ".env")
        self.roles = dict(DEFAULT_ROLES)
        cfg = config_path or self.root / "semaudit.toml"
        if cfg.exists():
            self.roles.update(tomllib.loads(cfg.read_text()).get("roles", {}))
        self.cache_dir = self.root / ".semaudit-cache"
        self.ledger_path = self.root / "runs" / "ledger.jsonl"
        self.max_usd = max_usd
        self.spent_usd = 0.0
        self.offline = offline            # cache only: a miss is an error, never a model call
        self.tag: str | None = None       # the run/condition each ledger row belongs to (benchmark accounting)
        self.usage: dict[str, dict[str, float]] = {}   # role -> calls, cached, spent, if_fresh, tokens

    def _key(self, provider: str) -> str:
        env = PROVIDERS[provider]["key_env"]
        key = os.environ.get(env)
        if not key:
            raise ModelError(f"{env} is not set (expected in .env)")
        return key

    def complete(self, role: str, messages: list[dict], *, schema: dict | None = None,
                 schema_name: str = "output", tools: list[dict] | None = None,
                 reasoning_effort: str | None = None, seed: int | None = None,
                 max_completion_tokens: int | None = None, fresh: bool = False,
                 timeout_s: float = 180.0) -> Result:
        spec = self.roles[role]
        provider, model = spec["provider"], spec["model"]
        body: dict[str, Any] = {"model": model, "messages": messages}
        effort = reasoning_effort or spec.get("reasoning_effort")
        if effort:
            body["reasoning_effort"] = effort
        if schema is not None:
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": schema_name, "schema": schema, "strict": True}}
        if tools:
            body["tools"] = tools
        if seed is not None:
            body["seed"] = seed
        max_completion_tokens = (max_completion_tokens or spec.get("max_completion_tokens")
                                 or PROVIDERS[provider].get("max_completion_tokens"))
        retries = int(spec.get("unreadable_retries", UNREADABLE_RETRIES))
        if max_completion_tokens:
            body["max_completion_tokens"] = max_completion_tokens

        keyed = body if provider == "meta" else {**body, "_provider": provider}   # meta keys unchanged: old cache stays valid
        digest = hashlib.sha256(json.dumps(keyed, sort_keys=True).encode()).hexdigest()
        cache_file = self.cache_dir / f"{digest}.json"
        if not fresh and cache_file.exists():
            raw, latency = json.loads(cache_file.read_text()), 0.0
            lost, lost_usd = 0, 0.0
            cached = True
        else:
            raw, lost, lost_usd = None, 0, 0.0
            for unreadable in range(retries + 1):
                send = body if unreadable == 0 else {**body, "seed": (seed or 0) + 1000 + unreadable}
                raw, latency = self._fetch(role, provider, model, send, digest, timeout_s)
                if schema is None or _readable(raw):
                    break
                cost = self._cost(model, raw.get("usage", {}))   # charged though unusable: count and log it
                self.spent_usd += cost or 0.0
                lost, lost_usd = lost + 1, lost_usd + (cost or 0.0)
                self._log(role, model, raw.get("usage", {}), cost, False, latency, digest + ":unreadable")
                if unreadable == retries:
                    fin = raw["choices"][0].get("finish_reason")
                    raise UnreadableReply(f"{provider}/{model}: reply is not JSON (finish_reason={fin}) after "
                                     f"{retries + 1} tries; not cached")
            self.cache_dir.mkdir(exist_ok=True)
            cache_file.write_text(json.dumps(raw))
            cached = False

        message = raw["choices"][0]["message"]
        content = message.get("content") or ""
        parsed = None
        if schema is not None and content:
            parsed = json.loads(content)
        usage = raw.get("usage", {})
        cost = self._cost(model, usage)
        if not cached and cost is not None:
            self.spent_usd += cost
        u = self.usage.setdefault(role, {"calls": 0, "cached": 0, "spent_usd": 0.0, "if_fresh_usd": 0.0,
                                         "prompt_tokens": 0, "completion_tokens": 0})
        u["calls"] += 1
        u["cached"] += int(cached)
        u["if_fresh_usd"] += cost or 0.0
        u["spent_usd"] += 0.0 if cached else (cost or 0.0)
        u["prompt_tokens"] += usage.get("prompt_tokens", 0)
        u["completion_tokens"] += usage.get("completion_tokens", 0)
        self._log(role, model, usage, cost, cached, latency, digest)
        result = Result(role, model, content, parsed, usage, cost, cached, latency, raw,
                        0 if cached else lost, 0.0 if cached else lost_usd)
        return result

    def _fetch(self, role, provider, model, body, digest, timeout_s):
        if self.offline:
            raise ModelError(f"offline: no cached answer for {role} ({digest[:12]})")
        if self.max_usd is not None and self.spent_usd >= self.max_usd:
            raise ModelError(f"budget exhausted: spent ${self.spent_usd:.4f} of ${self.max_usd}")
        if self.max_usd is not None and not PRICES_PER_MTOK.get(model):
            raise ModelError(f"{model} has no price, so a ${self.max_usd} cap could not count it: refused")
        if PROVIDERS[provider].get("sdk") == "anthropic":
            return self._fetch_anthropic(model, body, timeout_s)
        t0 = time.monotonic()
        resp = None
        for attempt in range(4):           # transient failures: timeouts, 429, 5xx
            try:
                resp = httpx.post(f"{PROVIDERS[provider]['base_url']}/chat/completions", json=body,
                                  headers={"Authorization": f"Bearer {self._key(provider)}"},
                                  timeout=timeout_s)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                if attempt == 3:
                    raise ModelError(f"{provider}/{model} transport error after retries: {e}") from e
                time.sleep(2 ** attempt * 2)
                continue
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** attempt * 2)
                continue
            break
        latency = time.monotonic() - t0
        if resp.status_code != 200:
            raise ModelError(f"{provider}/{model} HTTP {resp.status_code}: {resp.text[:500]}")
        raw = resp.json()
        return raw, latency

    def _fetch_anthropic(self, model: str, body: dict, timeout_s: float):
        """One Messages API call through the official SDK, streamed (replies can be long), returned in the
        chat-completions shape: choices[0].message.content, finish_reason ('length' when max_tokens was hit,
        'content_filter' on a refusal) and usage.prompt_tokens / completion_tokens (thinking counts as output)."""
        import anthropic
        params = anthropic_params(model, body)
        client = anthropic.Anthropic(api_key=self._key("anthropic"), timeout=max(timeout_s, 600.0), max_retries=3)
        t0 = time.monotonic()
        try:
            with client.messages.stream(**params) as stream:
                msg = stream.get_final_message()
        except anthropic.APIError as e:
            raise ModelError(f"anthropic/{model}: {type(e).__name__}: {str(e)[:400]}") from e
        return anthropic_to_chat(msg.model_dump()), time.monotonic() - t0

    def accounting(self) -> dict:
        """Spend for this router's lifetime: actually spent (cache hits cost 0) vs. the same calls made fresh."""
        tot = {k: sum(u[k] for u in self.usage.values()) for k in ("calls", "cached", "spent_usd", "if_fresh_usd")}
        return {"tag": self.tag, "fresh": tot["cached"] == 0 and tot["calls"] > 0,
                **{k: round(v, 6) if isinstance(v, float) else v for k, v in tot.items()},
                "by_role": {r: {k: round(v, 6) if isinstance(v, float) else v for k, v in u.items()}
                            for r, u in sorted(self.usage.items())}}

    @staticmethod
    def _cost(model: str, usage: dict) -> float | None:
        price = PRICES_PER_MTOK.get(model)
        if not price:
            return None
        return (usage.get("prompt_tokens", 0) * price[0] + usage.get("completion_tokens", 0) * price[1]) / 1e6

    def _log(self, role, model, usage, cost, cached, latency, digest) -> None:
        self.ledger_path.parent.mkdir(exist_ok=True)
        with self.ledger_path.open("a") as f:
            f.write(json.dumps({"ts": time.time(), "role": role, "model": model, "usage": usage,
                                "cost_usd": cost, "priced": cost is not None, "cached": cached,
                                "latency_s": round(latency, 2), "digest": digest[:16],
                                **({"tag": self.tag} if self.tag else {})}) + "\n")


# ---------------------------------------------------------------- Anthropic translation (pure, tested offline)

_EFFORT = {"minimal": "low", "low": "low", "medium": "medium", "high": "high"}
_STOP = {"end_turn": "stop", "stop_sequence": "stop", "max_tokens": "length", "refusal": "content_filter",
         "tool_use": "tool_calls"}


def _anyof_types(schema):
    """JSON Schema `"type": ["string", "null"]` (a type list) rewritten as the equivalent anyOf, which the
    structured-output schema subset documents; an enum beside a type list is split across the branches."""
    if isinstance(schema, list):
        return [_anyof_types(x) for x in schema]
    if not isinstance(schema, dict):
        return schema
    out = {k: _anyof_types(v) for k, v in schema.items()}
    t = out.get("type")
    if isinstance(t, list):
        enum = out.pop("enum", None)
        out.pop("type")
        branches = []
        for one in t:
            b = {"type": one}
            if enum is not None:
                vals = [v for v in enum if (v is None) == (one == "null")]
                if one != "null":
                    b["enum"] = vals
            branches.append(b)
        out["anyOf"] = branches
    return out


def anthropic_params(model: str, body: dict) -> dict:
    """Chat-completions body -> Messages API parameters. System messages become `system`; response_format
    json_schema becomes output_config.format; reasoning_effort becomes output_config.effort; seed is dropped (the
    API has none). Thinking is left at the model's default (adaptive on Claude Opus 5.5 / Sonnet 5.5)."""
    system = "\n\n".join(m["content"] for m in body["messages"] if m["role"] == "system")
    msgs = [{"role": m["role"], "content": m["content"]} for m in body["messages"] if m["role"] != "system"]
    p: dict = {"model": model, "max_tokens": body.get("max_completion_tokens") or 64000, "messages": msgs}
    if system:
        p["system"] = system
    oc: dict = {}
    rf = body.get("response_format")
    if rf and rf.get("type") == "json_schema":
        oc["format"] = {"type": "json_schema", "schema": _anyof_types(rf["json_schema"]["schema"])}
    if body.get("reasoning_effort"):
        oc["effort"] = _EFFORT.get(body["reasoning_effort"], body["reasoning_effort"])
    if oc:
        p["output_config"] = oc
    if body.get("tools"):
        raise ModelError("tool calls through the anthropic provider are not supported")
    return p


def anthropic_to_chat(msg: dict) -> dict:
    """Messages API reply (as a dict) -> the chat-completions shape the router stores and reads."""
    text = "".join(b.get("text", "") for b in msg.get("content", []) if b.get("type") == "text")
    u = msg.get("usage") or {}
    prompt = (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0) + \
        (u.get("cache_creation_input_tokens") or 0)
    return {"model": msg.get("model"), "id": msg.get("id"),
            "choices": [{"message": {"role": "assistant", "content": text},
                         "finish_reason": _STOP.get(msg.get("stop_reason"), msg.get("stop_reason"))}],
            "usage": {"prompt_tokens": prompt, "completion_tokens": u.get("output_tokens") or 0},
            "anthropic": {"stop_reason": msg.get("stop_reason"), "usage": u}}
