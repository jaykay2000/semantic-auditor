"""Release registry. A release is a module in this package (r2_3.py, r2_4.py, bench_01.py ...) that defines
RELEASE = Release(...). Selecting one never touches core code:

    Release(name="2.3", features=["core", "price_watch", "concierge"],
            settings={"price_watch": {"mode": "opt_in", "alert_delay": "30s"}},
            copy={"core.results": "..."})          # copy overrides AND new keys

`features` entries are feature ids or dotted module paths (see northbound.features). Release.derive() builds a
release from another one (add/remove features, change settings, override copy).
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Release:
    name: str
    features: list[str]
    settings: dict[str, dict[str, Any]] = field(default_factory=dict)
    copy: dict[str, str] = field(default_factory=dict)

    def derive(self, name: str, *, add: list[str] | None = None, remove: list[str] | None = None,
               settings: dict[str, dict[str, Any]] | None = None, copy: dict[str, str] | None = None) -> "Release":
        merged = {k: dict(v) for k, v in self.settings.items()}
        for fid, vals in (settings or {}).items():
            merged.setdefault(fid, {}).update(vals)
        return Release(name=name,
                       features=[f for f in self.features if f not in (remove or [])] + list(add or []),
                       settings=merged, copy={**self.copy, **(copy or {})})


_REGISTRY: dict[str, Release] = {}


def register_release(release: Release) -> Release:
    _REGISTRY[release.name] = release
    return release


def module_name(release_name: str) -> str:
    """'2.3' -> 'r2_3', '2.4.1' -> 'r2_4_1', 'bench-01' -> 'bench_01'."""
    slug = release_name.replace(".", "_").replace("-", "_")
    return f"r{slug}" if slug[:1].isdigit() else slug


def load_release(name: str) -> Release:
    if name in _REGISTRY:
        return _REGISTRY[name]
    try:
        module = importlib.import_module(f"{__name__}.{module_name(name)}")
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.endswith(module_name(name)):
            raise ValueError(f"unknown Northbound release {name!r}: no module "
                             f"northbound/releases/{module_name(name)}.py") from exc
        raise
    return module.RELEASE
