"""Run the saved, owner-approved checks of a contract: the next review uses what earlier discoveries left behind.

Nothing is imported here. The checks come from storage only:
  approvals.yaml        `check:<id>` -> the digest the owner approved
  checks/<id>.yaml      the check record (actions, invariant, source quote kept as evidence)
  dispositions.yaml     the owner's decisions on checks, and where each re-check's outcome is appended

A check whose record no longer has its approved digest is refused (listed, never run). Each approved check is
replayed fresh on the base and the head release, judged (recheck.py), and its base/head outcome is recorded in the
memory. The run writes `<run_dir>/saved-checks.json`: what was loaded (with file hashes), the four statuses per
release, the models used, and the memory outcome.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from semaudit.contract.approve import load_approvals
from semaudit.contract.schema import MEMORY_FILE, load_contract
from semaudit.decide import memory
from semaudit.models.router import Router

from . import recheck as rc
from .record import ImportedCheck, load_spec


def _sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else None


def saved_checks(contract_dir: Path) -> tuple[list[ImportedCheck], list[str]]:
    """(approved checks at their approved digest, refusals with the reason)."""
    approvals = load_approvals(contract_dir)
    ok, refused = [], []
    for key, a in sorted(approvals.items()):
        if not key.startswith("check:"):
            continue
        cid = key.split(":", 1)[1]
        p = Path(contract_dir) / "checks" / f"{cid}.yaml"
        if not p.exists():
            refused.append(f"{cid}: approved, but checks/{cid}.yaml is missing")
            continue
        c = ImportedCheck.read(p)
        if c.digest() != a.get("hash"):
            refused.append(f"{cid}: content changed since approval (approved {a.get('hash')}, now {c.digest()})")
        elif c.conversion.status != "converted":
            refused.append(f"{cid}: approved, but its conversion is {c.conversion.status}")
        else:
            ok.append(c)
    return ok, refused


def run_saved(contract_dir: Path, base: str, head: str, router: Router, *, runs_dir: Path, run_id: str,
              judgments: int = 3, before_release: Callable[[str], None] | None = None,
              after_release: Callable[[str], None] | None = None) -> dict[str, Any]:
    contract_dir = Path(contract_dir)
    checks, refused = saved_checks(contract_dir)
    approvals = load_approvals(contract_dir)
    loaded = {"approvals.yaml": _sha(contract_dir / "approvals.yaml"),
              MEMORY_FILE: _sha(contract_dir / MEMORY_FILE),
              **{f"checks/{c.id}.yaml": _sha(contract_dir / "checks" / f"{c.id}.yaml") for c in checks}}
    contract, spec = load_contract(contract_dir), load_spec(contract_dir)
    eps: dict[str, dict] = {}
    for rel in (base, head):
        if before_release:
            before_release(rel)
        eps[rel] = rc.replay(checks, contract_dir, rel, runs_dir=runs_dir, run_id=run_id, approved_only=True,
                             approvals=approvals) if checks else {}
        if after_release:
            after_release(rel)
    out = {"run": run_id, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "base": base,
           "head": head, "loaded_from_storage": loaded, "refused": refused, "checks": []}
    for c in checks:
        rows = {}
        for rel in (base, head):
            rows[rel] = rc.recheck(c, eps[rel].get(c.id), contract, spec, router, judgments=judgments, approved=True)
        o = memory.record_check_outcome(contract_dir, c.id, c.digest(), rows[base], rows[head], run=run_id)
        out["checks"].append({"id": c.id, "approved_digest": approvals[f"check:{c.id}"]["hash"],
                              "digest": c.digest(), "approved_by": approvals[f"check:{c.id}"].get("by"),
                              "results": rows, "memory": o})
    d = Path(runs_dir) / run_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "saved-checks.json").write_text(json.dumps(out, indent=1, default=str))
    return out
