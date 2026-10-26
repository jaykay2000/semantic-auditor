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


class Event(BaseModel):
    id: str
    at: datetime
    kind: Literal["message", "user_action"]
    feature: str | None = None
    surface: str | None = None
    channel: str | None = None          # card | banner | page | email | push | chat
    component: str | None = None        # flight | hotel
    topic: str | None = None            # e.g. booking (excluded from load counts)
    user_initiated: bool = False
    copy_key: str | None = None
    text: str | None = None
    action: str | None = None           # user actions: search, book, buy_lock, ask, opt_in ...
    effects: dict[str, Any] = Field(default_factory=dict)   # state changes caused by a user action
    extraction: Extraction | None = None


class Story(BaseModel):
    id: str
    release: str
    persona: str
    trip: dict[str, Any]                 # departure_at (exact), component, party ...
    oracles: dict[str, Any]              # inventory, charges ...
    events: list[Event]

    def messages(self) -> list[Event]:
        return [e for e in self.events if e.kind == "message"]

    def state_at(self, t: datetime) -> dict[str, Any]:
        """State derived from user actions strictly before t (exact timestamps, no rounding)."""
        state: dict[str, Any] = {"booking_status": "not_booked", "within_change_window": False}
        for e in sorted(self.events, key=lambda e: e.at):
            if e.kind == "user_action" and e.at < t:
                state.update(e.effects)
                if e.effects.get("booking_status") == "booked":
                    state["booked_at"] = e.at
        if "booked_at" in state:
            window = timedelta(hours=self.trip.get("change_window_hours", 24))
            state["within_change_window"] = t <= state["booked_at"] + window
        return state

    def first_action_after(self, t: datetime, actions: list[str]) -> datetime | None:
        """When the user first took one of these actions after t (e.g. the actions that settle a decision)."""
        acts = set(actions)
        times = [e.at for e in self.events if e.kind == "user_action" and e.action in acts and e.at > t]
        return min(times) if times else None


def load_story(path: Path) -> Story:
    return Story(**json.loads(path.read_text()))
