"""The normalized finding and ground-truth formats every benchmark condition is scored in.

One format for every system (the auditor, B-judge-1, B-judge-N, B-explore, ablations), so the matcher never
special-cases a system and no finding is matched by hand (docs/08-evaluation.md, "Matching rule").

A finding's TARGET is what it is about, at the granularity the matching rule names:
  relation: an unordered feature pair plus the decision both speak to (coherence rules)
  event:    one message, by feature, surface and message key (copy key)
  story:    the persona's experience as a whole (load rules)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

Label = Literal["conflict", "unexplained_tradeoff", "explained_tradeoff"]


class Target(BaseModel):
    kind: Literal["relation", "event", "story"]
    features: list[str] = Field(default_factory=list)   # relation: exactly two, sorted
    decision: str | None = None                          # relation
    feature: str | None = None                           # event
    surface: str | None = None                           # event
    message_key: str | None = None                       # event

    @model_validator(mode="after")
    def _shape(self):
        if self.kind == "relation":
            if len(set(self.features)) != 2 or not self.decision:
                raise ValueError("a relation target names two different features and a decision")
            self.features = sorted(self.features)
        if self.kind == "event" and not (self.feature and self.surface and self.message_key):
            raise ValueError("an event target names a feature, a surface and a message key")
        return self

    def key(self) -> tuple:
        if self.kind == "relation":
            return ("relation", *self.features, self.decision)
        if self.kind == "event":
            return ("event", self.feature, self.surface, self.message_key)
        return ("story",)


class Cited(BaseModel):
    persona: str
    event_id: str
    quote: str = ""          # verbatim text the finding relies on; checked against the capture


class Finding(BaseModel):
    id: str
    personas: list[str]
    rule: str
    label: Label | None = None
    target: Target
    severity: Literal["minor", "major", "critical"] | None = None
    confidence: Literal["low", "medium", "high"] | None = None
    why: str = ""
    cited: list[Cited] = Field(default_factory=list)
    secondary: bool = False  # the auditor's "also violated" on an event another rule already owns


class Findings(BaseModel):
    system: str              # the condition name; removed before adjudication
    release: str
    run: str = "1"
    findings: list[Finding]
    cost_usd: float | None = None
    calls: int | None = None


class TruthItem(BaseModel):
    id: str
    kind: Literal["issue", "negative_control"]
    personas: list[str]
    rule: str
    label: Label | None = None
    target: Target
    also_targets: list[Target] = Field(default_factory=list)  # an item made of several events: a finding about
                                                              # any one of them is about this item
    pattern: str | None = None          # issue kind, or the negative-control pattern
    objective: bool = False             # oracle-backed: no adjudication needed
    severity: Literal["minor", "major", "critical"] | None = None
    delta: Literal["new", "changed", "existing"] | None = None   # attribution, relative to the base release
    features: list[str] = Field(default_factory=list)              # attribution: the responsible features

    def target_keys(self) -> frozenset:
        return frozenset([self.target.key(), *(t.key() for t in self.also_targets)])


class Truth(BaseModel):
    release: str
    items: list[TruthItem]
    source: str = ""                    # where the truth came from (dev fixture vectors, sealed file, ...)
    personas: list[str] | None = None   # personas this truth covers; findings about others are not scored


# ---------- the auditor's review.json -> findings ----------

def _event_index(review: dict) -> dict[tuple[str, str], dict]:
    return {(p["id"], e["id"]): e for p in review.get("personas", []) for e in p.get("events", [])}


def _target(rule_kind: str, sig: list, events: list[dict]) -> Target:
    if rule_kind == "coherence":
        pair, decision = sig[1].split("@", 1)
        return Target(kind="relation", features=pair.split("|"), decision=decision.split(":", 1)[0])
    if sig[1] == "story":
        return Target(kind="story")
    e = events[0]
    return Target(kind="event", feature=e.get("feature"), surface=e.get("surface"),
                  message_key=e.get("message_key") or e.get("copy_key"))


def from_review(review: dict, *, system: str = "semaudit-full", run: str = "1") -> Findings:
    """Every issue the review raises, plus each "also violated" entry as its own (secondary) finding, so a rule
    the auditor reports only under another rule's issue is still scored as reported."""
    idx = _event_index(review)
    out: list[Finding] = []
    for i in review["issues"]:
        cited = [Cited(persona=o["persona"], event_id=eid, quote=(idx.get((o["persona"], eid)) or {}).get("text") or "")
                 for o in i["occurrences"] for eid in o["events"]]
        first = i["occurrences"][0]
        target = _target(i["rule_kind"], i["signature"], [idx[(first["persona"], eid)] for eid in first["events"]])
        out.append(Finding(id=i["id"], personas=sorted({o["persona"] for o in i["occurrences"]}), rule=i["rule"],
                           label=i.get("label"), target=target, severity=i["severity"]["level"],
                           confidence=i["confidence"]["level"], why=i.get("why", ""), cited=cited))
        also: dict[str, list[dict]] = {}
        for o in i["occurrences"]:
            for a in o.get("also", []):
                also.setdefault(a["rule"], []).append(o)
        for rule, occ in also.items():
            out.append(Finding(id=f"{i['id']}+{rule}", personas=sorted({o["persona"] for o in occ}), rule=rule,
                               target=target, why=f"also violated on the event {i['id']} cites",
                               cited=[c for c in cited if c.persona in {o["persona"] for o in occ}], secondary=True))
    return Findings(system=system, release=review["release"]["head"] if isinstance(review["release"], dict)
                    else str(review["release"]), run=run, findings=out, cost_usd=review.get("cost_usd"))


def load(path: Path, model: type[BaseModel]) -> Any:
    return model.model_validate(json.loads(Path(path).read_text()))
