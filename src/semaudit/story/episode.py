"""Episodes: what one persona experienced running one scenario on one release (layer L1, capture).

An episode is the ordered record of a scenario run: for every step the simulated time, what the runner did,
everything the product showed or sent as a *capture*, and a *state snapshot* read from the contract's oracles.
Episodes are the input to extraction (W6) and to `semaudit repro`, so the format is stable:

* every time is simulated time, exact (`at`); the only wall-clock field is `Episode.started_wall`;
* capture ids derive from release, persona, scenario, step seq and capture index, so a rerun yields the same ids;
* artifact paths (`Capture.files`) are relative to the run directory and derived from the capture id;
* elements are located structurally (CSS selector, message id, notification id, chat turn, PDF page); no model
  has read anything yet.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Attribute and header names the apps stamp on marked text (docs/03-architecture.md, "Stable event identity").
KEY_ATTRS = ("data-message-key", "X-Message-Key")
FEATURE_ATTRS = ("data-feature", "X-Feature")
COMPONENT_ATTRS = ("data-component",)
SHOWN_AT_ATTRS = ("data-shown-at", "sent_at")

CaptureKind = Literal["web", "email", "push", "chat", "pdf"]
StepStatus = Literal["done", "skipped_not_offered", "failed"]
CaptureStatus = Literal["captured", "not_measured"]


class BBox(Strict):
    x: float
    y: float
    width: float
    height: float


class Element(Strict):
    """A piece of marked text found structurally on a capture. W6 extracts its meaning later.

    `locator` always has a `kind`:
      css          {css, span}                  web page: a selector unique in that DOM, span into the element text
      message_id   {message_id, part, span}     email: message id + part ("text") + character span
      notification_id {notification_id, field, span}   push
      chat_turn    {turn, span}                 chat: turn index + character span
      pdf_page     {page, span}                 PDF: page number (1-based) + span into that page's text layer
    """
    locator: dict[str, Any]
    text: str
    attrs: dict[str, str] = Field(default_factory=dict)       # every attribute (web) or header/field (email, push)
    bbox: BBox | None = None


class Capture(Strict):
    id: str
    kind: CaptureKind
    surface: str                                              # contract surface id
    at: datetime                                              # simulated time the content was shown or sent
    url: str | None = None
    phase: Literal["step", "final_drain"] = "step"
    status: CaptureStatus = "captured"                        # not_measured: the surface could not be read
    error: str | None = None
    files: dict[str, str] = Field(default_factory=dict)       # role -> path relative to the run dir
    sha256: dict[str, str] = Field(default_factory=dict)      # role -> digest of every stored artifact (dom, raw, screenshot)
    meta: dict[str, Any] = Field(default_factory=dict)
    elements: list[Element] = Field(default_factory=list)


class OracleReading(Strict):
    status: Literal["ok", "not_applicable", "not_measured"]
    endpoint: str | None = None
    values: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class StepRecord(Strict):
    seq: int                                                  # 1-based
    at: datetime                                              # simulated time of the step, exact
    do: str
    params: dict[str, Any] = Field(default_factory=dict)
    when_offered: bool = False
    status: StepStatus
    error: str | None = None
    clock: dict[str, Any] | None = None                       # what was sent to the clock hook and what it answered
    captures: list[Capture] = Field(default_factory=list)
    state: dict[str, OracleReading] = Field(default_factory=dict)


class NotMeasured(Strict):
    surface: str
    reason: str


class Episode(Strict):
    release: str
    persona: str
    scenario: str
    seed: int = 0
    app_build: str
    started_wall: str                                         # wall clock; the only non-deterministic field
    day0: datetime
    clock_measured: bool                                      # False: no clock hook, time-triggered surfaces unmeasured
    not_measured: list[NotMeasured] = Field(default_factory=list)
    initial_state: dict[str, OracleReading] = Field(default_factory=dict)
    steps: list[StepRecord] = Field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.release}/{self.persona}/{self.scenario}"

    def captures(self) -> list[Capture]:
        return [c for s in self.steps for c in s.captures]

    def step(self, seq: int) -> StepRecord:
        return next(s for s in self.steps if s.seq == seq)

    def messages(self) -> list[dict[str, Any]]:
        """Every marked message the user was shown or sent, once each, in the order first observed.

        A message is identified by (capture kind, surface, message key, time shown): a chat transcript that
        repeats an earlier turn does not count it twice. Elements without a message key (the user's own chat
        turn, PDF text lines) are not messages. Meaning is not extracted here; this only reads the markers.
        """
        seen: set[tuple] = set()
        out: list[dict[str, Any]] = []
        for step in self.steps:
            for cap in step.captures:
                for i, el in enumerate(cap.elements):
                    key = _first(el.attrs, KEY_ATTRS)
                    if not key:
                        continue
                    shown = _first(el.attrs, SHOWN_AT_ATTRS)
                    ident = (cap.kind, cap.surface, key, shown or cap.at.isoformat())
                    if ident in seen:
                        continue
                    seen.add(ident)
                    out.append({
                        "key": key, "feature": _first(el.attrs, FEATURE_ATTRS),
                        "component": _first(el.attrs, COMPONENT_ATTRS), "shown_at": shown,
                        "kind": cap.kind, "surface": cap.surface, "text": el.text, "attrs": el.attrs,
                        "step": step.seq, "capture": cap.id, "element": i, "phase": cap.phase,
                    })
        return out

    # ---- files
    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")

    @classmethod
    def read(cls, path: Path) -> "Episode":
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _first(attrs: dict[str, str], names: tuple[str, ...]) -> str | None:
    for n in names:
        if attrs.get(n):
            return attrs[n]
    return None


def episode_path(runs_dir: Path, run_id: str, release: str, persona: str, scenario: str) -> Path:
    return runs_dir / run_id / "episodes" / release / f"{persona}__{scenario}.json"
