"""Product Contract: the owner-approved description of an app that every audit layer reads.

Rules (with conditions and scoped exceptions), the decision vocabulary, features, surfaces,
facts and their oracles, the derived-state model, personas, scenarios, the release policy and
the app's hooks. Everything app-specific lives in the consumer's YAML; nothing here names an app.

Times inside a contract are written relative to a scenario's day 0 ("D0 10:00", "D3 10:03:30").
`resolve_time` turns them into exact datetimes; nothing is rounded.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(Strict):
    """Where an item came from: a doc span, a transcript timestamp, or a review click."""
    kind: Literal["doc", "transcript", "review", "default"]
    file: str | None = None
    at: str | None = None
    by: str | None = None
    date: str | None = None


# ---------- rules ----------

class Condition(Strict):
    id: str
    kind: Literal["data", "judged"]
    test: str | None = None          # data conditions: name of a code test
    field: str | None = None         # judged conditions: extracted field the model filled
    hours: float | None = None
    trip_field: str | None = None
    claim: str | None = None
    oracle: str | None = None


class ExceptionRule(Strict):
    id: str
    conditions: list[Condition]
    scope: dict[str, list[str]] = Field(default_factory=dict)
    approved: dict[str, str] = Field(default_factory=dict)
    source: Source | None = None


class Rule(Strict):
    id: str
    kind: Literal["universal", "conditional", "coherence", "load"]
    text: str
    applies_to: dict[str, Any] = Field(default_factory=dict)
    check: dict[str, Any] = Field(default_factory=dict)
    count: dict[str, Any] = Field(default_factory=dict)
    exceptions: list[ExceptionRule] = Field(default_factory=list)
    severity: Literal["minor", "major", "critical"] = "major"   # owner-set base level of a violation
    source: Source | None = None


# ---------- decisions ----------

class Pair(Strict):
    pair: tuple[str, str]
    rationale: str | None = None
    material: str | None = None


class Decision(Strict):
    id: str
    actions: list[str]
    incompatible: list[Pair] = Field(default_factory=list)
    tradeoffs: list[Pair] = Field(default_factory=list)
    never_pairs: list[str] = Field(default_factory=list)
    decided_by: list[str] = Field(default_factory=list)   # user actions that settle the decision
    preconditions: dict[str, dict[str, Any]] = Field(default_factory=dict)
    source: Source | None = None

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


# ---------- features, surfaces, facts ----------

class Feature(Strict):
    id: str
    name: str | None = None
    release_introduced: str | None = None
    changed_in: list[str] = Field(default_factory=list)
    attribution: dict[str, Any] = Field(default_factory=dict)    # dom_attr / headers the app stamps
    topic: str | None = None             # e.g. booking: excluded from load counts
    default_lifetime_hours: dict[str, float] = Field(default_factory=dict)
    source: Source | None = None


class Surface(Strict):
    """A place the product tells the user something, and how evidence on it is located."""
    id: str
    kind: Literal["web", "email", "push", "pdf", "chat", "api"]
    locator: Literal["css", "message_id", "notification_id", "pdf_page", "json_path", "chat_turn"]
    component: str | None = None
    reached_by: str | None = None        # scenario verb that brings the user here
    message_selector: str | None = None  # web: elements that carry messages
    sink: str | None = None              # email/push: where the app writes messages
    user_turn: dict[str, str] = Field(default_factory=dict)   # chat: attrs marking the user's own turn


class Oracle(Strict):
    """Ground truth the app exposes; read after every scenario step to snapshot state."""
    id: str
    kind: Literal["http_json"] = "http_json"
    endpoint: str                        # path template, e.g. /api/oracle/inventory?fare={fare}
    fields: dict[str, str] = Field(default_factory=dict)   # name -> JSON path in the response


class FactSource(Strict):
    """Where a fact's true value is read: an oracle field, optionally one item of a list field."""
    oracle: str
    field: str
    where: dict[str, Any] = Field(default_factory=dict)   # list field: pick the item whose keys match
    take: str | None = None                              # list field: the value to take from that item
    match_feature: str | None = None                     # list field: item key that must equal the claiming feature
    scale: float = 1.0                                   # e.g. 0.01 for cents -> EUR


class Fact(Strict):
    """A kind of claim a message can make, and where its true value comes from (first source that reads)."""
    id: str
    unit: str | None = None
    sources: list[FactSource] = Field(default_factory=list)   # empty: claims of this fact are unverifiable


# ---------- derived state ----------

class StateVar(Strict):
    """A state variable derived from user actions strictly before a moment (never stored on a persona).

    plain:  value = initial, replaced by set_by[action] when that action happens.
    window: True while t <= (first time `opens_on` happened) + hours (or the trip's `hours_from_trip`).
    """
    id: str
    kind: Literal["plain", "window"] = "plain"
    initial: Any = None
    set_by: dict[str, Any] = Field(default_factory=dict)
    opens_on: str | None = None
    hours: float | None = None
    hours_from_trip: str | None = None

    @model_validator(mode="after")
    def _shape(self):
        if self.kind == "window" and not self.opens_on:
            raise ValueError(f"window state {self.id} needs opens_on")
        return self


# ---------- personas and scenarios ----------

_REL = re.compile(r"^D(-?\d+)\s+(\d{1,2}):(\d{2})(?::(\d{2}))?$")


def resolve_time(spec: str, day0: datetime) -> datetime:
    """'D3 10:03:30' -> day0's date + 3 days at 10:03:30 (same tz). Exact; never rounded."""
    m = _REL.match(spec.strip())
    if not m:
        raise ValueError(f"bad relative time {spec!r}; expected 'D<n> HH:MM[:SS]'")
    d, hh, mm, ss = int(m[1]), int(m[2]), int(m[3]), int(m[4] or 0)
    base = day0.replace(hour=0, minute=0, second=0, microsecond=0)
    return base + timedelta(days=d, hours=hh, minutes=mm, seconds=ss)


class Trip(Strict):
    component: Literal["flight", "hotel"] = "flight"
    route: str | None = None             # flights: ORIGIN-DEST
    hotel: str | None = None             # hotels: hotel id
    departure_at: str                    # relative time; for hotels, check-in
    flexible: bool = True


class Persona(Strict):
    id: str
    name: str
    party: int = 1
    axes: dict[str, Any] = Field(default_factory=dict)
    trip: Trip
    experiments: dict[str, Any] = Field(default_factory=dict)   # experiment arms the app assigns
    world: dict[str, Any] = Field(default_factory=dict)         # oracle state seeded before the scenario
    role: str | None = None              # hero | negative | boundary | factual (documentation only)


class Step(Strict):
    at: str                              # relative time
    do: str                              # scenario verb, mapped to the app by its adapter
    params: dict[str, Any] = Field(default_factory=dict)
    when_offered: bool = False           # skip (and record the skip) if the release does not offer it


class Scenario(Strict):
    id: str
    description: str | None = None
    day0: datetime
    personas: list[str]
    steps: list[Step]

    def times(self) -> list[datetime]:
        return [resolve_time(s.at, self.day0) for s in self.steps]


# ---------- release policy ----------

SEVERITY = ["minor", "major", "critical"]
CONFIDENCE = ["low", "medium", "high"]
VERIFICATION = ["unverified", "partially_verified", "verified"]


class Match(Strict):
    """Matches one open issue. Every listed constraint must hold; an empty Match matches any issue."""
    severity: list[Literal["minor", "major", "critical"]] | None = None
    confidence_at_least: Literal["low", "medium", "high"] | None = None
    verification: list[Literal["unverified", "partially_verified", "verified"]] | None = None
    verification_not: list[Literal["unverified", "partially_verified", "verified"]] | None = None

    def matches(self, issue: dict[str, str]) -> bool:
        if self.severity is not None and issue["severity"] not in self.severity:
            return False
        if self.confidence_at_least is not None and \
                CONFIDENCE.index(issue["confidence"]) < CONFIDENCE.index(self.confidence_at_least):
            return False
        if self.verification is not None and issue["verification"] not in self.verification:
            return False
        if self.verification_not is not None and issue["verification"] in self.verification_not:
            return False
        return True


class PolicyRow(Strict):
    recommendation: Literal["hold", "needs_owner_review", "ship_with_notes", "ship"]
    text: str                            # shown verbatim on the decision bar
    any_issue: list[Match] = Field(default_factory=list)   # row fires if ANY open issue matches ANY Match
    no_open_issues: bool = False
    otherwise: bool = False              # fires unconditionally (catch-all)


class Escalation(Strict):
    """Raise an issue's severity when it reaches enough people at a moment that matters."""
    text: str
    reach_at_least: int | None = None                        # distinct personas affected
    timing: Literal["before_decision", "after_decision"] | None = None
    rule_kinds: list[str] = Field(default_factory=list)      # empty: any kind
    raise_by: int = 1

    def applies(self, reach: int, timing: str, rule_kind: str) -> bool:
        return ((self.reach_at_least is None or reach >= self.reach_at_least)
                and (self.timing is None or timing == self.timing)
                and (not self.rule_kinds or rule_kind in self.rule_kinds))


class ReleasePolicy(Strict):
    rows: list[PolicyRow]
    escalation: list[Escalation] = Field(default_factory=list)
    source: Source | None = None

    def evaluate(self, open_issues: list[dict[str, str]]) -> tuple[PolicyRow, int]:
        """Top-down; the first row that fires wins. Issues whose verification failed are not open."""
        for i, row in enumerate(self.rows):
            if row.otherwise:
                return row, i
            if row.no_open_issues and not open_issues:
                return row, i
            if row.any_issue and any(m.matches(x) for x in open_issues for m in row.any_issue):
                return row, i
        raise ValueError("release policy is not exhaustive: no row fired")


# ---------- the app ----------

class Hooks(Strict):
    reset: str | None = None
    persona: str                         # creates the persona's account and trip
    clock: str | None = None             # without it, time-triggered surfaces are 'not measured'
    world: str | None = None             # seeds oracle state


class Launch(Strict):
    """How the capture runner starts the app under audit, once per release, on a free port.

    `cwd` is relative to the contract directory. `cmd` and every `env` value may use `{python}` (the runner's
    interpreter), `{port}`, `{release}` and `{scratch}` (a fresh temp dir per launched app). The release is also
    passed in `App.release_env`. Email and push sink paths (`Surface.sink`) are resolved relative to `sink_root`
    (default: the resolved `cwd`; may use `{scratch}`), so an app can write its outbox anywhere.
    """
    cwd: str = "."
    cmd: list[str]
    env: dict[str, str] = Field(default_factory=dict)
    sink_root: str | None = None
    health: str = "/"                    # GET until it answers (any status below 500)
    startup_timeout: float = 30.0


class App(Strict):
    name: str
    fictional: bool
    data: Literal["synthetic", "real"]
    base_url: str
    release_env: str | None = None       # env var that selects the release, if the app is launched by us
    releases: list[str] = Field(default_factory=list)
    hooks: Hooks
    launch: Launch | None = None         # how the capture runner starts the app; absent = already running
    adapter: str | None = None           # scenario-verb adapter: a .py path relative to the contract, or a dotted
                                         # module path; it must define a class `Adapter` (see semaudit.adapters)


# ---------- the contract ----------

class Contract(Strict):
    rules: list[Rule]
    decisions: list[Decision]
    features: list[Feature]
    rubric: str
    surfaces: list[Surface] = Field(default_factory=list)
    oracles: list[Oracle] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    state: list[StateVar] = Field(default_factory=list)
    personas: list[Persona] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)
    policy: ReleasePolicy | None = None
    app: App | None = None

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

    def persona(self, persona_id: str) -> Persona:
        return next(p for p in self.personas if p.id == persona_id)

    def scenario_for(self, persona_id: str) -> list[Scenario]:
        return [s for s in self.scenarios if persona_id in s.personas]


FILES = {   # section -> file; only the first four are required
    "rules": "principles.yaml", "decisions": "decisions.yaml", "features": "features.yaml",
    "surfaces": "surfaces.yaml", "oracles": "oracles.yaml", "facts": "facts.yaml", "state": "state.yaml",
    "personas": "personas.yaml", "scenarios": "scenarios.yaml",
}


def load_contract(directory: Path) -> Contract:
    def read(name: str):
        p = directory / name
        return yaml.safe_load(p.read_text()) if p.exists() else None

    data: dict[str, Any] = {k: read(f) or [] for k, f in FILES.items()}
    data["rubric"] = (directory / "rubric.md").read_text()
    policy = read("release_policy.yaml")
    data["policy"] = ReleasePolicy(**policy) if policy else None
    app = read("app.yaml")
    data["app"] = App(**app) if app else None
    return Contract(**data)
