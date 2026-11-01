"""The imported-check record and its import vocabulary.

A check keeps three things apart:
  actions    the persona and steps the replay runs (only adapter verbs);
  invariant  what must hold, tied to one owner rule and one surface, stated against the store's own record so it
             survives wording and layout changes;
  source     the agent's finding as written (claim, where, shown, reproduce, rule): evidence of the original
             finding only. The quote is never shown to the judge, so a fix is confirmed by the invariant passing,
             not by the old words disappearing.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

ConversionStatus = Literal["converted", "partially_converted", "adapter_gap", "not_converted"]
ImportOutcome = Literal["replayed", "partially_converted", "adapter_gap", "not_converted", "replay_failed",
                        "not_replayed_yet"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- the consumer's import vocabulary (imports.yaml beside the contract) ----------

class ListField(Strict):
    """A persona list field whose elements name catalog entries, e.g. 'key|member|count'. `pattern` is a regex with
    named groups; `key_group` must equal a catalog entry's `key_attr`, `member_group` must be empty or one of that
    entry's `members_attr` values."""
    pattern: str
    catalog: str                          # json file, relative to the contract directory
    key_group: str
    key_attr: str
    member_group: str | None = None
    members_attr: str | None = None
    show_attrs: list[str] = Field(default_factory=list)   # catalog attributes shown to the converter


class ImportSpec(Strict):
    verbs: dict[str, str]                 # adapter verb -> what it does, for the converter
    verb_args: dict[str, dict[str, Any]] = Field(default_factory=dict)   # verb -> step params the importer sets
    implied_ok: list[str] = Field(default_factory=list)   # verbs a reproduction may leave unsaid (prerequisites)
    read_verbs: dict[str, list[str]] = Field(default_factory=dict)   # verb that only reads -> surfaces it lands
                                                          # on; implied only to reach the invariant's surface
    prerequisites: dict[str, list[str]] = Field(default_factory=dict)   # verb -> verbs that must come before it;
                                                          # missing implied_ok ones are inserted, others are reported
    verb_cues: dict[str, str] = Field(default_factory=dict)   # verb -> regex its clause must match ("{catalog}":
                                                          # any catalog entry's name or key also counts)
    list_fields: dict[str, ListField] = Field(default_factory=dict)
    material_fields: list[str] = Field(default_factory=list)   # must come from the finding or a declared default
    persona_defaults: dict[str, Any] = Field(default_factory=dict)
    place_defaults: dict[str, dict[str, Any]] = Field(default_factory=dict)   # value of `place_field` -> defaults
    place_field: str | None = None
    unique_fields: dict[str, str] = Field(default_factory=dict)   # field -> template with {id}, set by the importer
    rule_aliases: dict[str, str] = Field(default_factory=dict)    # the finding's rule names -> contract rule ids
    step_note_fails: list[str] = Field(default_factory=list)   # regexes: an adapter step note saying the app did
                                                          # not do what the scenario needs (a refused code...)
    action_words: list[str] = Field(default_factory=list)  # regexes: an "observation" clause matching one is
                                                           # suspected of hiding an action (fail closed)
    day0: str = "2026-11-02T00:00:00+00:00"


def load_spec(contract_dir: Path) -> ImportSpec:
    p = Path(contract_dir) / "imports.yaml"
    if not p.exists():
        raise FileNotFoundError(f"{p}: the contract declares no import vocabulary, so nothing can be imported")
    return ImportSpec(**yaml.safe_load(p.read_text()))


# ---------- the check ----------

class Source(Strict):
    """The agent's finding, verbatim. Evidence of the original finding only."""
    ref: str                              # e.g. "C2#05"
    trial: str | None = None
    heading: str | None = None
    claim: str = ""
    where: str = ""
    shown: str = ""                       # the original quoted text
    should_be: str = ""
    reproduce: str = ""
    rule: str = ""
    sha256: str = ""                      # of the fields above, as imported


class Clause(Strict):
    text: str
    kind: Literal["action", "context", "observation", "alternative"]
    steps: list[int] = Field(default_factory=list)
    sets: list[str] = Field(default_factory=list)
    unmapped: dict[str, Any] | None = None    # {reason: no_verb | cannot_map, missing_verb, why}


class Invariant(Strict):
    rule: str                             # contract rule id
    surface: str
    statement: str


class Conversion(Strict):
    status: ConversionStatus
    reasons: list[str] = Field(default_factory=list)       # why it is not "converted"
    gaps: list[str] = Field(default_factory=list)          # verbs the adapter would need
    unmapped: list[str] = Field(default_factory=list)      # clauses that name actions not converted
    alternatives: list[str] = Field(default_factory=list)  # other reproduction paths in the text, not converted
    defaulted: list[str] = Field(default_factory=list)     # persona fields set from declared defaults
    implied_steps: list[str] = Field(default_factory=list)
    gate_rounds: int = 1                  # 2: the first draft failed the gate and was redrafted once
    gate_errors: list[list[str]] = Field(default_factory=list)   # per round
    model: str | None = None
    cost_usd: float | None = None


class ImportedCheck(Strict):
    id: str
    source: Source
    clauses: list[Clause] = Field(default_factory=list)
    persona: dict[str, Any] = Field(default_factory=dict)     # a contract Persona, as a dict
    scenario: dict[str, Any] = Field(default_factory=dict)    # a contract Scenario, as a dict
    invariant: Invariant | None = None
    conversion: Conversion
    converter: dict[str, str] = Field(default_factory=dict)   # code commit + prompt hash the draft was made with

    def digest(self) -> str:
        """What the owner approves: actions and invariant (not the source or the conversion log)."""
        body = {"persona": self.persona, "scenario": self.scenario,
                "invariant": self.invariant.model_dump() if self.invariant else None}
        return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:16]

    def write(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        p = directory / f"{self.id}.yaml"
        p.write_text(yaml.safe_dump(self.model_dump(mode="json"), sort_keys=False, allow_unicode=True))
        return p

    @classmethod
    def read(cls, path: Path) -> "ImportedCheck":
        return cls(**yaml.safe_load(Path(path).read_text()))


def source_from_item(ref: str, item: dict[str, Any]) -> Source:
    """An agent finding (the graded item format: claim, where, shown, should_be, reproduce, rule) as a Source."""
    fields = {k: str(item.get(k) or "") for k in ("claim", "where", "shown", "should_be", "reproduce", "rule")}
    src = item.get("_source") or {}
    sha = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()[:16]
    return Source(ref=ref, trial=src.get("trial"), heading=src.get("heading"), sha256=sha, **fields)
