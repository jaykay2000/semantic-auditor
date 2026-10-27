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

GROUNDS = ["exception_applies", "extraction_wrong", "reconciled", "timing", "rule_does_not_apply", "none"]
FIELDS_DISPUTABLE = ["message_kind", "decision", "action", "strength", "explains_own_tradeoff"]

DEFENSE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["strongest_defense", "ground", "exception_conditions_met", "disputed_readings",
                 "reconciling_event_id", "addresses_actions", "defense_succeeds"],
    "properties": {
        "strongest_defense": {"type": "string"},
        "ground": {"type": "string", "enum": GROUNDS},
        "exception_conditions_met": {"type": "array", "items": {"type": "string"}},
        "disputed_readings": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["event_id", "field", "value"],
            "properties": {"event_id": {"type": "string"}, "field": {"type": "string", "enum": FIELDS_DISPUTABLE},
                           "value": {"type": "string"}}}},
        "reconciling_event_id": {"type": "string"},
        "addresses_actions": {"type": "array", "items": {"type": "string"}},
        "defense_succeeds": {"type": "boolean"},
    },
}

DEFENSE_INSTRUCTIONS = """You are the product team defending a release against one reported issue.
Using ONLY the owner's rules and exceptions, the rubric, and the messages the user actually saw, make the
strongest honest case that this is NOT a violation. Write that defense first, then name its ground:
- exception_applies: an exception's conditions all hold; list the condition ids you say are met.
- extraction_wrong: a cited message does not say what its reading says; list each disputed reading as
  {event_id, field, value} with the value you say is correct under the rubric.
- reconciled: another message reconciled the cited recommendations in time; give its id and which of the
  pair's actions it addresses.
- timing: the cited moments did not overlap, or came after the decision the rule protects.
- rule_does_not_apply: the rule's own text, read as a whole, does not cover this case.
- none: you found no honest defense.
The rule applies to each message as the rubric classifies it (its reading is given). Arguing that a message the
rubric classifies as forbidden is nonetheless fine is not a defense; dispute the reading instead.
Then set defense_succeeds: true if your defense shows the rule is NOT broken by what the user actually saw;
false if the violation still holds despite your best defense. Use [] and "" for fields your ground does not use.
Do not invent messages, rules or facts. Your claims are checked against the measured data."""


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


def _cross_one(issue: Issue, o, story: Story, contract: Contract, router: Router, *, fresh: bool,
               readings: dict | None = None) -> tuple[bool, str]:
    from semaudit.relate.rules import evaluate
    story = story.model_copy(deep=True)
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
        if readings is not None:
            readings[e.id] = x
    interp = model_interpreter(router, fresh=fresh, rng=random.Random(f"x:{issue.id}:{o.persona}"),
                               role="cross_checker_interpret")
    again = [x for x in evaluate(story, contract, interp)
             if x.rule == issue.rule and x.status == "violated"
             and (x.subject == o.entry.subject or issue.rule_kind != "coherence" and x.subject in o.events)]
    same = [x for x in again if issue.rule_kind != "coherence" or x.label == o.entry.label]
    if same:
        return True, "re-derived" + (f" (reading differs: {changed})" if changed else "")
    if again:
        return False, f"re-derived with a different label: {again[0].label}"
    return False, f"the other model's reading does not produce this violation; {changed or 'same reading'}"


def step_cross_model(issue: Issue, stories: dict[str, Story], contract: Contract, router: Router, *,
                     fresh: bool, readings: dict[str, dict] | None = None) -> dict:
    """Independent re-derivation, for EVERY occurrence: the other model re-extracts each cited message (and, for
    coherence issues, re-labels the candidate); the rules then run again on that reading. Passes only if the
    same violation (rule, subject, and label for P2) comes out again for every persona the issue groups."""
    if readings is not None:
        for o in issue.occurrences:
            readings.setdefault(o.persona, {})
    per = {o.persona: _cross_one(issue, o, stories[o.persona], contract, router, fresh=fresh,
                                 readings=readings.get(o.persona) if readings is not None else None)
           for o in issue.occurrences}
    ok = all(v for v, _ in per.values())
    return {"result": "pass" if ok else "fail", "detail": {p: d for p, (_, d) in per.items()},
            "occurrences": {p: "pass" if v else "fail" for p, (v, _) in per.items()}}


def adjudicate(defense: dict, issue: Issue, o, story: Story, contract: Contract,
               cross: dict[str, Any] | None) -> tuple[bool, str]:
    """Code checks a successful defense against what was measured. Returns (defense_stands, why).

    A claim about a data condition is decided by its measured value; a disputed reading stands only where the two
    models disagree and the defense takes the other model's reading (a reading both share, or a restatement of
    the reading, is overruled; whether the violation follows from the reading is the cross-check's job); a claimed reconciler must be timely and address
    both actions of the pair. Judged grounds (a reading the models disagree on, timing, the rule's scope) stand.
    """
    if not defense["defense_succeeds"]:
        return False, "the defender found no defense"
    ground = defense["ground"]
    rule = contract.rule(issue.rule)
    if ground == "exception_applies":
        data = {c.id for e in rule.exceptions for c in e.conditions if c.kind == "data"} | {"scope", "expiry"}
        measured = dict(o.entry.conditions)
        wrong = [c for c in defense["exception_conditions_met"] if c in data and measured.get(c) not in (None, "met")]
        if wrong:
            return False, f"overruled: claims {', '.join(wrong)} met; measured {', '.join(measured[c] for c in wrong)}"
        return True, "an exception applies (judged conditions disputed)"
    if ground == "extraction_wrong":
        by = {e.id: e for e in story.events}
        relevant = set(rule_fields(contract, issue.rule))
        for d in defense["disputed_readings"]:
            e = by.get(d["event_id"])
            if e is None or e.extraction is None or d["field"] not in relevant:
                continue
            mine = str(getattr(e.extraction, d["field"])).lower()
            other = cross.get(e.id) if cross else None
            theirs = str(getattr(other, d["field"])).lower() if other is not None else None
            if d["value"].lower() != mine and theirs is not None and d["value"].lower() == theirs:
                return True, f"the models disagree on {e.id}.{d['field']} and the defense takes the other reading"
        return False, "overruled: no disputed reading is one the models disagree on"
    if ground == "reconciled":
        from semaudit.relate.rules import reconciler_addresses_pair, reconciler_is_timely
        cand = next((c for c in p2_candidates(story, contract) if c.subject == o.entry.subject), None)
        rid = defense["reconciling_event_id"]
        if cand is None:
            return True, "reconciled (not a coherence candidate; judged)"
        if not reconciler_is_timely(story, cand, rid, contract):
            return False, f"overruled: {rid or 'no message'} was not shown while both were live and before deciding"
        if not reconciler_addresses_pair(cand, defense["addresses_actions"]):
            return False, f"overruled: {rid} does not address both actions of the pair"
        return True, f"{rid} reconciles the pair in time"
    if ground == "none":
        return False, "the defender named no ground"
    if ground == "rule_does_not_apply" and evidence_kind(issue, contract) == "measured":
        # code applied this rule over contract-declared fields (channels, topics, states, oracle values); a
        # disagreement with how the contract scopes it is the owner's to settle, not grounds to drop the issue
        return False, "overruled: this rule is applied by code from the contract's own definitions"
    return True, f"{ground.replace('_', ' ')} (judged)"


def _defend_one(issue: Issue, o, story: Story, contract: Contract, router: Router, *, fresh: bool,
                cross: dict[str, Any] | None) -> tuple[bool, str]:
    rule = contract.rule(issue.rule)
    cited = [e for e in cited_events(o.entry, story) if e.kind == "message"]
    payload = {
        "issue": {"rule": rule.id, "rule_text": rule.text, "label": issue.label, "why": issue.why,
                  "exception_conditions_measured": [list(c) for c in o.entry.conditions]},
        "exceptions": [{"id": e.id, "conditions": [c.model_dump(exclude_none=True) for c in e.conditions],
                        "scope": e.scope} for e in rule.exceptions],
        **({"exception_measured": o.entry.meta.get("exception")} if len(rule.exceptions) > 1 else {}),
        "rubric": contract.rubric,
        "cited_messages": [{"id": e.id, "feature": e.feature, "channel": e.channel, "at": e.at.isoformat(),
                            "text": e.text, "reading": {f: getattr(e.extraction, f) for f in FIELDS_DISPUTABLE}
                            if e.extraction else None} for e in cited],
        "story_in_time_order": story_view(story),
    }
    r = router.complete("defender", [{"role": "system", "content": DEFENSE_INSTRUCTIONS},
                                     {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=1)}],
                        schema=DEFENSE_SCHEMA, schema_name="defense", fresh=fresh)
    stands, why = adjudicate(r.parsed, issue, o, story, contract, cross)
    return not stands, f"[{r.parsed['ground']}] {why} · {r.parsed['strongest_defense'][:300]}"


def step_defended(issue: Issue, stories: dict[str, Story], contract: Contract, router: Router, *,
                  fresh: bool, cross: dict[str, dict] | None = None) -> dict:
    """The defender argues each occurrence away on that persona's own story; code adjudicates the defense
    against what was measured. The issue holds only if no occurrence's defense stands."""
    per = {o.persona: _defend_one(issue, o, stories[o.persona], contract, router, fresh=fresh,
                                  cross=(cross or {}).get(o.persona))
           for o in issue.occurrences}
    ok = all(v for v, _ in per.values())
    return {"result": "pass" if ok else "fail", "detail": {p: d for p, (_, d) in per.items()},
            "occurrences": {p: "pass" if v else "fail" for p, (v, _) in per.items()}}


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
        basis.append("reduced independence: extractor, cross-checker and defender are one model family")
        if level == "high":                       # agreement within one family is corroboration, not proof
            level = "medium"
            basis.append("capped at medium until an independent model family agrees")
    return {"level": level, "basis": basis}


def same_family(router: Router, a: str, b: str) -> bool:
    fam = lambda role: "-".join(router.roles[role]["model"].split("-")[:2])  # noqa: E731
    return fam(a) == fam(b)


def verify(issue: Issue, stories: dict[str, Story], episodes: dict[str, Episode], run_dir: Path,
           contract: Contract, router: Router, *, repro: dict[str, Story] | None, fresh: bool = False,
           models: bool = True) -> None:
    readings: dict[str, dict] = {}            # persona -> event id -> the cross-checker's reading
    steps: dict[str, Any] = {
        "reproduced": step_reproduced(issue, stories, repro),
        "evidence_linked": step_evidence(issue, stories, episodes, run_dir),
        "cross_model": step_cross_model(issue, stories, contract, router, fresh=fresh, readings=readings) if models
        else {"result": "not_run", "detail": "models off"},
        "defended": step_defended(issue, stories, contract, router, fresh=fresh, cross=readings) if models
        else {"result": "not_run", "detail": "models off"},
        "oracle_checked": step_oracle(issue, stories, contract),
    }
    issue.verification = verification_status(steps)
    issue.confidence = confidence_of(issue, steps, contract,
                                     reduced_independence=bool(router) and models
                                     and same_family(router, "extractor", "cross_checker_extract"))
