"""From rule evaluations to issues the owner decides on (W9). No model calls here.

An issue groups the same violation (same signature) across personas. Severity is the rule's own level, set by
the owner in the contract; how many test personas an issue reaches, and whether before or after their decision,
is recorded but never changes it (a count of fixtures is not production reach). Confidence and verification are
attached later by the verifier and are never derived from severity, or from each other.
"""

from __future__ import annotations

import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any

from semaudit.contract.schema import SEVERITY, Contract, Rule
from semaudit.relate.rules import Entry
from semaudit.story.model import Event, Story

FACTUAL_CHECKS = {"match_oracle", "match_charge"}


@dataclass
class Occurrence:
    persona: str
    story_id: str
    events: list[str]                  # cited event ids in that story (one, a pair, or a load window)
    entry: Entry
    timing: str                        # before_decision | after_decision
    also: list[Entry] = field(default_factory=list)   # other rules violated on the same event


@dataclass
class Issue:
    id: str
    signature: tuple
    rule: str
    rule_kind: str
    layer: str                         # release | factual
    label: str | None
    occurrences: list[Occurrence]
    severity: dict[str, Any]
    why: str
    delta: str = "new"                 # new | pre_existing | resolved | not_measured_in_head; with an owner
                                       # fix decision also still_open | regressed (decide.memory)
    delta_basis: str = ""
    confidence: dict[str, Any] = field(default_factory=dict)
    verification: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)   # the owner's past decision on this signature, if any

    @property
    def personas(self) -> list[str]:
        return sorted({o.persona for o in self.occurrences})

    @property
    def features(self) -> list[str]:
        return self._features

    _features: list[str] = field(default_factory=list)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def commitment_actions(contract: Contract) -> set[str]:
    return {a for d in contract.decisions for a in d.decided_by}


def timing_of(events: list[Event], story: Story, contract: Contract) -> str:
    """before_decision if the cited moment comes before the user's first commitment (a decided_by action)."""
    commits = [e.at for e in story.events if e.kind == "user_action" and e.action in commitment_actions(contract)]
    first = min(commits) if commits else None
    last = max(e.at for e in events)
    return "before_decision" if first is None or last < first else "after_decision"


def cited_events(entry: Entry, story: Story) -> list[Event]:
    by = {e.id: e for e in story.events}
    if entry.rule and "pairs" in entry.meta:
        ids = sorted({i for p in entry.meta["pairs"] for i in p}, key=lambda i: by[i].at)
    elif "events" in entry.meta:
        ids = entry.meta["events"]
    else:
        ids = [entry.subject]
    return [by[i] for i in ids if i in by]


def signature(entry: Entry, events: list[Event]) -> tuple:
    failing = tuple(sorted(c for c, v in entry.conditions if v != "met"))
    if "pairs" in entry.meta or entry.subject == "story":
        return (entry.rule, entry.subject, entry.label or "", failing)
    e = events[0]
    return (entry.rule, e.feature or "", e.copy_key or e.text or "", failing)


def issue_id(release: str, sig: tuple) -> str:
    rule, what, label, failing = sig
    tail = "-".join(x for x in (_slug(what.split("@")[0].replace("|", "-")), _slug(label), "-".join(failing)) if x)
    return f"I-{release}-{rule}-{tail}" if tail else f"I-{release}-{rule}"


def severity_of(rule: Rule, occurrences: list[Occurrence]) -> dict[str, Any]:
    """The rule's owner-set level (per label, for a coherence rule that sets one). Tested-persona counts are
    context for the reader, never a multiplier. An issue's occurrences share one signature, hence one label."""
    before = sorted({o.persona for o in occurrences if o.timing == "before_decision"})
    after = sorted({o.persona for o in occurrences if o.timing == "after_decision"} - set(before))
    label = occurrences[0].entry.label if occurrences else None
    level = rule.severity_for(label)
    return {"level": level,
            "factors": {"rule": rule.id, "base": rule.severity, "label": label,
                        "set_by": "severity_by_label" if label in rule.severity_by_label else "severity",
                        "tested_personas": len({o.persona for o in occurrences}),
                        "tested_personas_before_decision": len(before),
                        "tested_personas_after_decision": len(after)}}


def _hm(e: Event) -> str:
    return e.at.strftime("%H:%M")


def explain(entry: Entry, events: list[Event], story: Story, contract: Contract) -> str:
    """One sentence assembled from the relation's fields; never free model prose."""
    r = contract.rule(entry.rule)
    who = contract.subject.noun
    if r.kind == "coherence" and len(events) >= 2:
        acts = {}
        for e in events:
            acts.setdefault(e.feature, e)
        (fa, a), (fb, b) = list(acts.items())[:2]
        dec = contract.decision(entry.meta.get("decision", ""))
        decided = story.first_action_after(b.at, dec.decided_by if dec else [])
        when = f"before the {who} decided at {decided:%H:%M}" if decided else f"while the {who} was deciding"
        if entry.meta.get("pair_kind") == "incompatible":
            return (f"{a.extraction.action} ({fa}, {_hm(a)}) and {b.extraction.action} ({fb}, {_hm(b)}) are "
                    f"incompatible on {entry.meta.get('decision')} ({entry.meta.get('material')}); "
                    f"nothing reconciled them {when}.")
        return (f"{a.extraction.action} ({fa}, live from {_hm(a)}) and {b.extraction.action} ({fb}, {_hm(b)}) "
                f"are compatible with a material tradeoff ({entry.meta.get('material')}); "
                f"nothing explained it {when}.")
    e = events[0] if events else None
    if r.check.get("must") == "precondition_holds_at_shown_time" and e:
        dec = contract.decision(e.extraction.decision)
        pre = dec.precondition(e.extraction.action) if dec else {}
        state = story.state_at(e.at, contract.state, inclusive=True)
        need = ", ".join(f"{k} = {v}" for k, v in pre.items())
        was = ", ".join(f"{k} = {state.get(k)}" for k in pre)
        return f"'{e.extraction.action}' needs {need}; when shown at {_hm(e)}, {was}."
    if "message_kind" in r.applies_to and e:
        return f"a {r.applies_to['message_kind']} message at {_hm(e)}, after the {who} had committed."
    if r.kind == "conditional" and e:
        return conditional_why(r, entry, e, story)
    if r.kind == "load":
        return f"{entry.meta.get('count')} outbound contacts within {r.count.get('window_hours')} h (max {r.count.get('max')})."
    return entry.note or ""


def nearest_exception(r: Rule, entry: Entry):
    """The exception the rule engine measured this entry against (most conditions met), or None."""
    want = entry.meta.get("exception")
    return next((x for x in r.exceptions if x.id == want), r.exceptions[0] if r.exceptions and not want else None)


def condition_details(r: Rule, entry: Entry, e: Event, story: Story) -> list[dict[str, str]]:
    """Every exception condition with its measured value in words, met or not ('<deadline> 29 h 57 m … ≤ 72 h')."""
    ex = nearest_exception(r, entry)
    if ex is None:
        return []
    conds = {c.id: c for c in ex.conditions}
    out = []
    for cid, v in entry.conditions:
        c, ok = conds.get(cid), v == "met"
        if cid == "scope":
            covered = " / ".join(f"{k}: {', '.join(x)}" for k, x in ex.scope.items())
            text = f"{e.feature} on a {e.component} {e.surface.replace('_', ' ')}; the exception covers {covered}"
        elif cid == "expiry":
            text = f"approved until {ex.approved.get('expires')}"
        elif c is not None and c.test == "time_until":
            name = c.context_field.replace("_at", "").replace("_", " ")
            dep = story.context.get(c.context_field)
            if dep is None:
                text = f"{name} unknown"
            else:
                dep = datetime.fromisoformat(dep) if isinstance(dep, str) else dep
                secs = int((dep - e.at).total_seconds())
                h, rem = divmod(abs(secs), 3600)
                span = f"{h} h {rem // 60:02d} m {rem % 60:02d} s"
                text = (f"{name} {span} after the message ({'≤' if ok else '>'} {c.hours:g} h)" if secs >= 0
                        else f"the {name} has already passed")
        elif c is not None and c.test == "claim_matches_oracle":
            claimed = [x["value"] for x in e.extraction.claims if x["type"] == c.claim]
            truth = story.truth_at(c.claim, e.at, e.feature)
            text = f"claims {claimed[0] if claimed else '?'} {c.claim.replace('_', ' ')}; true value {truth}"
        elif c is not None and c.kind == "judged":
            verb = c.field.replace("_", " ").replace("explains", "explains" if ok else "does not explain")
            text = f"the message {verb}" if ok else f"the message {verb.replace('does not explain', 'does not explain')}"
        else:
            text = v
        out.append({"id": cid, "value": v, "text": text})
    return out


def conditional_why(r: Rule, entry: Entry, e: Event, story: Story) -> str:
    """'nearest exception P1-E1 does not apply: scope (…)', with each failing condition's measured value."""
    ex = nearest_exception(r, entry)
    if ex is None:
        return f"{e.extraction.strength} on {r.applies_to.get('decision')}, which {r.id} forbids."
    bad = [f"({d['id']}) {d['text']}" if d["id"] not in ("scope", "expiry") else f"{d['id']} ({d['text']})"
           for d in condition_details(r, entry, e, story) if d["value"] != "met"]
    return (f"{e.extraction.strength} {e.extraction.action} on {r.applies_to.get('decision')}; nearest exception "
            f"{ex.id} does not apply: " + "; ".join(bad) + ".")


def build_issues(release: str, results: dict[str, tuple[Story, list[Entry]]], contract: Contract) -> list[Issue]:
    """results: persona -> (story, entries) for one release."""
    order = {r.id: i for i, r in enumerate(contract.rules)}
    groups: dict[tuple, list[Occurrence]] = {}
    for persona, (story, entries) in sorted(results.items()):
        violated = [e for e in entries if e.status == "violated"]
        by_subject: dict[str, list[Entry]] = {}
        for e in violated:
            by_subject.setdefault(e.subject, []).append(e)
        for subject, es in by_subject.items():
            es.sort(key=lambda e: order[e.rule])           # one event, one issue: the contract's first rule
            primary, also = es[0], es[1:]
            evs = cited_events(primary, story)
            sig = signature(primary, evs)
            groups.setdefault(sig, []).append(Occurrence(persona, story.id, [e.id for e in evs], primary,
                                                         timing_of(evs, story, contract), also))
    issues = []
    for sig, occ in groups.items():
        rule = contract.rule(sig[0])
        story, _ = results[occ[0].persona]
        evs = cited_events(occ[0].entry, story)
        it = Issue(id=issue_id(release, sig), signature=sig, rule=rule.id, rule_kind=rule.kind,
                   layer="factual" if rule.check.get("must") in FACTUAL_CHECKS else "release",
                   label=occ[0].entry.label, occurrences=occ, severity=severity_of(rule, occ),
                   why=explain(occ[0].entry, evs, story, contract))
        it._features = sorted({e.feature for o in occ for e in cited_events(o.entry, results[o.persona][0])
                               if e.feature})
        issues.append(it)
    return sorted(issues, key=lambda i: (-SEVERITY.index(i.severity["level"]), order[i.rule], i.id))


def apply_delta(head: list[Issue], base: list[Issue], measured_base: set[str],
                measured_head: set[str]) -> tuple[list[Issue], list[Issue]]:
    """Mark head issues new / pre_existing. Return (resolved, unconfirmed): base issues whose signature is gone
    from head, split by whether every persona they reached was actually measured in head. An issue can only be
    resolved where we looked; absence in an unmeasured story is not evidence of a fix."""
    base_sigs = {i.signature: i for i in base}
    head_sigs = {i.signature for i in head}
    for i in head:
        if i.signature in base_sigs:
            i.delta, i.delta_basis = "pre_existing", f"also in base as {base_sigs[i.signature].id}"
        else:
            unmeasured = [p for p in i.personas if p not in measured_base]
            i.delta = "new"
            i.delta_basis = ("base not measured for " + ", ".join(unmeasured)) if unmeasured else "absent in base"
    resolved, unconfirmed = [], []
    for b in base:
        if b.signature in head_sigs:
            continue
        missing = [p for p in b.personas if p not in measured_head]
        if missing:
            b.delta, b.delta_basis = "not_measured_in_head", "head not measured for " + ", ".join(missing)
            unconfirmed.append(b)
        else:
            b.delta, b.delta_basis = "resolved", "absent in head; every affected persona measured"
            resolved.append(b)
    return resolved, unconfirmed
