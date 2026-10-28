"""The ONE comparison between a claim a message makes and the true value of that fact.

Every place that asks "is this claim true?" calls `compare`: rule evaluation (match_oracle, match_charge), the
claim_matches_oracle exception condition, the issue text, and the review page (through the per-claim verdict
written into review.json). A second comparison anywhere is how a claim reads true on one surface and false on
another.

Verdicts:
  match       the claim states the true value
  mismatch    the claim states a different value: the only verdict that can become a violation
  unreadable  the claim's value could not be read in the form the truth takes (e.g. a date/time claim with no
              readable time). This is an extraction gap, not a product fault, so it is never a violation.

A claim the message showed rounded ("$1.2M") carries its displayed `precision` (100000) when the contract asks
for it (a fact with `match: displayed`), and matches any truth that rounds to it: within half that step.

A truth that is a date/time (a datetime, or an ISO 8601 string) is compared with the claim's `when`, at the
claim's own precision. A date-only claim compares dates. A time that states no seconds compares to the minute;
one that states them (even ":00") compares to the second. A claim with no time zone is read as the wall-clock
time the truth is expressed in. Anything else is compared as a number.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any

MATCH, MISMATCH, UNREADABLE = "match", "mismatch", "unreadable"


def _as_datetime(v: Any) -> datetime | None:
    if isinstance(v, datetime):
        return v
    if isinstance(v, str) and len(v) >= 10 and v[4:5] == "-":
        try:
            return datetime.fromisoformat(v)
        except ValueError:
            return None
    return None


def is_temporal(truth: Any) -> bool:
    return _as_datetime(truth) is not None


def precision(claim: dict) -> float:
    """The size of the last digit the message showed ('$1.2M' -> 100000), when the extractor recorded it (contracts
    with a `match: displayed` fact). 0 means exact."""
    p = claim.get("precision")
    return float(p) if isinstance(p, (int, float)) and not isinstance(p, bool) and p > 0 else 0.0


def checkable(claim: dict, fact=None) -> bool:
    """A claim the fact's true value can check: one whose role is a role the fact's truth describes (by default
    as_is, the figure as it is now). A target, what-if or change is not the user's current figure and is never
    compared with the oracle's; for a fact that IS a limit, a claim stating the limit is. Without roles every
    claim is checkable, as before."""
    return claim.get("role") in (None, *(fact.truth_roles if fact is not None else ("as_is",)))


ROLE_GROUP = {"as_is": "as_is", "proposed": "level", "limit": "level", "change": "change"}


def comparable(fact, a: dict, b: dict) -> bool:
    """Two claims can disagree only if they are the same kind of figure about the same quantity (key). A target
    and the cap it is set at are both the level to reach ("ramp toward $X" / "the max of $X"), so proposed and
    limit compare with each other; the current figure and the size of a change each compare only with their own."""
    ra, rb = a.get("role"), b.get("role")
    return ROLE_GROUP.get(ra, ra) == ROLE_GROUP.get(rb, rb) and same_quantity(fact, a, b)


UNKEYED = ("", "unknown", "other")   # a key that names no single quantity ("other" is a catch-all)


def same_quantity(fact, a: dict, b: dict) -> bool:
    """Two claims of one fact are about the same quantity. Always, for a plain fact. For a family fact (`key`),
    only when every key field names the same known value in both: an unknown, catch-all ('other'), missing or
    out-of-vocabulary key is never compared, because two different quantities would read as a disagreement."""
    for k in (fact.key if fact is not None else []):
        va, vb = a.get(k.field), b.get(k.field)
        if not isinstance(va, str) or va.strip().lower() in UNKEYED or (k.values and va not in k.values):
            return False
        if va.strip().lower() != (vb or "").strip().lower():
            return False
    return True


UNWORDED = ("", "unknown", "other", "none")   # a word claim that names nothing in particular


def word(claim: dict) -> str | None:
    w = claim.get("word")
    return w.strip().lower() if isinstance(w, str) and w.strip().lower() not in UNWORDED else None


def compare(claim: dict, truth: Any, truth_precision: float = 0.0) -> str:
    """`truth_precision` is the displayed precision of the other side when the truth is itself a shown claim: two
    roundings agree when they are within half the coarser step of each other. A word claim (`word`: an action
    id, yes/no) matches a word truth exactly, ignoring case; an unknown word is unreadable."""
    if "word" in claim and claim.get("value") is None and (isinstance(truth, str) or truth is None):
        w = word(claim)
        if w is None or not isinstance(truth, str) or truth.strip().lower() in UNWORDED:
            return UNREADABLE
        return MATCH if w == truth.strip().lower() else MISMATCH
    if is_temporal(truth):
        return _compare_time(claim.get("when"), _as_datetime(truth))
    v = claim.get("value")
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not isinstance(truth, (int, float)):
        return MATCH if v == truth and v is not None else (UNREADABLE if v is None else MISMATCH)
    tol = max(precision(claim), truth_precision) / 2
    return MATCH if math.isclose(float(v), float(truth), rel_tol=0, abs_tol=tol + 1e-9) else MISMATCH


def _compare_time(when: Any, truth: datetime) -> str:
    if not isinstance(when, str) or not when.strip():
        return UNREADABLE
    w = when.strip()
    if len(w) == 10:                                   # YYYY-MM-DD: the claim states a date only
        try:
            return MATCH if date.fromisoformat(w) == truth.date() else MISMATCH
        except ValueError:
            return UNREADABLE
    claimed = _as_datetime(w)
    if claimed is None:
        return UNREADABLE
    if claimed.tzinfo is not None and truth.tzinfo is not None:
        truth = truth.astimezone(claimed.tzinfo)       # same instant, in the zone the message speaks in
    claimed, truth = claimed.replace(tzinfo=None), truth.replace(tzinfo=None)
    if not _states_seconds(w):
        truth = truth.replace(second=0, microsecond=0)  # "14:05" states the minute, not the second
    elif claimed.microsecond == 0:
        truth = truth.replace(microsecond=0)            # "14:05:00" states the second
    return MATCH if claimed == truth else MISMATCH


_TZ = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")


def _states_seconds(when: str) -> bool:
    """Whether the stated time gives seconds. Read from the text, not the value: "14:05:00" states the second
    (and is wrong against 14:05:30), "14:05" states only the minute."""
    clock = _TZ.sub("", when[11:])
    return clock.count(":") >= 2


def stated(claim: dict):
    """The value a claim states, in the form `compare` takes as a truth: its moment if it has one, else its
    amount. None when it states neither (unreadable)."""
    return claim.get("when") or (claim.get("value") if claim.get("value") is not None else word(claim))


def shown(claim: dict) -> str:
    """The claim as the message states it, for issue text and the page."""
    if claim.get("when"):
        return str(claim["when"])
    if claim.get("value") is None and word(claim):
        return word(claim)
    v = claim.get("value")
    if v is None:
        return "?"
    return f"{v:g}" if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)
