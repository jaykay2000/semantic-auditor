"""The ONLY module that reads environment variables.

NORTHBOUND_RELEASE     release to run: 2.3 (default) | 2.4 | 2.4.1 | bench-NN
NORTHBOUND_OUTBOX      directory for the email / push file sinks (default: examples/northbound/outbox)
NORTHBOUND_TEST_HOOKS  "1" (default) mounts /api/test/*; anything else leaves them out
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_RELEASE = "2.3"
APP_ROOT = Path(__file__).resolve().parent.parent  # examples/northbound/


@dataclass(frozen=True)
class Config:
    release: str = DEFAULT_RELEASE
    outbox_dir: Path = field(default_factory=lambda: APP_ROOT / "outbox")
    test_hooks: bool = True

    @classmethod
    def from_env(cls) -> "Config":
        env = os.environ
        return cls(
            release=env.get("NORTHBOUND_RELEASE", DEFAULT_RELEASE),
            outbox_dir=Path(env.get("NORTHBOUND_OUTBOX") or (APP_ROOT / "outbox")),
            test_hooks=env.get("NORTHBOUND_TEST_HOOKS", "1") == "1",
        )
