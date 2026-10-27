"""Code side of the relation layer: validity, candidate generation and rule evaluation.

Produces a status vector: one entry per (rule, subject) with a status, plus exception
conditions where they apply. Model judgement enters only through each message's
Extraction and through the P2 interpreter (see interpret.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import combinations
from typing import Any, Callable

from semaudit.contract.schema import Contract, Rule
from semaudit.story.model import Event, Story


@dataclass(frozen=True)
class Entry:
    rule: str
    subject: str
    status: str                      # violated | passed | excepted
    label: str | None = None         # P2 only
    conditions: tuple = ()           # (("a","met"), ...) for exception evaluations
    note: str = field(default="", compare=False)
    meta: dict = field(default_factory=dict, compare=False, hash=False)   # e.g. liveness bases, for confidence

    def key(self) -> tuple:
        return (self.rule, self.subject, self.status, self.label, self.conditions)


@dataclass
class Live:
    event: Event
    start: datetime
    end: datetime | None             # None = unknown, never "forever"
    basis: str


def is_directive(e: Event) -> bool:
    x = e.extraction
    return bool(x and x.message_kind == "directive" and x.action not in ("none", "other"))


def holds(pre: dict[str, Any], state: dict[str, Any]) -> bool:
    return all(state.get(k) == v for k, v in pre.items())


def validity(e: Event, story: Story, contract: Contract) -> Live:
    """Live from shown time until the earliest of: the action's precondition fails, the feature's default
    lifetime for that channel, or a later directive from the same feature on the same decision supersedes it.
    A deadline stated in the text is NOT read yet (needs an extraction field); with no end found the end is
    None with basis 'unknown', which confidence must treat as weaker evidence, never as 'forever'."""
    x = e.extraction
    dec = contract.decision(x.decision)
    pre = dec.precondition(x.action) if dec else {}
    ends: list[tuple[datetime, str]] = []
    later = [m for m in story.messages() if m.at > e.at and m.feature == e.feature and is_directive(m)
             and m.extraction.decision == x.decision]
    if later:
        ends.append((min(m.at for m in later), "superseded"))
    for a in sorted((a for a in story.events if a.kind == "user_action" and a.at > e.at), key=lambda a: a.at):
        if not holds(pre, story.state_at(a.at + timedelta(microseconds=1), contract.state)):
            ends.append((a.at, "action_rule"))
            break
    hours = contract.lifetime_hours(e.feature, e.channel)
    if hours is not None:
        ends.append((e.at + timedelta(hours=hours), "feature_default"))
    if not ends:
        return Live(e, e.at, None, "unknown")
    end, basis = min(ends)
    return Live(e, e.at, end, basis)


def live_at(live: Live, t: datetime) -> bool:
    return live.start <= t and (live.end is None or t < live.end)


# ---------- universal rules ----------

def eval_match_oracle(rule: Rule, story: Story) -> list[Entry]:
    """Claims of the given types must equal the named oracle; a missing oracle is unverifiable, not false."""
    out = []
    for e in story.messages():
        for c in e.extraction.claims:
            if c["type"] not in rule.check["claims"]:
                continue
            truth = story.truth_at(c["type"], e.at, e.feature)
            if truth is None:
                continue                      # unverifiable: an owner question, never a violation
            status = "passed" if c["value"] == truth else "violated"
            out.append(Entry(rule.id, e.id, status, note=f"claim {c['value']} vs true {c['type']} {truth}"))
    return out


def eval_match_charge(rule: Rule, story: Story) -> list[Entry]:
    out = []
    for e in story.messages():
        for c in e.extraction.claims:
            if c["type"] in rule.check["claims"]:
                charged = story.final_truth(rule.check["charge"], e.feature)   # ultimately charged, same feature
                if charged is None:       # no transaction in this story: not applicable
                    continue
                status = "passed" if c["value"] == charged else "violated"
                out.append(Entry(rule.id, e.id, status, note=f"shown {c['value']} vs charged {charged}"))
    return out


def eval_actionable(rule: Rule, story: Story, contract: Contract) -> list[Entry]:
    out = []
    for e in story.messages():
        if not is_directive(e):
            continue
        dec = contract.decision(e.extraction.decision)
        pre = dec.precondition(e.extraction.action) if dec else {}
        status = "passed" if holds(pre, story.state_at(e.at, contract.state, inclusive=True)) else "violated"
        out.append(Entry(rule.id, e.id, status))
    return out


def eval_message_kind(rule: Rule, story: Story, contract: Contract) -> list[Entry]:
    """Forbid a message kind in a given state (e.g. retrospective messages once booked)."""
    kind, state = rule.applies_to["message_kind"], rule.applies_to.get("state", {})
    return [Entry(rule.id, e.id, "violated") for e in story.messages()
            if e.extraction.message_kind == kind
            and holds(state, story.state_at(e.at, contract.state, inclusive=True))]


# ---------- conditional rules ----------

def condition_value(cond, e: Event, story: Story) -> str:
    if cond.kind == "judged":
        v = getattr(e.extraction, cond.field)
        return "met" if v else "not_met"
    if cond.test == "time_until":
        dep = story.trip.get(cond.trip_field)
        if dep is None:
            return "unknown"
        dep = datetime.fromisoformat(dep) if isinstance(dep, str) else dep
        gap = dep - e.at                                                            # exact timestamps
        return "met" if timedelta(0) <= gap <= timedelta(hours=cond.hours) else "not_met"   # past: not "soon"
    if cond.test == "claim_matches_oracle":
        claims = [c for c in e.extraction.claims if c["type"] == cond.claim]
        truth = story.truth_at(cond.claim, e.at, e.feature)
        if not claims or truth is None:
            return "unknown"
        return "met" if all(c["value"] == truth for c in claims) else "not_met"
    return "unknown"


def expiry_value(ex, e: Event) -> str:
    """An exception applies only to messages shown on or before its expiry date (inclusive, UTC)."""
    exp = ex.approved.get("expires")
    if not exp:
        return "unknown"
    end = datetime.fromisoformat(str(exp)).replace(tzinfo=e.at.tzinfo) + timedelta(days=1)
    return "met" if e.at < end else "not_met"


def in_scope(scope: dict, e: Event) -> bool:
    checks = {"features": e.feature, "components": e.component, "surfaces": e.surface}
    return all(checks[k] in v for k, v in scope.items() if k in checks)


def eval_conditional(rule: Rule, story: Story) -> list[Entry]:
    out = []
    want_decision = rule.applies_to.get("decision")
    strengths = rule.applies_to.get("strength", [])
    for e in story.messages():
        if not is_directive(e) or e.extraction.decision != want_decision or e.extraction.strength not in strengths:
            continue
        status, conds = "violated", ()
        for ex in rule.exceptions:
            values = tuple((c.id, condition_value(c, e, story)) for c in ex.conditions)
            values += (("scope", "met" if in_scope(ex.scope, e) else "not_met"),
                       ("expiry", expiry_value(ex, e)))
            conds = values
            if all(v == "met" for _, v in values):
                status = "excepted"
                break
        out.append(Entry(rule.id, e.id, status, conditions=conds))
    return out


# ---------- coherence (P2) ----------

@dataclass
class PairCandidate:
    subject: str                      # "featureA|featureB@decision" (sorted features)
    decision: str
    pair_kind: str                    # incompatible | tradeoff
    pairs: list[tuple[Event, Event]]  # every overlapping directive pair for this subject
    material: str
    lives: dict = field(default_factory=dict)   # event id -> Live


def p2_candidates(story: Story, contract: Contract) -> list[PairCandidate]:
    lives = [validity(e, story, contract) for e in story.messages() if is_directive(e)]
    found: dict[str, PairCandidate] = {}   # one candidate per feature pair, decision AND pair kind
    for a, b in combinations(lives, 2):
        xa, xb = a.event.extraction, b.event.extraction
        if a.event.feature == b.event.feature or xa.decision != xb.decision:
            continue
        dec = contract.decision(xa.decision)
        if not dec or xa.action in dec.never_pairs or xb.action in dec.never_pairs:
            continue
        kind = dec.pair_kind(xa.action, xb.action)
        if not kind:
            continue
        first, second = sorted((a, b), key=lambda l: l.start)
        if not live_at(first, second.start):
            continue
        feats = "|".join(sorted((a.event.feature, b.event.feature)))
        subject = f"{feats}@{xa.decision}:{kind}"
        pt = dec.pair_type(xa.action, xb.action)
        cand = found.setdefault(subject, PairCandidate(subject, xa.decision, kind, [],
                                                       pt.material or pt.rationale or ""))
        cand.pairs.append((first.event, second.event))
        cand.lives.update({first.event.id: first, second.event.id: second})
    return list(found.values())


Interpreter = Callable[[Story, PairCandidate, Contract], dict]


def eval_p2(rule: Rule, story: Story, contract: Contract, interpret: Interpreter) -> list[Entry]:
    out = []
    for cand in p2_candidates(story, contract):
        verdict = interpret(story, cand, contract)
        label = verdict["label"]
        rid = verdict.get("reconciling_event_id")
        if label == "explained_tradeoff" and not reconciler_is_timely(story, cand, rid, contract):
            label = "conflict" if cand.pair_kind == "incompatible" else "unexplained_tradeoff"
        status = "violated" if label in ("conflict", "unexplained_tradeoff") else "passed"
        bases = {i: lv.basis for i, lv in cand.lives.items()}
        out.append(Entry(rule.id, cand.subject, status, label=label, note=verdict.get("rationale", "")[:300],
                         meta={"liveness": bases, "unknown_validity": "unknown" in bases.values(),
                               "reconciler": rid or None, "pairs": [[x.id, y.id] for x, y in cand.pairs],
                               "decision": cand.decision, "pair_kind": cand.pair_kind,
                               "material": cand.material,
                               "live_until": {i: (lv.end.isoformat() if lv.end else None)
                                              for i, lv in cand.lives.items()}}))
    return out


def reconciler_is_timely(story: Story, cand: PairCandidate, rid: str | None, contract: Contract) -> bool:
    """A reconciling message counts only if, for some candidate pair, it is shown while BOTH directives are
    still live and no later than the decision that settles it."""
    if not rid:
        return False
    ev = next((e for e in story.events if e.id == rid), None)
    if ev is None:
        return False
    dec = contract.decision(cand.decision)
    for a, b in cand.pairs:
        la, lb = cand.lives[a.id], cand.lives[b.id]
        decided = story.first_action_after(b.at, dec.decided_by if dec else [])
        if live_at(la, ev.at) and live_at(lb, ev.at) and (decided is None or ev.at <= decided):
            return True
    return False


# ---------- load (P3) ----------

def eval_load(rule: Rule, story: Story) -> list[Entry]:
    c = rule.count
    contacts = sorted((e for e in story.messages()
                       if e.channel in c["channels"] and not e.user_initiated
                       and e.topic not in c.get("exclude_topics", [])), key=lambda e: e.at)
    window = timedelta(hours=c["window_hours"])
    for i, start in enumerate(contacts):
        inside = [e for e in contacts[i:] if e.at - start.at < window]
        if len(inside) > c["max"]:
            return [Entry(rule.id, "story", "violated", note=",".join(e.id for e in inside),
                          meta={"events": [e.id for e in inside], "count": len(inside), "max": c["max"]})]
    return [Entry(rule.id, "story", "passed")]


def evaluate(story: Story, contract: Contract, interpret: Interpreter) -> list[Entry]:
    entries: list[Entry] = []
    universal = {"match_oracle": eval_match_oracle, "match_charge": eval_match_charge}
    for r in contract.rules:
        must = r.check.get("must")
        if r.kind == "universal" and must in universal:
            entries += universal[must](r, story)
        elif r.kind == "universal" and must == "precondition_holds_at_shown_time":
            entries += eval_actionable(r, story, contract)
        elif r.kind == "universal" and "message_kind" in r.applies_to:
            entries += eval_message_kind(r, story, contract)
        elif r.kind == "conditional":
            entries += eval_conditional(r, story)
        elif r.kind == "coherence":
            entries += eval_p2(r, story, contract, interpret)
        elif r.kind == "load":
            entries += eval_load(r, story)
    return entries
