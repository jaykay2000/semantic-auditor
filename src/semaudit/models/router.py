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
}

# USD per million tokens (input, output). Standard mode only; unverified entries stay None
# so the ledger records "unpriced" rather than a misleading $0.
PRICES_PER_MTOK: dict[str, tuple[float, float] | None] = {
    "muse-spark-1.3": (1.25, 4.25),
    "muse-spark-1.2": (1.25, 4.25),
    "muse-spark-1.1": (1.25, 4.25),
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


class Router:
    def __init__(self, root: Path | None = None, config_path: Path | None = None,
                 max_usd: float | None = None):
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
        if max_completion_tokens:
            body["max_completion_tokens"] = max_completion_tokens

        digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        cache_file = self.cache_dir / f"{digest}.json"
        if not fresh and cache_file.exists():
            raw, latency = json.loads(cache_file.read_text()), 0.0
            cached = True
        else:
            if self.max_usd is not None and self.spent_usd >= self.max_usd:
                raise ModelError(f"budget exhausted: spent ${self.spent_usd:.4f} of ${self.max_usd}")
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
        self._log(role, model, usage, cost, cached, latency, digest)
        result = Result(role, model, content, parsed, usage, cost, cached, latency, raw)
        return result

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
                                "latency_s": round(latency, 2), "digest": digest[:16]}) + "\n")
