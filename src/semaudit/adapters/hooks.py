"""A generic HTTP client for the contract's test hooks (reset, persona, clock, world) and its oracles.

Nothing here knows an app. The contract names each hook as `"METHOD /path"`; what to send (the persona body,
the clock body) comes from the app's adapter. Oracles are path templates (`/api/oracle/booking?traveller={traveller}`)
filled from adapter-supplied params; each response is read with the contract's JSON paths.
"""

from __future__ import annotations

import string
from typing import Any
from urllib.parse import quote

import httpx

from ..contract.schema import Hooks, Oracle
from ..story.episode import OracleReading


class HookError(RuntimeError):
    """A hook answered with an error, or did not answer."""


class HookClient:
    def __init__(self, base_url: str, hooks: Hooks, http: httpx.Client | None = None, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.hooks = hooks
        self.http = http or httpx.Client(timeout=timeout)

    def has(self, name: str) -> bool:
        return bool(getattr(self.hooks, name, None))

    def call(self, name: str, body: dict[str, Any] | None = None) -> Any:
        """Call hook `name`; returns the parsed JSON answer (or None for an empty answer)."""
        spec = getattr(self.hooks, name, None)
        if not spec:
            raise HookError(f"the contract defines no {name!r} hook")
        method, _, path = spec.partition(" ")
        if not path:
            method, path = "POST", spec
        try:
            r = self.http.request(method.upper(), self.base_url + path.strip(), json=body)
        except httpx.HTTPError as exc:
            raise HookError(f"{name} hook {spec!r}: {exc}") from exc
        if r.status_code >= 400:
            raise HookError(f"{name} hook {spec!r} answered {r.status_code}: {r.text[:300]}")
        if not r.content:
            return None
        try:
            return r.json()
        except ValueError:
            return {"text": r.text}

    def reset(self) -> Any:
        return self.call("reset") if self.has("reset") else None

    def persona(self, body: dict[str, Any]) -> Any:
        return self.call("persona", body)

    def clock(self, body: dict[str, Any]) -> Any:
        return self.call("clock", body)

    def world(self, body: dict[str, Any]) -> Any:
        return self.call("world", body)


def json_path(doc: Any, path: str) -> Any:
    """`$.a.b[0].c` into a parsed JSON document. KeyError if the path is not there."""
    if not path.startswith("$"):
        raise KeyError(path)
    cur = doc
    rest = path[1:]
    i = 0
    while i < len(rest):
        ch = rest[i]
        if ch == ".":
            j = i + 1
            while j < len(rest) and rest[j] not in ".[":
                j += 1
            name = rest[i + 1:j]
            if not isinstance(cur, dict) or name not in cur:
                raise KeyError(path)
            cur, i = cur[name], j
        elif ch == "[":
            j = rest.index("]", i)
            idx = int(rest[i + 1:j])
            if not isinstance(cur, list) or not -len(cur) <= idx < len(cur):
                raise KeyError(path)
            cur, i = cur[idx], j + 1
        else:
            raise KeyError(path)
    return cur


class OracleClient:
    def __init__(self, base_url: str, oracles: list[Oracle], http: httpx.Client | None = None, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.oracles = oracles
        self.http = http or httpx.Client(timeout=timeout)

    def read(self, oracle: Oracle, params: dict[str, Any]) -> OracleReading:
        needed = [f for _, f, _, _ in string.Formatter().parse(oracle.endpoint) if f]
        missing = [n for n in needed if params.get(n) in (None, "")]
        if missing:
            return OracleReading(status="not_applicable",
                                 error=f"needs {', '.join(missing)}, which this persona does not have")
        endpoint = oracle.endpoint.format_map({k: quote(str(v), safe="") for k, v in params.items() if v is not None})
        try:
            r = self.http.get(self.base_url + endpoint)
            if r.status_code >= 400:
                return OracleReading(status="not_measured", endpoint=endpoint,
                                     error=f"HTTP {r.status_code}: {r.text[:200]}")
            doc = r.json()
        except (httpx.HTTPError, ValueError) as exc:
            return OracleReading(status="not_measured", endpoint=endpoint, error=f"{type(exc).__name__}: {exc}")
        values: dict[str, Any] = {}
        absent: list[str] = []
        for name, path in oracle.fields.items():
            try:
                values[name] = json_path(doc, path)
            except KeyError:
                values[name] = None
                absent.append(name)
        if absent:
            return OracleReading(status="not_measured", endpoint=endpoint, values=values,
                                 error=f"missing in the response: {', '.join(absent)}")
        return OracleReading(status="ok", endpoint=endpoint, values=values)

    def snapshot(self, params: dict[str, Any]) -> dict[str, OracleReading]:
        return {o.id: self.read(o, params) for o in self.oracles}
