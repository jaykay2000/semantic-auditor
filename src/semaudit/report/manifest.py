"""What a review was computed from, so it can be checked and replayed: contract, adapter, episodes, code
revision, models, prompts and verifier settings, each pinned by digest.

`semaudit repro` refuses to replay against a contract that changed since the review; `semaudit verify-report`
re-derives the review's findings from the pinned episodes and compares.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import semaudit
from semaudit.contract.schema import Contract
from semaudit.extract import messages as _extract
from semaudit.relate import interpret as _interpret
from semaudit.verify import steps as _steps

SKIP = {"approvals.yaml"}          # approving later does not change what was measured


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def contract_files(contract_dir: Path) -> dict[str, str]:
    return {str(p.relative_to(contract_dir)): sha256_file(p) for p in sorted(contract_dir.rglob("*"))
            if p.is_file() and p.name not in SKIP and "__pycache__" not in p.parts}


def adapter_path(contract_dir: Path, contract: Contract) -> Path | None:
    spec = contract.app.adapter if contract.app else None
    if spec and (spec.endswith(".py") or "/" in spec):
        return (contract_dir / spec).resolve()
    return None


def code_revision() -> dict[str, Any]:
    root = Path(semaudit.__file__).resolve().parents[2]
    try:
        rev = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True,
                             check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--", "src"],
                                    capture_output=True, text=True, check=True).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        rev, dirty = None, None
    return {"git": rev, "src_dirty": dirty}


def prompt_digests(contract: Contract) -> dict[str, str]:
    return {"extraction": _sha([_extract.PROMPT, contract.rubric, _extract.extraction_schema(contract)]),
            "interpret": _sha([_interpret.INSTRUCTIONS, _interpret.LABEL_SCHEMA]),
            "defense": _sha([_steps.DEFENSE_INSTRUCTIONS, _steps.DEFENSE_SCHEMA])}


def episode_digests(run_dir: Path, releases: list[str]) -> dict[str, str]:
    return {str(p.relative_to(run_dir)): sha256_file(p) for rel in releases
            for p in sorted((run_dir / "episodes" / rel).glob("*.json"))}


def build(contract_dir: Path, contract: Contract, run_dir: Path, base: str, head: str, *, router,
          models: bool, max_usd: float, repro_run: str | None) -> dict[str, Any]:
    ad = adapter_path(contract_dir, contract)
    return {
        "schema": "semaudit.manifest/1",
        "code": code_revision(),
        "contract": {"dir": str(contract_dir.resolve()), "files": contract_files(contract_dir),
                     "adapter": {"path": str(ad), "sha256": sha256_file(ad)} if ad and ad.is_file() else None},
        "releases": {"base": base, "head": head},
        "run_dir": str(run_dir.resolve()),
        "episodes": episode_digests(run_dir, [base, head]),
        "repro_run": repro_run,
        "models": {role: spec["model"] for role, spec in router.roles.items()} if router else {},
        "prompts": prompt_digests(contract),
        "verifier": {"models": models, "per_occurrence": True,
                     "steps": ["reproduced", "evidence_linked", "cross_model", "defended", "oracle_checked"]},
        "max_usd": max_usd,
    }


def contract_problems(manifest: dict, contract: Contract) -> list[str]:
    """Differences between the contract (and adapter) now and as the review pinned them."""
    d = Path(manifest["contract"]["dir"])
    if not d.is_dir():
        return [f"contract directory {d} is gone"]
    now, then = contract_files(d), manifest["contract"]["files"]
    out = [f"contract file {f} {'removed' if f not in now else 'added' if f not in then else 'changed'}"
           for f in sorted(set(now) | set(then)) if now.get(f) != then.get(f)]
    ad = manifest["contract"].get("adapter")
    if ad:
        p = Path(ad["path"])
        if not p.is_file() or sha256_file(p) != ad["sha256"]:
            out.append(f"adapter {p} changed")
    if manifest["prompts"] != prompt_digests(contract):
        out.append("model prompts changed since the review")
    return out


def episode_problems(manifest: dict) -> list[str]:
    run_dir = Path(manifest["run_dir"])
    out = []
    for rel, digest in manifest["episodes"].items():
        p = run_dir / rel
        if not p.is_file():
            out.append(f"episode {rel} missing")
        elif sha256_file(p) != digest:
            out.append(f"episode {rel} changed since the review")
    return out
