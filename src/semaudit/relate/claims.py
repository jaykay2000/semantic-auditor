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

A truth that is a date/time (a datetime, or an ISO 8601 string) is compared with the claim's `when`, at the
claim's own precision. A date-only claim compares dates. A time with no seconds compares to the minute. A claim
with no time zone is read as the wall-clock time the truth is expressed in. Anything else is compared as a
number.
"""

from __future__ import annotations

import math
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


def compare(claim: dict, truth: Any) -> str:
    if is_temporal(truth):
        return _compare_time(claim.get("when"), _as_datetime(truth))
    v = claim.get("value")
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not isinstance(truth, (int, float)):
        return MATCH if v == truth and v is not None else (UNREADABLE if v is None else MISMATCH)
    return MATCH if math.isclose(float(v), float(truth), rel_tol=0, abs_tol=1e-9) else MISMATCH


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
    if claimed.second == 0 and claimed.microsecond == 0:
        truth = truth.replace(second=0, microsecond=0)  # "14:05" states the minute, not the second
    return MATCH if claimed == truth else MISMATCH


def shown(claim: dict) -> str:
    """The claim as the message states it, for issue text and the page."""
    if claim.get("when"):
        return str(claim["when"])
    v = claim.get("value")
    if v is None:
        return "?"
    return f"{v:g}" if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)
