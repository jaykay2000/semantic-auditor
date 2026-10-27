"""`semaudit verify-report`: is this review.json what its pinned inputs produce?

Offline (model cache only, no spend). Checks that the contract, adapter, prompts and episodes are the ones the
manifest pins; that every cited message still resolves to its captured evidence; and that re-deriving from those
episodes gives the same measurement, issues (signature, rule, severity, personas, delta), resolved and unconfirmed
lists, verification statuses and confidence levels from the recorded steps, and the same policy row and outcome.
A hand-edited review.json, or one built from different inputs, fails here.
"""

from __future__ import annotations

import json
from pathlib import Path

from semaudit.contract.schema import load_contract
from semaudit.decide import memory as mem
from semaudit.decide.issues import apply_delta, build_issues
from semaudit.decide.pipeline import evaluate_release
from semaudit.models.router import ModelError, Router
from semaudit.report import manifest as mf
from semaudit.report.review import outcome_of
from semaudit.verify.steps import confidence_of, same_family, step_evidence, verification_status


class CannotVerify(RuntimeError):
    pass


def _row(i) -> dict:
    return {"signature": json.loads(json.dumps(list(i.signature))), "rule": i.rule,
            "severity": i.severity["level"], "personas": i.personas, "delta": i.delta,
            "memory": (i.memory or {}).get("status")}


def _row_of(d: dict) -> dict:
    return {"signature": d["signature"], "rule": d["rule"], "severity": d["severity"]["level"],
            "personas": d["personas"], "delta": d["delta"], "memory": (d.get("memory") or {}).get("status")}


def verify_report(review_path: Path, *, root: Path | None = None) -> list[str]:
    r = json.loads(review_path.read_text())
    m = r.get("manifest")
    if not m:
        raise CannotVerify("no manifest in this review")
    memory = (m.get("memory") or {}).get("issues", [])
    contract = load_contract(Path(m["contract"]["dir"]), memory=memory)
    problems = mf.contract_problems(m, contract) + mf.episode_problems(m) + mf.memory_problems(m)
    if problems:
        return problems
    run_dir = Path(m["run_dir"])
    base, head = r["release"]["base"], r["release"]["head"]
    router = Router(root=root or Path.cwd(), offline=True)
    try:
        b = evaluate_release(run_dir, base, contract, router)
        h = evaluate_release(run_dir, head, contract, router)
    except ModelError as e:
        raise CannotVerify(f"cannot re-derive offline: {e}") from e

    if r["measurement"] != {"complete": b.complete and h.complete, "base": b.not_measured, "head": h.not_measured}:
        problems.append("measurement differs from what the episodes show")
    head_issues = build_issues(head, h.results, contract)
    resolved, unconfirmed = apply_delta(head_issues, build_issues(base, b.results, contract), set(b.results),
                                        set(h.results))
    applied = mem.apply(head_issues, resolved, unconfirmed, memory, contract, {p: s for p, (s, _) in h.results.items()})
    aside = sorted(i.id for i in applied.set_aside)
    recorded_aside = sorted(s for x in r["not_raised"] if x["status"] == "owner_set_aside" for s in x["subjects"])
    if aside != recorded_aside:
        problems.append(f"set aside by owner decisions: review {recorded_aside}, its recorded decisions give {aside}")
    head_issues = [i for i in head_issues if all(i is not s for s in applied.set_aside)]
    recorded = {d["id"]: d for d in r["issues"]}
    failed_ids = {s for x in r["not_raised"] if x["status"] == "not_raised" for s in x["subjects"]}
    derived = {i.id: i for i in head_issues}
    for iid in sorted(set(derived) - set(recorded) - failed_ids):
        problems.append(f"{iid}: re-derived from the episodes but not in the review")
    for iid in sorted(set(recorded) - set(derived)):
        problems.append(f"{iid}: in the review but not re-derived from the episodes")
    stories = {p: s for p, (s, _) in h.results.items()}
    reduced = same_family(router, "extractor", "cross_checker_extract") if m["verifier"]["models"] else False
    for iid in sorted(set(recorded) & set(derived)):
        d, i = recorded[iid], derived[iid]
        if _row(i) != _row_of(d):
            problems.append(f"{iid}: review says {_row_of(d)}, episodes give {_row(i)}")
        steps = d["verification"]["steps"]
        if verification_status(steps)["status"] != d["verification"]["status"]:
            problems.append(f"{iid}: verification status does not follow from its recorded steps")
        if confidence_of(i, steps, contract, reduced_independence=reduced)["level"] != d["confidence"]["level"]:
            problems.append(f"{iid}: confidence does not follow from its recorded basis")
        ev = step_evidence(i, stories, h.episodes, run_dir)
        if ev["result"] != "pass":
            problems.append(f"{iid}: evidence does not resolve: {ev['detail']}")
    for name, now, then in (("resolved", resolved, r["resolved"]), ("unconfirmed", unconfirmed, r["unconfirmed"])):
        mark = lambda xs: sorted((x.id, (x.memory or {}).get("status")) for x in xs)          # noqa: E731
        if mark(now) != sorted((x["id"], (x.get("memory") or {}).get("status")) for x in then):
            problems.append(f"{name} differs: review {sorted(x['id'] for x in then)}, "
                            f"episodes {sorted(i.id for i in now)}")
    rows = [{"severity": d["severity"]["level"], "confidence": d["confidence"]["level"],
             "verification": d["verification"]["status"]} for d in r["issues"]]
    row, idx = contract.policy.evaluate(rows)
    if (row.recommendation, idx + 1) != (r["policy"]["recommendation"], r["policy"]["row"]):
        problems.append(f"policy: review says row {r['policy']['row']} ({r['policy']['recommendation']}), "
                        f"its issues give row {idx + 1} ({row.recommendation})")
    fired = sorted(r["issues"][k]["id"] for k in contract.policy.fired_by(row, rows))
    if sorted(r["policy"].get("fired_by", [])) != fired:
        problems.append(f"policy: review says it fired on {sorted(r['policy'].get('fired_by', []))}, "
                        f"its issues give {fired}")
    if outcome_of(row.recommendation, b.complete and h.complete, r["approval"]) != r["outcome"]:
        problems.append("outcome does not follow from the policy, the measurement and the recorded approval")
    return problems
