"""`semaudit repro`: replay one finding from a review, from scratch, and say exactly what came back.

Two checks, both required:
  evidence  every cited moment of every occurrence is captured again: same message key, feature, text and
            time (user actions: same action at the same time). A cited event the review cannot resolve, or a
            replay that checked nothing, fails; nothing is skipped silently.
  finding   the rules run again on the fresh capture (extraction and interpretation through the model cache,
            so an unchanged message costs nothing) and the same issue comes out: same signature, rule and
            severity, for every persona it reached. For a resolved issue the base finding must re-derive on the
            base release AND be absent from a fresh head capture.

The review's manifest pins the contract, adapter and prompts; a replay against anything else is refused.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from semaudit.capture import Runner
from semaudit.contract.schema import load_contract
from semaudit.decide.issues import build_issues
from semaudit.decide.pipeline import evaluate_release
from semaudit.models.router import Router
from semaudit.report import manifest as mf
from semaudit.story.build import story_from_episode


class CannotReplay(RuntimeError):
    """The replay could not be measured (exit 2), as opposed to a replay that ran and did not reproduce."""


@dataclass
class Check:
    name: str
    ok: bool
    lines: list[str] = field(default_factory=list)


@dataclass
class Replay:
    issue_id: str
    kind: str                       # open | resolved
    checks: list[Check]
    run_dir: Path

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)


def _find(review: dict, issue_id: str) -> tuple[dict, str]:
    for key, kind in (("issues", "open"), ("resolved", "resolved"), ("unconfirmed", "unconfirmed")):
        for i in review.get(key, []):
            if i["id"] == issue_id:
                return i, kind
    raise CannotReplay(f"{issue_id} is not in this review")


def evidence_check(issue: dict, review: dict, release_side: str, fresh: dict) -> Check:
    """release_side: 'events' (head) or 'base_events'. `fresh`: persona -> Story captured just now."""
    views = {p["id"]: {e["id"]: e for e in p.get(release_side, [])} for p in review["personas"]}
    c = Check("evidence", True)
    checked = 0
    for o in issue["occurrences"]:
        story = fresh.get(o["persona"])
        if story is None:
            c.ok = False
            c.lines.append(f"✗ {o['persona']}: not re-captured")
            continue
        for eid in o["events"]:
            want = views.get(o["persona"], {}).get(eid)
            if want is None:
                c.ok = False
                c.lines.append(f"✗ {o['persona']}/{eid}: the review does not record this cited event")
                continue
            if want["kind"] == "message":
                got = [e for e in story.messages() if e.copy_key == want["message_key"] and e.feature == want["feature"]
                       and e.text == want["text"] and e.at.isoformat() == want["at"]]
                what = f"{want['feature']}: \"{want['text'][:70]}\""
            else:
                got = [e for e in story.events if e.kind == "user_action" and e.action == want["action"]
                       and e.at.isoformat() == want["at"]]
                what = f"action {want['action']}"
            checked += 1
            c.ok &= bool(got)
            c.lines.append(f"{'✓' if got else '✗'} {o['persona']} {want['at'][11:19]} {what}")
    if checked == 0:
        c.ok = False
        c.lines.append("✗ no cited event was checked")
    return c


def _sig(i) -> list:
    return json.loads(json.dumps(list(i.signature)))


def finding_check(issue: dict, issues_now: list, personas: list[str], *, expect_present: bool, label: str) -> Check:
    c = Check(label, True)
    match = [i for i in issues_now if _sig(i) == issue["signature"]]
    if not expect_present:
        c.ok = not match
        c.lines.append("✓ absent, as the review says" if c.ok else f"✗ still present as {match[0].id}")
        return c
    if not match:
        c.ok = False
        c.lines.append("✗ the rules no longer produce this issue from the fresh capture")
        return c
    m = match[0]
    for what, now, then in (("rule", m.rule, issue["rule"]), ("severity", m.severity["level"],
                                                               issue["severity"]["level"])):
        ok = now == then
        c.ok &= ok
        c.lines.append(f"{'✓' if ok else '✗'} {what} {now}" + ("" if ok else f" (review: {then})"))
    missing = sorted(set(personas) - set(m.personas))
    c.ok &= not missing
    c.lines.append(f"✓ reached {', '.join(m.personas)}" if not missing else f"✗ not re-derived for {', '.join(missing)}")
    return c


def replay(review_path: Path, issue_id: str, *, max_usd: float, runs_dir: Path | None = None,
           fresh: bool = False, root: Path | None = None) -> Replay:
    review = json.loads(review_path.read_text())
    m = review.get("manifest")
    if not m:
        raise CannotReplay("this review has no manifest (written before replays were pinned); re-run the review")
    issue, kind = _find(review, issue_id)
    if kind == "unconfirmed":
        raise CannotReplay(f"{issue_id} was not measured in head; there is no finding to replay")
    contract_dir = Path(m["contract"]["dir"])
    contract = load_contract(contract_dir)
    changed = mf.contract_problems(m, contract)
    if changed:
        raise CannotReplay("the contract changed since the review: " + "; ".join(changed))
    personas = sorted({o["persona"] for o in issue["occurrences"]})
    rel = review["release"]["base"] if kind == "resolved" else review["release"]["head"]
    runs_dir = runs_dir or Path(m["run_dir"]).parent
    run_id = f"repro-{issue_id[:40]}-{time.strftime('%Y%m%dT%H%M%S')}"
    router = Router(root=root or Path.cwd(), max_usd=max_usd)
    with Runner(contract_dir, runs_dir=runs_dir, run_id=run_id) as run:
        eps = run.capture(rel, personas)
        if kind == "resolved":                 # the fix must hold on a fresh head capture too
            run.capture(review["release"]["head"], personas)
    run_dir = runs_dir / run_id
    stories = {ep.persona: story_from_episode(ep, contract) for ep in eps}
    checks = [evidence_check(issue, review, "base_events" if kind == "resolved" else "events", stories)]

    ev = evaluate_release(run_dir, rel, contract, router, fresh=fresh, personas=set(personas))
    if not ev.complete:
        raise CannotReplay("the fresh capture could not be measured: "
                           + "; ".join(f"{p}: {r[0]}" for p, r in ev.not_measured.items()))
    checks.append(finding_check(issue, build_issues(rel, ev.results, contract), personas, expect_present=True,
                                label=f"finding on {rel}"))
    if kind == "resolved":
        hv = evaluate_release(run_dir, review["release"]["head"], contract, router, fresh=fresh,
                              personas=set(personas))
        if not hv.complete:
            raise CannotReplay("the fresh head capture could not be measured")
        checks.append(finding_check(issue, build_issues(review["release"]["head"], hv.results, contract), personas,
                                    expect_present=False, label=f"absent on {review['release']['head']}"))
    return Replay(issue_id, kind, checks, run_dir)
