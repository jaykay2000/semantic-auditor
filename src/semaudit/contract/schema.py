"""Product Contract: the owner-approved rules, decision vocabulary and features.

Only the parts W1b needs are modelled here; surfaces, facts, scenarios and release
policy are added in W3b. Everything app-specific lives in the consumer's YAML.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class Condition(BaseModel):
    id: str
    kind: Literal["data", "judged"]
    test: str | None = None          # data conditions: name of a code test
    field: str | None = None         # judged conditions: extracted field the model filled
    hours: float | None = None
    trip_field: str | None = None
    claim: str | None = None
    oracle: str | None = None


class ExceptionRule(BaseModel):
    id: str
    conditions: list[Condition]
    scope: dict[str, list[str]] = Field(default_factory=dict)
    approved: dict[str, str] = Field(default_factory=dict)


class Rule(BaseModel):
    id: str
    kind: Literal["universal", "conditional", "coherence", "load"]
    text: str
    applies_to: dict[str, Any] = Field(default_factory=dict)
    check: dict[str, Any] = Field(default_factory=dict)
    count: dict[str, Any] = Field(default_factory=dict)
    exceptions: list[ExceptionRule] = Field(default_factory=list)


class Pair(BaseModel):
    pair: tuple[str, str]
    rationale: str | None = None
    material: str | None = None


class Decision(BaseModel):
    id: str
    actions: list[str]
    incompatible: list[Pair] = Field(default_factory=list)
    tradeoffs: list[Pair] = Field(default_factory=list)
    never_pairs: list[str] = Field(default_factory=list)
    decided_by: list[str] = Field(default_factory=list)   # user actions that settle the decision
    preconditions: dict[str, dict[str, Any]] = Field(default_factory=dict)

    def pair_type(self, a: str, b: str) -> Pair | None:
        for kind in ("incompatible", "tradeoffs"):
            for p in getattr(self, kind):
                if set(p.pair) == {a, b}:
                    return p
        return None

    def pair_kind(self, a: str, b: str) -> str | None:
        if any(set(p.pair) == {a, b} for p in self.incompatible):
            return "incompatible"
        if any(set(p.pair) == {a, b} for p in self.tradeoffs):
            return "tradeoff"
        return None

    def precondition(self, action: str) -> dict[str, Any]:
        return self.preconditions.get(action, self.preconditions.get("*", {}))


class Feature(BaseModel):
    id: str
    default_lifetime_hours: dict[str, float] = Field(default_factory=dict)


class Contract(BaseModel):
    rules: list[Rule]
    decisions: list[Decision]
    features: list[Feature]
    rubric: str

    def rule(self, rule_id: str) -> Rule:
        return next(r for r in self.rules if r.id == rule_id)

    def rules_of(self, kind: str) -> list[Rule]:
        return [r for r in self.rules if r.kind == kind]

    def decision(self, decision_id: str) -> Decision | None:
        return next((d for d in self.decisions if d.id == decision_id), None)

    def lifetime_hours(self, feature: str, channel: str) -> float | None:
        f = next((f for f in self.features if f.id == feature), None)
        return f.default_lifetime_hours.get(channel) if f else None

    def actions(self) -> list[str]:
        return sorted({a for d in self.decisions for a in d.actions})


def load_contract(directory: Path) -> Contract:
    read = lambda name: yaml.safe_load((directory / name).read_text())  # noqa: E731
    return Contract(
        rules=[Rule(**r) for r in read("principles.yaml")],
        decisions=[Decision(**d) for d in read("decisions.yaml")],
        features=[Feature(**f) for f in read("features.yaml")],
        rubric=(directory / "rubric.md").read_text(),
    )
