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
from semaudit.relate.claims import compare, shown
from semaudit.relate.rules import validity
from semaudit.story.align import align
from semaudit.story.model import Story

CLEARED_LABELS = {"explained_tradeoff", "compatible"}


def measurement(base: ReleaseEval, head: ReleaseEval, contract: Contract, reader: bool = False) -> dict:
    """What was measured: both releases' capture problems, and rules that are not fully evaluated: rules whose facts
    the extraction cannot carry, and rules the engine has no check for, or checks only in part. Such a rule makes the
    measurement incomplete: its silence is not a pass. In reader mode neither applies: no extraction runs (the model
    reads the raw text) and no rule engine runs (the model judges every rule's text)."""
    from semaudit.relate.claims import unmeasurable_rules
    from semaudit.relate.rules import unevaluable_rules
    rules: list[dict] = []
    if not reader:
        why: dict[str, list[str]] = {}
        for x in unmeasurable_rules(contract) + unevaluable_rules(contract):
            why.setdefault(x["rule"], []).append(x["reason"])
        order = {r.id: k for k, r in enumerate(contract.rules)}
        rules = [{"rule": r, "reason": "; ".join(why[r])} for r in sorted(why, key=order.get)]
    out = {"complete": base.complete and head.complete and not rules, "base": base.not_measured,
           "head": head.not_measured}
    if rules:
        out["rules_not_measured"] = rules
    return out


def not_raised(head: ReleaseEval, failed: list[Issue], contract: Contract, set_aside: list[Issue] = ()) -> list[dict]:
    out = []
    coherence = {r.id for r in contract.rules_of("coherence")}   # a contract may have none
    for persona, (story, entries) in sorted(head.results.items()):
        by = {e.id: e for e in story.events}
        for e in entries:
            if e.status == "excepted":
                ex = next((x for x in contract.rule(e.rule).exceptions if x.id == e.meta.get("exception")), None)
                src = ex.source if ex else None
                origin = (f", accepted by {src.by} on {src.date} from {src.at}" if src and src.kind == "review" else "")
                out.append({"persona": persona, "rule": e.rule, "subjects": [e.subject], "status": "excepted",
                            "label": None, "conditions": [list(c) for c in e.conditions],
                            "exception": ex.id if ex else None,
                            "reason": f"exception {ex.id if ex else ''}{origin} applies: "
                                      + ", ".join(f"({c}) {v}" for c, v in e.conditions)})
            elif e.rule in coherence and e.status == "passed" and e.label in CLEARED_LABELS:
                rid = e.meta.get("reconciler")
                when = f" by {rid} at {by[rid].at:%H:%M:%S}" if rid in by else ""
                out.append({"persona": persona, "rule": e.rule, "subjects": [e.subject], "status": "passed",
                            "label": e.label, "conditions": [],
                            "reason": f"{e.label.replace('_', ' ')}{when}, while both were live and before deciding"})
    for i in failed:
        out.append({"persona": ",".join(i.personas), "rule": i.rule, "subjects": [i.id], "status": "not_raised",
                    "label": i.label, "conditions": [],
                    "reason": f"verification failed: {i.verification['reason']}"})
    for i in set_aside:
        m = i.memory
        out.append({"persona": ",".join(i.personas), "rule": i.rule, "subjects": [i.id], "status": "owner_set_aside",
                    "label": i.label, "conditions": [], "memory": m,
                    "reason": f"owner decided not an issue ({m['decision']}, {m['by']}, {m['date']}, on {m['made_on']}): "
                              f"{m.get('reason', '')}; same signature, personas and messages"})
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


def _with_verdicts(e, story: Story) -> dict:
    """The extraction, with each claim's true value and verdict from the one comparison (relate/claims.py),
    so the page never compares a claim itself."""
    x = e.extraction.model_dump()
    for c in x["claims"]:
        truth = story.truth_at(c["type"], e.at, e.feature)
        c["truth"] = truth.isoformat() if hasattr(truth, "isoformat") else truth
        c["verdict"] = None if truth is None else compare(c, truth)
        c["shown"] = shown(c)
    return x


def event_row(e, story: Story, contract: Contract, ep=None) -> dict:
    row: dict[str, Any] = {"id": e.id, "at": e.at.isoformat(), "kind": e.kind}
    if e.kind == "user_action":
        row["action"] = e.action
        return row
    live = validity(e, story, contract) if e.extraction and e.extraction.message_kind == "directive" else None
    row.update(feature=e.feature, component=e.component, surface=e.surface, channel=e.channel, text=e.text, message_key=e.copy_key,
               user_initiated=e.user_initiated,
               extraction=_with_verdicts(e, story) if e.extraction else None,
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
        if isinstance(v, list):                   # a list field: {n} entries, {qty} their summed quantity
            def _q(x):                            # {"qty": 3} / {"quantity": 3} / "slug|variant|3" / anything else: 1
                if isinstance(x, dict):
                    return int(x.get("qty", x.get("quantity", 1)) or 0)
                last = str(x).rsplit("|", 1)[-1]
                return int(last) if "|" in str(x) and last.isdigit() else 1
            qty = sum(_q(x) for x in v)
            text = text.replace("{n}", str(len(v))).replace("{qty}", str(qty))
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


def issue_dict(i: Issue, stories: dict[str, Story], contract: Contract, review_path: str | None = None) -> dict:
    rule = contract.rule(i.rule)
    o = i.occurrences[0]
    return {
        "id": i.id, "signature": json.loads(json.dumps(list(i.signature))), "layer": i.layer, "rule": i.rule, "rule_kind": i.rule_kind, "label": i.label,
        "personas": i.personas, "features": i.features, "delta": i.delta, "delta_basis": i.delta_basis,
        "why": i.why, "rule_text": rule.text, "rule_source": rule.source.model_dump() if rule.source else None,
        "conditions": [list(c) for c in o.entry.conditions],
        "occurrences": [{"persona": x.persona, "events": x.events, "timing": x.timing,
                         "conditions": [list(c) for c in x.entry.conditions],
                         "exception": x.entry.meta.get("exception"),
                         "also": [asdict(a) | {"conditions": [list(c) for c in a.conditions]} for a in x.also],
                         **({"quotes": x.entry.meta["quotes"],
                             "compared_with": x.entry.meta.get("compared_with", [])}
                            if "quotes" in x.entry.meta else {})}
                        for x in i.occurrences],
        "severity": i.severity, "confidence": i.confidence, "verification": i.verification,
        "memory": i.memory or None,
        "repro": f"semaudit repro {i.id} --review {review_path} --max-usd 1" if review_path else None,
    }


def other_rules(i: Issue, results: dict[str, tuple[Story, list]]) -> list[dict]:
    """Every rule evaluated on the issue's cited events (first occurrence): passes and exceptions included."""
    o = i.occurrences[0]
    story, entries = results[o.persona]
    cited = set(o.events)
    return [{"rule": e.rule, "subject": e.subject, "status": e.status, "label": e.label,
             "conditions": [list(c) for c in e.conditions]}
            for e in entries if e.subject in cited and (e.rule, e.status) != (i.rule, "violated")]


def outcome_of(policy_rec: str, measured: bool | dict, approval: dict) -> dict:
    """What the review may actually recommend. The owner's policy decides only over a complete measurement and a
    fully approved contract; otherwise the review says why it cannot decide, and never says ship. `measured`: the
    review's measurement dict (or a bare bool), so the reason names what was not measured."""
    m = measured if isinstance(measured, dict) else {"complete": measured}
    if not m["complete"]:
        gaps = []
        if m.get("base") or m.get("head") or m.get("reader_problems") or not isinstance(measured, dict):
            gaps.append("some personas or surfaces could not be measured")
        if m.get("rules_not_measured"):
            gaps.append(f"{len(m['rules_not_measured'])} rule(s) are not fully evaluated in this mode")
        return {"status": "not_measurable", "recommendation": "not_measurable",
                "reason": "; ".join(gaps or ["the measurement is incomplete"]) + "; see measurement"}
    if not approval["complete"]:
        return {"status": "provisional", "recommendation": "provisional", "policy_would_say": policy_rec,
                "reason": f"{len(approval['pending'])} contract item(s) are not owner-approved at their current "
                          f"content; the release policy's answer is shown but is not an owner decision"}
    return {"status": "decided", "recommendation": policy_rec, "reason": ""}


def assemble(base: ReleaseEval, head: ReleaseEval, contract: Contract, verified: list[Issue],
             resolved: list[Issue], spent_usd: float, *, approval: dict,
             unconfirmed: list[Issue] = (), manifest: dict | None = None, review_path: str | None = None,
             set_aside: list[Issue] = (), reader: dict | None = None) -> dict:
    """`reader`: set in reader mode ({"refused": not_raised rows, "base"/"head": accounting}); the issues then
    come from decide/reader.py and carry no replay command (re-reading needs a fresh capture)."""
    open_issues = [i for i in verified if i.verification.get("status") != "failed"]
    failed = [i for i in verified if i.verification.get("status") == "failed"]
    rows = [{"severity": i.severity["level"], "confidence": i.confidence["level"],
             "verification": i.verification["status"]} for i in open_issues]
    row, idx = contract.policy.evaluate(rows)
    fired_by = [open_issues[k].id for k in contract.policy.fired_by(row, rows)]
    measured_d = measurement(base, head, contract, reader is not None)
    if reader is not None:                  # a reading cut short or with findings it could not express is partial
        probs = [f"{side} reading: {what}" for side in ("base", "head") for what, bad in
                 (("output truncated", (reader.get(side) or {}).get("truncated")),
                  (f"{len((reader.get(side) or {}).get('dropped', []))} finding(s) dropped as malformed",
                   (reader.get(side) or {}).get("dropped"))) if bad]
        if probs:
            measured_d = {**measured_d, "complete": False, "reader_problems": probs}
    stories = {p: s for p, (s, _) in head.results.items()}
    base_stories = {p: s for p, (s, _) in base.results.items()}
    issues = []
    for i in open_issues:
        d = issue_dict(i, stories, contract, None if reader is not None else review_path)
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
        "policy": {"recommendation": row.recommendation, "row": idx + 1, "rule_fired": row.text,
                   "fired_by": fired_by},
        "outcome": outcome_of(row.recommendation, measured_d, approval),
        "measurement": measured_d,
        "approval": approval,
        "issues": issues,
        "resolved": [issue_dict(i, base_stories, contract, None if reader is not None else review_path)
                     for i in resolved],
        "unconfirmed": [issue_dict(i, base_stories, contract) for i in unconfirmed],
        "not_raised": not_raised(head, failed, contract, set_aside) + list((reader or {}).get("refused", [])),
        "mode": "reader" if reader is not None else "rules",
        "reader": {k: v for k, v in (reader or {}).items() if k != "refused"} or None,
        "personas": [persona_view(p, s, base_stories.get(p), contract, head, base) for p, s in sorted(stories.items())],
        "cost_usd": round(spent_usd, 4),
        "manifest": manifest,
        "written_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def write(review: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(review, indent=1, ensure_ascii=False, default=str))
    return path


__all__ = ["assemble", "write", "build_issues", "apply_delta"]
