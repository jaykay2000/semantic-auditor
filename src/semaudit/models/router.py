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
}

UNREADABLE_RETRIES = 1    # a schema reply that is not JSON is retried this many times (another seed), never cached

# USD per million tokens (input, output). Standard mode only; unverified entries stay None
# so the ledger records "unpriced" rather than a misleading $0.
PRICES_PER_MTOK: dict[str, tuple[float, float] | None] = {
    "muse-spark-1.3": (1.25, 4.25),
    "muse-spark-1.2": (1.25, 4.25),
    "muse-spark-1.1": (1.25, 4.25),
    "meta-models/muse-spark-open-1026": (1.25, 4.25),   # Baseten hackathon model; third-party listing, not
                                                        # Baseten's own page (2026-10-28): confirm on the invoice
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
        max_completion_tokens = max_completion_tokens or PROVIDERS[provider].get("max_completion_tokens")
        if max_completion_tokens:
            body["max_completion_tokens"] = max_completion_tokens

        keyed = body if provider == "meta" else {**body, "_provider": provider}   # meta keys unchanged: old cache stays valid
        digest = hashlib.sha256(json.dumps(keyed, sort_keys=True).encode()).hexdigest()
        cache_file = self.cache_dir / f"{digest}.json"
        if not fresh and cache_file.exists():
            raw, latency = json.loads(cache_file.read_text()), 0.0
            cached = True
        else:
            raw = None
            for unreadable in range(UNREADABLE_RETRIES + 1):
                send = body if unreadable == 0 else {**body, "seed": (seed or 0) + 1000 + unreadable}
                raw, latency = self._fetch(role, provider, model, send, digest, timeout_s)
                if schema is None or _readable(raw):
                    break
                cost = self._cost(model, raw.get("usage", {}))   # charged though unusable: count and log it
                self.spent_usd += cost or 0.0
                self._log(role, model, raw.get("usage", {}), cost, False, latency, digest + ":unreadable")
                if unreadable == UNREADABLE_RETRIES:
                    fin = raw["choices"][0].get("finish_reason")
                    raise UnreadableReply(f"{provider}/{model}: reply is not JSON (finish_reason={fin}) after "
                                     f"{UNREADABLE_RETRIES + 1} tries; not cached")
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
        result = Result(role, model, content, parsed, usage, cost, cached, latency, raw)
        return result

    def _fetch(self, role, provider, model, body, digest, timeout_s):
        if self.offline:
            raise ModelError(f"offline: no cached answer for {role} ({digest[:12]})")
        if self.max_usd is not None and self.spent_usd >= self.max_usd:
            raise ModelError(f"budget exhausted: spent ${self.spent_usd:.4f} of ${self.max_usd}")
        if self.max_usd is not None and not PRICES_PER_MTOK.get(model):
            raise ModelError(f"{model} has no price, so a ${self.max_usd} cap could not count it: refused")
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
