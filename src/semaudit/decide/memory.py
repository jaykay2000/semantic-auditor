"""Owner decisions on issues and releases, and what the next review does with them (W11, L6 memory).

`dispositions.yaml` sits beside the contract. Every decision is pinned to the review it was made on (by hash),
the issue's signature, the exact message texts the owner saw, and the rule's content at the time, so a decision
never stretches past what the owner looked at:

- fix           the next review must show the issue resolved; if it is still there it is `still_open`, and if it
                comes back after a release without it, `regressed`.
- not_an_issue  that exact signature, with the same personas and the same message texts, is set aside (listed on
                the not-raised list with the owner's reason). Any variant is raised, with what differs.
- accept        only for a conditional rule whose nearest exception failed on scope alone: a new exception with
                the same conditions, scoped to exactly the features, components and surfaces of the issue's events.
                It becomes part of the contract (merged by `load_contract`) and is approved by the decision itself.

A decision made under a different version of the rule is `stale` and does not apply. Release decisions (ship /
ship with notes / hold) are recorded beside the review's recommendation and never change it.

Each review records the issue decisions it applied (`manifest.memory`), so repro and verify-report replay
exactly what the review applied, whatever the owner decides later.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from semaudit.contract.approve import approve, rule_digest
from semaudit.contract.schema import MEMORY_FILE, Contract, ExceptionRule, load_contract
from semaudit.contract.validate import validate

ISSUE_KINDS = ("fix", "not_an_issue", "accept")
RELEASE_DECISIONS = ("ship", "ship_with_notes", "hold")
HEADER = ("# Owner decisions on issues and releases. Written by `semaudit decide`, `semaudit decide-release` or\n"
          "# `semaudit serve`. Each is pinned to the review it was made on; see semaudit/decide/memory.py.\n")


class DecisionError(ValueError):
    pass


# ---------- the file ----------

def load(directory: Path) -> dict[str, list[dict]]:
    p = directory / MEMORY_FILE
    data = (yaml.safe_load(p.read_text()) or {}) if p.exists() else {}
    return {"issues": list(data.get("issues") or []), "releases": list(data.get("releases") or [])}


def save(directory: Path, data: dict[str, list[dict]]) -> None:
    (directory / MEMORY_FILE).write_text(HEADER + yaml.safe_dump(
        {"issues": data["issues"], "releases": data["releases"]}, sort_keys=False, allow_unicode=True))


def snapshot(directory: Path) -> dict[str, Any]:
    """What a review applies, recorded in its manifest: the issue decisions, in full, and their digest."""
    issues = load(directory)["issues"]
    return {"file": MEMORY_FILE, "issues": issues, "sha256": digest(issues)}


def digest(issues: list[dict]) -> str:
    return hashlib.sha256(json.dumps(issues, sort_keys=True, default=str).encode()).hexdigest()


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------- fingerprints: what the owner saw ----------

def _row_text(row: dict) -> str:
    return row["text"] if row.get("kind") == "message" else f"<{row.get('action')}>"


def _event_text(e) -> str:
    return e.text if e.kind == "message" else f"<{e.action}>"


def fingerprint_from_review(issue: dict, review: dict) -> list[dict]:
    rows = {p["id"]: {e["id"]: e for e in p["events"]} for p in review["personas"]}
    return [{"persona": o["persona"], "texts": [_row_text(rows[o["persona"]][eid]) for eid in o["events"]]}
            for o in issue["occurrences"]]


def fingerprint(issue, stories: dict) -> list[dict]:
    out = []
    for o in issue.occurrences:
        by = {e.id: e for e in stories[o.persona].events}
        out.append({"persona": o.persona, "texts": [_event_text(by[eid]) for eid in o.events]})
    return out


def _fp_set(fp: list[dict]) -> set[tuple]:
    return {(x["persona"], tuple(x["texts"])) for x in fp}


# ---------- recording ----------

def _review_and_contract(review_path: Path) -> tuple[dict, Path, Contract]:
    from semaudit.report import manifest as mf
    review = json.loads(review_path.read_text())
    m = review.get("manifest")
    if not m:
        raise DecisionError("this review has no manifest; re-run the review before deciding on it")
    contract_dir = Path(m["contract"]["dir"])
    contract = load_contract(contract_dir)
    changed = mf.contract_problems(m, contract)
    if changed:
        raise DecisionError("the contract changed since this review, so it no longer shows what a decision would "
                            "apply to; re-run the review first (" + "; ".join(changed) + ")")
    return review, contract_dir, contract


def _next_id(data: dict) -> str:
    n = max([int(d["id"].split("-")[1]) for d in data["issues"]] or [0]) + 1
    return f"D-{n:03d}"


def accepted_exceptions(issue: dict, review: dict, contract: Contract, *, by: str, on: str, expires: str,
                        review_file: str) -> list[dict]:
    """The narrowest exceptions that clear exactly this issue's events, or DecisionError saying why not."""
    rule = contract.rule(issue["rule"])
    if rule.kind != "conditional":
        raise DecisionError(f"{rule.id} is a {rule.kind} rule; exceptions exist only for conditional rules "
                            "(an exception never clears a universal, coherence or load rule). Use fix or not-an-issue.")
    if not rule.exceptions:
        raise DecisionError(f"{rule.id} has no exception to narrow from; write one in the contract and approve it")
    rows = {p["id"]: {e["id"]: e for e in p["events"]} for p in review["personas"]}
    by_ex = {x.id: x for x in rule.exceptions}
    triples: dict[tuple, ExceptionRule] = {}
    for o in issue["occurrences"]:
        ex = by_ex.get(o.get("exception") or "")
        failing = sorted(c for c, v in o.get("conditions", []) if v != "met")
        if ex is None:
            raise DecisionError(f"{o['persona']}: no measured exception on this occurrence")
        if failing != ["scope"]:
            raise DecisionError(f"{o['persona']}: {ex.id} failed on {', '.join(failing)}, not on scope alone. "
                                "Accepting would drop a condition; change the exception in the contract instead.")
        for eid in o["events"]:
            e = rows[o["persona"]][eid]
            if e.get("kind") == "message":
                triples[(ex.id, e["feature"], e.get("component"), e["surface"])] = ex
    taken = {x.id for x in rule.exceptions}
    out, n = [], 1
    for (ex_id, feature, component, surface), ex in sorted(triples.items(), key=lambda kv: kv[0][1:]):
        while f"{rule.id}-E{n}" in taken:
            n += 1
        new_id = f"{rule.id}-E{n}"
        taken.add(new_id)
        scope = {"features": [feature], "surfaces": [surface]}
        if component:
            scope["components"] = [component]
        out.append({"id": new_id, "conditions": [c.model_dump(exclude_none=True) for c in ex.conditions],
                    "scope": scope, "approved": {"by": by, "date": on, "expires": expires},
                    "source": {"kind": "review", "file": review_file, "at": issue["id"], "by": by, "date": on}})
    return out


def decide_issue(review_path: Path, issue_id: str, kind: str, *, by: str, reason: str | None = None,
                 expires: str | None = None, on: str | None = None) -> dict:
    """Record an owner decision on one open issue of a review. Returns the stored decision."""
    if kind not in ISSUE_KINDS:
        raise DecisionError(f"unknown decision {kind!r}; one of {', '.join(ISSUE_KINDS)}")
    if not by:
        raise DecisionError("a decision needs the name of who made it (--by)")
    review, contract_dir, contract = _review_and_contract(review_path)
    issue = next((i for i in review["issues"] if i["id"] == issue_id), None)
    if issue is None:
        raise DecisionError(f"{issue_id} is not an open issue of this review")
    if kind == "not_an_issue" and not (reason or "").strip():
        raise DecisionError("not-an-issue needs a reason (--reason): it is what the next reviewer reads")
    on = on or date.today().isoformat()
    data = load(contract_dir)
    d = {"id": _next_id(data), "kind": kind, "issue": issue_id, "signature": issue["signature"],
         "rule": issue["rule"], "rule_digest": rule_digest(contract.rule(issue["rule"])),
         "review": str(review_path), "review_sha256": sha256_file(review_path), "release": review["release"]["head"],
         "occurrences": fingerprint_from_review(issue, review), "by": by, "date": on}
    if reason:
        d["reason"] = reason.strip()
    if kind == "accept":
        if not expires:
            raise DecisionError("accept needs an expiry (--expires YYYY-MM-DD): exceptions must expire")
        if date.fromisoformat(expires) < date.fromisoformat(on):
            raise DecisionError(f"expiry {expires} is before {on}")
        d["exceptions"] = accepted_exceptions(issue, review, contract, by=by, on=on, expires=expires,
                                              review_file=str(review_path))
        merged = load_contract(contract_dir, memory=data["issues"] + [d])
        problems = sorted(set(validate(merged)) - set(validate(contract)))
        if problems:
            raise DecisionError("the accepted exception does not validate: " + "; ".join(problems))
    supersedes = [x["id"] for x in data["issues"] if x["signature"] == d["signature"]]
    if supersedes:
        d["supersedes"] = supersedes
    data["issues"].append(d)
    save(contract_dir, data)
    if kind == "accept":           # the decision is the owner's approval of exactly these exceptions
        merged = load_contract(contract_dir)
        approve(contract_dir, merged, [f"exception:{x['id']}" for x in d["exceptions"]], by=by, on=on)
    return d


def decide_release(review_path: Path, decision: str, *, by: str, note: str | None = None,
                   on: str | None = None) -> dict:
    if decision not in RELEASE_DECISIONS:
        raise DecisionError(f"unknown release decision {decision!r}; one of {', '.join(RELEASE_DECISIONS)}")
    if not by:
        raise DecisionError("a decision needs the name of who made it (--by)")
    review, contract_dir, _ = _review_and_contract(review_path)
    data = load(contract_dir)
    d = {"review": str(review_path), "review_sha256": sha256_file(review_path),
         "base": review["release"]["base"], "head": review["release"]["head"], "decision": decision,
         "by": by, "date": on or date.today().isoformat(),
         "review_said": {"outcome": review["outcome"]["status"], "recommendation": review["outcome"]["recommendation"],
                         "policy": review["policy"]["recommendation"]}}
    if note:
        d["note"] = note.strip()
    data["releases"].append(d)
    save(contract_dir, data)
    return d


def decisions_for(review_path: Path, directory: Path) -> dict[str, Any]:
    """The owner's decisions made on this exact review (by hash), latest first, for the page."""
    sha = sha256_file(review_path)
    data = load(directory)
    issues: dict[str, dict] = {}
    for d in data["issues"]:
        if d.get("review_sha256") == sha:
            issues[d["issue"]] = d
    rel = [d for d in data["releases"] if d.get("review_sha256") == sha]
    return {"issues": issues, "release": rel[-1] if rel else None}


# ---------- applying memory in the next review ----------

@dataclass
class Applied:
    set_aside: list = field(default_factory=list)      # issues an exact not-an-issue decision removes


def _latest(memory: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for d in memory:
        out[json.dumps(d["signature"])] = d
    return out


def _stamp(d: dict, status: str, note: str) -> dict:
    return {"decision": d["id"], "kind": d["kind"], "by": d["by"], "date": d["date"], "made_on": d["release"],
            "status": status, "note": note, **({"reason": d["reason"]} if d.get("reason") else {})}


def apply(head: list, resolved: list, unconfirmed: list, memory: list[dict], contract: Contract,
          stories: dict) -> Applied:
    """Annotate this review's issues with the owner's past decisions (issue.memory), adjust deltas for fixes, and
    return the issues an exact not-an-issue decision sets aside. Pure: the same inputs give the same result."""
    latest = _latest(memory)
    out = Applied()
    for i in head:
        d = latest.get(json.dumps(json.loads(json.dumps(list(i.signature)))))
        if d is None:
            continue
        if rule_digest(contract.rule(i.rule)) != d["rule_digest"]:
            i.memory = _stamp(d, "stale", f"rule {i.rule} changed since {d['id']}; the decision does not apply")
            continue
        if d["kind"] == "fix":
            if i.delta == "pre_existing":
                i.delta, i.delta_basis = "still_open", f"{i.delta_basis}; marked fix in {d['id']} on {d['release']}"
                i.memory = _stamp(d, "still_open", "marked fix, still present")
            else:
                i.delta, i.delta_basis = "regressed", f"{i.delta_basis}; marked fix in {d['id']} on {d['release']}"
                i.memory = _stamp(d, "regressed", "marked fix, absent from the base, back in this release")
        elif d["kind"] == "not_an_issue":
            now, then = _fp_set(fingerprint(i, stories)), _fp_set(d["occurrences"])
            if now <= then:
                i.memory = _stamp(d, "set_aside", "the exact signature, personas and messages the owner judged")
                out.set_aside.append(i)
            else:
                seen = {p for p, _ in then}
                diffs = []
                new_p = sorted({p for p, _ in now} - seen)
                if new_p:
                    diffs.append("also reaches " + ", ".join(new_p))
                changed = sorted({p for p, t in now - then if p in seen})
                if changed:
                    diffs.append("message text changed for " + ", ".join(changed))
                i.memory = _stamp(d, "variant", "a variant of what the owner judged: " + "; ".join(diffs))
        elif d["kind"] == "accept":
            ids = ", ".join(x["id"] for x in d.get("exceptions", []))
            i.memory = _stamp(d, "not_covered", f"the accepted exception ({ids}) does not cover this occurrence")
    for b in resolved:
        d = latest.get(json.dumps(json.loads(json.dumps(list(b.signature)))))
        if d is not None and d["kind"] == "fix":
            b.memory = _stamp(d, "fix_confirmed", "marked fix, absent in this release where measured")
    for b in unconfirmed:
        d = latest.get(json.dumps(json.loads(json.dumps(list(b.signature)))))
        if d is not None and d["kind"] == "fix":
            b.memory = _stamp(d, "not_confirmed", "marked fix; not every affected persona was measured")
    return out

