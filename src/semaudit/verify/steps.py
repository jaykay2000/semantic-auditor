"""Verification and confidence for issues (W9).

Verification records which checks actually ran and how each came out. Confidence is computed from a basis
(evidence kind, cross-model agreement, the defense, unknowns). Severity never enters either; each of the three
can change while the other two stay fixed.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from semaudit.contract.schema import Contract
from semaudit.decide.issues import Issue, cited_events
from semaudit.extract.messages import extract_unique
from semaudit.models.router import Router
from semaudit.relate.interpret import model_interpreter, story_view
from semaudit.relate.rules import p2_candidates
from semaudit.story.align import event_keys
from semaudit.story.episode import Episode
from semaudit.story.model import Story
from semaudit.verify.evidence import resolve

FIELDS = ("message_kind", "decision", "action", "strength", "explains_own_tradeoff")


def rule_fields(contract: Contract, rule_id: str) -> tuple[str, ...]:
    """The extracted fields a rule's verdict actually depends on: the cross-check compares only these."""
    r = contract.rule(rule_id)
    if r.kind == "coherence":
        return ("message_kind", "decision", "action")
    if r.kind == "conditional":
        return ("message_kind", "decision", "strength", "explains_own_tradeoff")
    if "message_kind" in r.applies_to:
        return ("message_kind",)
    if r.check.get("must") == "precondition_holds_at_shown_time":
        return ("message_kind", "decision", "action")
    return ()                                   # fact rules: claims are compared instead

DEFENSE_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["strongest_defense", "defense_succeeds"],
    "properties": {"strongest_defense": {"type": "string"}, "defense_succeeds": {"type": "boolean"}},
}

DEFENSE_INSTRUCTIONS = """You are the product team defending a release against one reported issue.
Using ONLY the owner's rules and exceptions given and the messages the traveller actually saw, make the
strongest honest case that this is NOT a violation (an exception applies, the cited messages do not say what
the report claims, the timing is different, the rule does not apply to this case). Write that defense first.
Then set defense_succeeds: true if your defense shows the rule is NOT broken by what the traveller actually
saw; false if the violation still holds despite your best defense. Do not invent messages, rules or facts."""


# ---------- individual steps ----------

def step_evidence(issue: Issue, stories: dict[str, Story], episodes: dict[str, Episode], run_dir: Path) -> dict:
    problems = []
    for o in issue.occurrences:
        story = stories[o.persona]
        for e in cited_events(o.entry, story):
            if e.kind != "message":
                continue
            ok, why = resolve(e, episodes[o.persona], run_dir)
            if not ok:
                problems.append(f"{o.persona}/{e.id}: {why}")
    return {"result": "fail" if problems else "pass", "detail": problems or "every cited message resolves"}


def step_reproduced(issue: Issue, stories: dict[str, Story], repro: dict[str, Story] | None) -> dict:
    if repro is None:
        return {"result": "not_run", "detail": "no re-capture"}
    missing = []
    for o in issue.occurrences:
        fresh = repro.get(o.persona)
        if fresh is None:
            missing.append(f"{o.persona}: not re-captured")
            continue
        old_k, new_k = event_keys(stories[o.persona]), event_keys(fresh)
        new_by_key = {new_k[e.id]: e for e in fresh.events}
        for e in cited_events(o.entry, stories[o.persona]):
            again = new_by_key.get(old_k[e.id])
            if again is None or again.text != e.text or again.at != e.at:
                missing.append(f"{o.persona}/{e.id}")
    return {"result": "fail" if missing else "pass", "detail": missing or "same events, same text, same time"}


def step_cross_model(issue: Issue, stories: dict[str, Story], contract: Contract, router: Router, *,
                     fresh: bool) -> dict:
    """Independent re-derivation: the other model re-extracts every cited message (and, for coherence issues,
    re-labels the candidate); the rules then run again on that reading. Passes only if the same violation
    (rule, subject, and label for P2) comes out again. Agreement with the first model is not the test."""
    from semaudit.relate.rules import evaluate
    o = issue.occurrences[0]
    story = stories[o.persona].model_copy(deep=True)
    cited = [e for e in cited_events(o.entry, story) if e.kind == "message"]
    msgs = [{"feature": e.feature, "channel": e.channel, "text": e.text} for e in cited]
    other = extract_unique(msgs, contract, router, fresh=fresh, role="cross_checker_extract") if msgs else {}
    changed = []
    for e in cited:
        x = other[(e.feature or "", e.channel or "", e.text)]
        diffs = [f for f in rule_fields(contract, issue.rule) if getattr(x, f) != getattr(e.extraction, f)]
        if diffs:
            changed.append(f"{e.id}: {', '.join(f'{f} {getattr(e.extraction, f)}->{getattr(x, f)}' for f in diffs)}")
        e.extraction = x
    interp = model_interpreter(router, fresh=fresh, rng=random.Random(f"x:{issue.id}"), role="cross_checker_interpret")
    again = [x for x in evaluate(story, contract, interp)
             if x.rule == issue.rule and x.status == "violated"
             and (x.subject == o.entry.subject or issue.rule_kind != "coherence" and x.subject in o.events)]
    same = [x for x in again if issue.rule_kind != "coherence" or x.label == o.entry.label]
    if same:
        return {"result": "pass", "detail": "re-derived with the other model" + (f" (reading differs: {changed})"
                                                                                if changed else "")}
    why = f"other model's reading does not produce this violation; {changed or 'same reading'}"
    if again and not same:
        why = f"re-derived with a different label: {again[0].label}"
    return {"result": "fail", "detail": why}


def step_defended(issue: Issue, stories: dict[str, Story], contract: Contract, router: Router, *,
                  fresh: bool) -> dict:
    o = issue.occurrences[0]
    story = stories[o.persona]
    rule = contract.rule(issue.rule)
    payload = {
        "issue": {"rule": rule.id, "rule_text": rule.text, "label": issue.label, "why": issue.why,
                  "exception_conditions": [list(c) for c in o.entry.conditions]},
        "exceptions": [{"id": e.id, "conditions": [c.model_dump(exclude_none=True) for c in e.conditions],
                        "scope": e.scope} for e in rule.exceptions],
        "cited_messages": [{"id": e.id, "feature": e.feature, "channel": e.channel, "at": e.at.isoformat(),
                            "text": e.text} for e in cited_events(o.entry, story) if e.kind == "message"],
        "story_in_time_order": story_view(story),
    }
    r = router.complete("defender", [{"role": "system", "content": DEFENSE_INSTRUCTIONS},
                                     {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=1)}],
                        schema=DEFENSE_SCHEMA, schema_name="defense", fresh=fresh)
    holds = not r.parsed["defense_succeeds"]
    return {"result": "pass" if holds else "fail", "detail": r.parsed["strongest_defense"][:400]}


def step_oracle(issue: Issue, stories: dict[str, Story], contract: Contract) -> dict:
    if issue.layer != "factual":
        return {"result": "not_applicable", "detail": "not a factual issue"}
    facts = set(contract.rule(issue.rule).check.get("claims", []))
    gaps = []
    for o in issue.occurrences:
        story = stories[o.persona]
        for e in cited_events(o.entry, story):
            for c in (e.extraction.claims if e.extraction else []):
                if c["type"] not in facts:
                    continue
                if story.truth_at(c["type"], e.at, e.feature) is None and story.final_truth(c["type"], e.feature) is None:
                    gaps.append(f"{o.persona}/{e.id}: no oracle value for {c['type']}")
    return {"result": "fail" if gaps else "pass", "detail": gaps or "claims compared with oracle readings"}


# ---------- status and confidence ----------

def verification_status(steps: dict[str, dict]) -> dict:
    res = {k: v["result"] for k, v in steps.items()}
    applicable = {k: v for k, v in res.items() if v != "not_applicable"}
    if res.get("reproduced") == "fail":
        status, reason = "failed", "not_reproducible"
    elif res.get("evidence_linked") == "fail":
        status, reason = "failed", "evidence_unresolved"
    elif res.get("cross_model") == "fail" and res.get("defended") == "fail":
        status, reason = "failed", "disputed"
    elif all(v == "not_run" for v in applicable.values()):
        status, reason = "unverified", ""
    elif all(v == "pass" for v in applicable.values()):
        status, reason = "verified", ""
    else:
        status, reason = "partially_verified", ", ".join(k for k, v in applicable.items() if v != "pass")
    return {"status": status, "reason": reason, "steps": steps}


def evidence_kind(issue: Issue, contract: Contract) -> str:
    """measured: the violation is decided by code against oracles or state; interpreted: it rests on a
    model judgement (a P2 label, a retrospective classification, a judged exception condition)."""
    rule = contract.rule(issue.rule)
    if rule.kind == "coherence" or "message_kind" in rule.applies_to:
        return "interpreted"
    judged = {c.id for e in rule.exceptions for c in e.conditions if c.kind == "judged"}
    failing = {c for c, v in issue.occurrences[0].entry.conditions if v != "met"}
    return "interpreted" if failing & judged else "measured"


def confidence_of(issue: Issue, steps: dict[str, dict], contract: Contract,
                  reduced_independence: bool = False) -> dict:
    basis, level = [], "high"
    kind = evidence_kind(issue, contract)
    basis.append(f"evidence: {kind}")
    cm = steps.get("cross_model", {}).get("result", "not_run")
    df = steps.get("defended", {}).get("result", "not_run")
    basis.append({"pass": "independent model agrees", "fail": "independent model disagrees",
                  "not_run": "no independent model check"}[cm])
    basis.append({"pass": "defense failed to explain it away", "fail": "defense explained it away",
                  "not_run": "no defense run"}[df])
    unknown = any(o.entry.meta.get("unknown_validity") for o in issue.occurrences) or \
        any(v == "unknown" for o in issue.occurrences for _, v in o.entry.conditions)
    if unknown:
        basis.append("an unknown validity or exception condition")
    if cm == "fail" or df == "fail":
        level = "low"
    elif cm == "not_run" or df == "not_run" or unknown:
        level = "medium"
    if reduced_independence and cm != "not_run":
        basis.append("reduced independence: the cross-check model is from the same family")
    return {"level": level, "basis": basis}


def same_family(router: Router, a: str, b: str) -> bool:
    fam = lambda role: "-".join(router.roles[role]["model"].split("-")[:2])  # noqa: E731
    return fam(a) == fam(b)


def verify(issue: Issue, stories: dict[str, Story], episodes: dict[str, Episode], run_dir: Path,
           contract: Contract, router: Router, *, repro: dict[str, Story] | None, fresh: bool = False,
           models: bool = True) -> None:
    steps: dict[str, Any] = {
        "reproduced": step_reproduced(issue, stories, repro),
        "evidence_linked": step_evidence(issue, stories, episodes, run_dir),
        "cross_model": step_cross_model(issue, stories, contract, router, fresh=fresh) if models
        else {"result": "not_run", "detail": "models off"},
        "defended": step_defended(issue, stories, contract, router, fresh=fresh) if models
        else {"result": "not_run", "detail": "models off"},
        "oracle_checked": step_oracle(issue, stories, contract),
    }
    issue.verification = verification_status(steps)
    issue.confidence = confidence_of(issue, steps, contract,
                                     reduced_independence=bool(router) and models
                                     and same_family(router, "extractor", "cross_checker_extract"))
