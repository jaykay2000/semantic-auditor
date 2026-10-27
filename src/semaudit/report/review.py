"""Assemble a release review: issues, verification, policy, not-raised list and the per-persona stories (W9).

Writes runs/<id>/review.json, the single input of the Release Story page (docs/design/release-story.md).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from semaudit.contract.schema import Contract
from semaudit.decide.issues import Issue, apply_delta, build_issues, condition_details
from semaudit.decide.pipeline import ReleaseEval
from semaudit.relate.rules import validity
from semaudit.story.align import align
from semaudit.story.model import Story

CLEARED_LABELS = {"explained_tradeoff", "compatible"}


def not_raised(head: ReleaseEval, failed: list[Issue], contract: Contract) -> list[dict]:
    out = []
    for persona, (story, entries) in sorted(head.results.items()):
        by = {e.id: e for e in story.events}
        for e in entries:
            if e.status == "excepted":
                out.append({"persona": persona, "rule": e.rule, "subjects": [e.subject], "status": "excepted",
                            "label": None, "conditions": [list(c) for c in e.conditions],
                            "reason": "exception applies: " + ", ".join(f"({c}) {v}" for c, v in e.conditions)})
            elif e.rule == contract.rules_of("coherence")[0].id and e.status == "passed" and e.label in CLEARED_LABELS:
                rid = e.meta.get("reconciler")
                when = f" by {rid} at {by[rid].at:%H:%M:%S}" if rid in by else ""
                out.append({"persona": persona, "rule": e.rule, "subjects": [e.subject], "status": "passed",
                            "label": e.label, "conditions": [],
                            "reason": f"{e.label.replace('_', ' ')}{when}, while both were live and before deciding"})
    for i in failed:
        out.append({"persona": ",".join(i.personas), "rule": i.rule, "subjects": [i.id], "status": "not_raised",
                    "label": i.label, "conditions": [],
                    "reason": f"verification failed: {i.verification['reason']}"})
    return out


def capture_view(ep, evidence) -> dict | None:
    """Where the page can show this message: the screenshot and the element's box (web), or the raw text."""
    if evidence is None or ep is None:
        return None
    cap = next((c for c in ep.captures() if c.id == evidence.capture_id), None)
    if cap is None:
        return None
    el = cap.elements[evidence.element]
    return {"kind": cap.kind, "surface": cap.surface, "url": cap.url, "screenshot": cap.files.get("screenshot"),
            "bbox": el.bbox.model_dump() if el.bbox else None}


def event_row(e, story: Story, contract: Contract, ep=None) -> dict:
    row: dict[str, Any] = {"id": e.id, "at": e.at.isoformat(), "kind": e.kind}
    if e.kind == "user_action":
        row["action"] = e.action
        return row
    live = validity(e, story, contract) if e.extraction and e.extraction.message_kind == "directive" else None
    row.update(feature=e.feature, surface=e.surface, channel=e.channel, text=e.text, message_key=e.copy_key,
               user_initiated=e.user_initiated,
               extraction=e.extraction.model_dump() if e.extraction else None,
               evidence=e.evidence.model_dump() if e.evidence else None,
               capture=capture_view(ep, e.evidence),
               live_until=(live.end.isoformat() if live.end else None) if live else None,
               live_basis=live.basis if live else None,
               step_id=f"s{e.evidence.step:02d}" if e.evidence else None)
    return row


def _span(hours: float) -> str:
    return f"{round(hours / 24)} days away" if abs(hours) >= 48 else f"{round(hours)} hours away"


def context_summary(context: dict, contract: Contract, start) -> list[str]:
    """The persona's situation in the contract's own words (Subject.context `show`), in declared order."""
    out = []
    for f in contract.subject.context:
        v = context.get(f.id)
        if f.show is None or v is None:
            continue
        if isinstance(f.show, dict):
            key = str(v).lower() if isinstance(v, bool) else str(v)
            text = f.show.get(key, f.show.get("*"))
            if text is None:
                continue
        else:
            text = f.show
        when = _span((v - start).total_seconds() / 3600) if f.type == "time" and start is not None else ""
        out.append(text.replace("{v}", str(v)).replace("{in}", when))
    return out


def persona_view(persona: str, story: Story, base: Story | None, contract: Contract, ev: ReleaseEval,
                 base_ev: ReleaseEval | None = None) -> dict:
    diff = align(base, story) if base else None
    steps = [{"step_id": f"s{st.seq:02d}", "at": st.at.isoformat(), "do": st.do, "status": st.status}
             for st in ev.episodes[persona].steps]
    events = []
    for e in story.events:
        row = event_row(e, story, contract, ev.episodes.get(persona))
        if diff:
            row["delta"] = diff.head_status(e.id)
            row["base_event"] = diff.base_of(e.id)
        events.append(row)
    by_id = {e.id: e for e in story.events}
    evaluations = []
    for x in ev.results[persona][1]:
        e = by_id.get(x.subject)
        detail = condition_details(contract.rule(x.rule), x, e, story) if e is not None and x.conditions else []
        evaluations.append({"rule": x.rule, "subject": x.subject, "status": x.status, "label": x.label,
                            "conditions": detail, "note": x.note[:200]})
    persona_c = contract.persona(persona)
    start = ev.episodes[persona].steps[0].at if ev.episodes[persona].steps else None
    view = {"id": persona, "name": persona_c.name, "role": persona_c.role,
        "context": {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in story.context.items()},
        "summary": context_summary(story.context, contract, start),
        "steps": steps, "events": events, "evaluations": evaluations,
        "state_steps": [{"at": st.at.isoformat(), "state": story.state_at(st.at, contract.state, inclusive=True)}
                        for st in ev.episodes[persona].steps],
        "state": [{"at": s["at"].isoformat() if hasattr(s["at"], "isoformat") else s["at"], "truth": s["truth"]}
                  for s in story.snapshots]}
    if diff:
        view["removed_from_base"] = list(diff.removed)
        bep = base_ev.episodes.get(persona) if base_ev else None
        view["base_events"] = [event_row(b, base, contract, bep) for b in base.events]
        view["base_state_steps"] = [{"at": st.at.isoformat(),
                                     "state": base.state_at(st.at, contract.state, inclusive=True)}
                                    for st in bep.steps] if bep else []
        view["base_steps"] = [{"step_id": f"s{st.seq:02d}", "at": st.at.isoformat(), "do": st.do, "status": st.status}
                              for st in bep.steps] if bep else []
    return view


def issue_dict(i: Issue, stories: dict[str, Story], contract: Contract) -> dict:
    rule = contract.rule(i.rule)
    o = i.occurrences[0]
    return {
        "id": i.id, "layer": i.layer, "rule": i.rule, "rule_kind": i.rule_kind, "label": i.label,
        "personas": i.personas, "features": i.features, "delta": i.delta, "delta_basis": i.delta_basis,
        "why": i.why, "rule_text": rule.text, "rule_source": rule.source.model_dump() if rule.source else None,
        "conditions": [list(c) for c in o.entry.conditions],
        "occurrences": [{"persona": x.persona, "events": x.events, "timing": x.timing,
                         "also": [asdict(a) | {"conditions": [list(c) for c in a.conditions]} for a in x.also]}
                        for x in i.occurrences],
        "severity": i.severity, "confidence": i.confidence, "verification": i.verification,
        "repro": f"semaudit repro {i.id}",
    }


def other_rules(i: Issue, results: dict[str, tuple[Story, list]]) -> list[dict]:
    """Every rule evaluated on the issue's cited events (first occurrence): passes and exceptions included."""
    o = i.occurrences[0]
    story, entries = results[o.persona]
    cited = set(o.events)
    return [{"rule": e.rule, "subject": e.subject, "status": e.status, "label": e.label,
             "conditions": [list(c) for c in e.conditions]}
            for e in entries if e.subject in cited and (e.rule, e.status) != (i.rule, "violated")]


def assemble(base: ReleaseEval, head: ReleaseEval, contract: Contract, verified: list[Issue],
             resolved: list[Issue], spent_usd: float) -> dict:
    open_issues = [i for i in verified if i.verification.get("status") != "failed"]
    failed = [i for i in verified if i.verification.get("status") == "failed"]
    row, idx = contract.policy.evaluate([{"severity": i.severity["level"], "confidence": i.confidence["level"],
                                          "verification": i.verification["status"]} for i in open_issues])
    stories = {p: s for p, (s, _) in head.results.items()}
    base_stories = {p: s for p, (s, _) in base.results.items()}
    issues = []
    for i in open_issues:
        d = issue_dict(i, stories, contract)
        d["other_rules"] = other_rules(i, head.results)
        issues.append(d)
    return {
        "schema": "semaudit.review/1",
        "generated_at_sim": None,
        "release": {"base": base.release, "head": head.release},
        "app": contract.app.model_dump() if contract.app else None,
        "subject": {"noun": contract.subject.noun},
        "features": [{"id": f.id, "name": f.name or f.id, "core": f.core} for f in contract.features],
        "rules": [{"id": r.id, "kind": r.kind, "text": r.text, "title": r.title} for r in contract.rules],
        "policy": {"recommendation": row.recommendation, "row": idx + 1, "rule_fired": row.text},
        "owner_decision": {"status": "pending"},
        "issues": issues,
        "resolved": [issue_dict(i, base_stories, contract) for i in resolved],
        "not_raised": not_raised(head, failed, contract),
        "not_measured": {"base": base.not_measured, "head": head.not_measured},
        "personas": [persona_view(p, s, base_stories.get(p), contract, head, base) for p, s in sorted(stories.items())],
        "cost_usd": round(spent_usd, 4),
        "written_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def write(review: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(review, indent=1, ensure_ascii=False, default=str))
    return path


__all__ = ["assemble", "write", "build_issues", "apply_delta"]
