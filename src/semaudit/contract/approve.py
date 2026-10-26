"""Owner approval of contract items, pinned by content hash.

`approvals.yaml` (beside the contract) maps item keys to the hash the owner approved. An item whose
content changed since approval reads `changed`, never `approved`: approval is of exact content.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml

from .schema import Contract

Status = Literal["approved", "changed", "unapproved"]


@dataclass
class Item:
    key: str             # "<section>:<id>"
    section: str
    id: str
    obj: Any             # the pydantic model (or list of them, for whole-section items)
    digest: str


def _digest(obj: Any) -> str:
    def dump(o):
        if isinstance(o, list):
            return [dump(x) for x in o]
        return o.model_dump(mode="json", exclude={"source"})
    return hashlib.sha256(json.dumps(dump(obj), sort_keys=True).encode()).hexdigest()[:16]


def items(c: Contract) -> list[Item]:
    out: list[Item] = []

    def add(section: str, id: str, obj: Any):
        out.append(Item(f"{section}:{id}", section, id, obj, _digest(obj)))

    for r in c.rules:
        add("rule", r.id, r)
        for e in r.exceptions:
            add("exception", e.id, e)
    for d in c.decisions:
        add("decision", d.id, d)
    for f in c.features:
        add("feature", f.id, f)
    for p in c.personas:
        add("persona", p.id, p)
    for s in c.scenarios:
        add("scenario", s.id, s)
    for section, coll in (("state", c.state), ("surfaces", c.surfaces), ("oracles", c.oracles), ("facts", c.facts)):
        if coll:
            add(section, "all", coll)
    if c.policy:
        add("policy", "release", c.policy)
    if c.app:
        add("app", c.app.name, c.app)
    return out


def load_approvals(directory: Path) -> dict[str, dict[str, str]]:
    p = directory / "approvals.yaml"
    return (yaml.safe_load(p.read_text()) or {}) if p.exists() else {}


def status_of(item: Item, approvals: dict[str, dict[str, str]]) -> Status:
    a = approvals.get(item.key)
    if not a:
        return "unapproved"
    return "approved" if a.get("hash") == item.digest else "changed"


def approve(directory: Path, c: Contract, keys: list[str], by: str, on: str | None = None) -> list[str]:
    """Record approval of the given item keys at their current content. Returns the keys approved."""
    by_key = {i.key: i for i in items(c)}
    unknown = [k for k in keys if k not in by_key]
    if unknown:
        raise KeyError(f"unknown contract items: {unknown}")
    approvals = load_approvals(directory)
    for k in keys:
        approvals[k] = {"hash": by_key[k].digest, "by": by, "date": on or date.today().isoformat()}
    (directory / "approvals.yaml").write_text(
        "# Owner approvals, pinned to content hashes. Written by `semaudit contract approve` or the review page.\n"
        + yaml.safe_dump(dict(sorted(approvals.items())), sort_keys=False))
    return keys


def summary(c: Contract, approvals: dict[str, dict[str, str]]) -> dict[str, int]:
    counts = {"approved": 0, "changed": 0, "unapproved": 0}
    for i in items(c):
        counts[status_of(i, approvals)] += 1
    return counts
