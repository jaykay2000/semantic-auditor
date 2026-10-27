"""User Experience Story: one persona's time-ordered experience of one release."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class Extraction(BaseModel):
    """What a model (or the gold file, in offline tests) says a message tells the user."""
    message_kind: Literal["information", "directive", "retrospective"]
    decision: str
    action: str
    strength: Literal["inform", "suggest", "urge", "require"]
    urgency_cue: str
    explains_own_tradeoff: bool
    claims: list[dict[str, Any]] = Field(default_factory=list)
    normalized: str | None = None        # set when code overruled a field the contract determines


class Evidence(BaseModel):
    """Where a message event was observed: enough to re-find the exact text in the stored capture."""
    episode: str                         # release/persona/scenario
    step: int                            # 1-based step of the scenario
    capture_id: str
    element: int                         # index into the capture's elements
    locator: dict[str, Any]              # source-specific: css + span, message_id + part + span, turn + span ...
    capture_sha256: dict[str, str] = Field(default_factory=dict)   # role -> digest of the stored artifact
    attribution: dict[str, Any] = Field(default_factory=dict)      # how the feature was attributed


class Event(BaseModel):
    id: str
    at: datetime
    kind: Literal["message", "user_action"]
    feature: str | None = None
    surface: str | None = None
    channel: str | None = None          # card | banner | page | email | push | chat
    component: str | None = None        # a part of the product the contract names (exception scopes read it)
    topic: str | None = None            # e.g. the main transaction (excluded from load counts)
    user_initiated: bool = False
    copy_key: str | None = None
    text: str | None = None
    action: str | None = None           # user actions: the scenario verbs
    effects: dict[str, Any] = Field(default_factory=dict)   # state changes caused by a user action
    extraction: Extraction | None = None
    evidence: Evidence | None = None    # None only for hand-authored stories; captured stories always carry it


class Story(BaseModel):
    id: str
    release: str
    persona: str
    context: dict[str, Any] = Field(default_factory=dict)   # the persona's situation (subject.context), times exact
    truth: dict[str, Any] = Field(default_factory=dict)   # fact id -> true value (hand-authored stories)
    snapshots: list[dict[str, Any]] = Field(default_factory=list)  # [{at, truth: {fact: value}}] from captures
    events: list[Event]

    def truth_at(self, fact: str, t: datetime, feature: str | None = None) -> Any:
        """The fact's true value in force at t: the latest snapshot taken at or before t, else the static truth.

        A fact scoped to the claiming feature (e.g. a fee: only that feature's own charges) is stored as
        'fact@feature'; it is preferred when present.
        """
        for name in ([f"{fact}@{feature}"] if feature else []) + [fact]:
            snaps = [x for x in self.snapshots if _dt(x["at"]) <= t and name in x["truth"]]
            if snaps:
                return max(snaps, key=lambda x: _dt(x["at"]))["truth"][name]
        return self.truth.get(fact)

    def final_truth(self, fact: str, feature: str | None = None) -> Any:
        """The fact's value at the end of the story (e.g. what was ultimately charged)."""
        for name in ([f"{fact}@{feature}"] if feature else []) + [fact]:
            snaps = [x for x in self.snapshots if name in x["truth"]]
            if snaps:
                return max(snaps, key=lambda x: _dt(x["at"]))["truth"][name]
        return self.truth.get(fact)

    def messages(self) -> list[Event]:
        return [e for e in self.events if e.kind == "message"]

    def state_at(self, t: datetime, model: list, *, inclusive: bool = False) -> dict[str, Any]:
        """State derived from the contract's state model and user actions strictly before t.

        inclusive=True also counts actions AT t: use it for a message, which is shown as the result of the step
        it appears in (a confirmation shown at 10:06:00 follows the 10:06:00 action). Exact timestamps,
        no rounding. An action's explicit `effects` are applied after the model.
        """
        acts = sorted((e for e in self.events if e.kind == "user_action" and (e.at <= t if inclusive else e.at < t)),
                      key=lambda e: e.at)
        state: dict[str, Any] = {}
        for var in model:
            if var.kind == "plain":
                value = var.initial
                for a in acts:
                    if a.action in var.set_by:
                        value = var.set_by[a.action]
                state[var.id] = value
            else:
                opened = next((a.at for a in acts if a.action == var.opens_on), None)
                hours = self.context.get(var.hours_from_context) if var.hours_from_context else None
                hours = var.hours if hours is None else hours
                state[var.id] = opened is not None and hours is not None and t <= opened + timedelta(hours=hours)
        for a in acts:
            state.update(a.effects)
        return state

    def first_action_after(self, t: datetime, actions: list[str]) -> datetime | None:
        """When the user first took one of these actions after t (e.g. the actions that settle a decision)."""
        acts = set(actions)
        times = [e.at for e in self.events if e.kind == "user_action" and e.action in acts and e.at > t]
        return min(times) if times else None


def _dt(v) -> datetime:
    return datetime.fromisoformat(v) if isinstance(v, str) else v


def load_story(path: Path) -> Story:
    return Story(**json.loads(path.read_text()))
