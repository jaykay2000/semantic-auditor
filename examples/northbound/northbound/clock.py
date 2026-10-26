"""Simulated clock and job queue. Every timestamp in Northbound comes from here.

Times are timezone-aware UTC and keep full precision: nothing is rounded or truncated, so a departure
72 h 00 min 30 s away is never "within 72 h".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

UTC = timezone.utc
D0 = datetime(2026, 11, 2, 10, 0, 0, tzinfo=UTC)

_TOKEN = re.compile(r"(\d+)([dhms])")
_UNIT = {"d": "days", "h": "hours", "m": "minutes", "s": "seconds"}


def parse_duration(text: str) -> timedelta:
    """'2h', '30s', '1d2h', '5m10s' -> timedelta. Anything else is a ValueError."""
    s = text.strip().lower().replace(" ", "")
    if not s:
        raise ValueError("empty duration")
    total, pos = timedelta(), 0
    for m in _TOKEN.finditer(s):
        if m.start() != pos:
            raise ValueError(f"bad duration {text!r}")
        total += timedelta(**{_UNIT[m.group(2)]: int(m.group(1))})
        pos = m.end()
    if pos != len(s):
        raise ValueError(f"bad duration {text!r}")
    return total


def parse_instant(text: str) -> datetime:
    """ISO-8601 with an explicit offset (or Z). Naive times are rejected: no guessing a zone."""
    d = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError(f"time {text!r} has no timezone")
    return d.astimezone(UTC)


def iso(d: datetime) -> str:
    return d.astimezone(UTC).isoformat()


class SimClock:
    def __init__(self, start: datetime = D0):
        self._now = start

    @property
    def now(self) -> datetime:
        return self._now

    def set_now(self, when: datetime) -> None:
        self._now = when.astimezone(UTC)


@dataclass
class Job:
    id: str
    due: datetime
    feature: str
    kind: str
    traveller_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    seq: int = 0

    def summary(self) -> dict[str, Any]:
        return {"id": self.id, "due": iso(self.due), "feature": self.feature, "kind": self.kind,
                "traveller": self.traveller_id}


class JobQueue:
    def __init__(self) -> None:
        self._jobs: list[Job] = []
        self._seq = 0

    def schedule(self, due: datetime, feature: str, kind: str, traveller_id: str | None = None,
                 payload: dict[str, Any] | None = None) -> Job:
        self._seq += 1
        job = Job(f"j{self._seq:05d}", due, feature, kind, traveller_id, payload or {}, self._seq)
        self._jobs.append(job)
        return job

    def cancel(self, feature: str | None = None, traveller_id: str | None = None) -> list[Job]:
        gone = [j for j in self._jobs
                if (feature is None or j.feature == feature)
                and (traveller_id is None or j.traveller_id == traveller_id)]
        self._jobs = [j for j in self._jobs if j not in gone]
        return gone

    def pop_due(self, until: datetime) -> Job | None:
        """The earliest job due at or before `until` (ties: scheduling order), removed from the queue."""
        due = [j for j in self._jobs if j.due <= until]
        if not due:
            return None
        job = min(due, key=lambda j: (j.due, j.seq))
        self._jobs.remove(job)
        return job

    def pending(self) -> list[Job]:
        return sorted(self._jobs, key=lambda j: (j.due, j.seq))


def run_until(clock: SimClock, queue: JobQueue, target: datetime, run: Callable[[Job], None]) -> list[Job]:
    """Move the clock to `target`, running every due job in due-time order with the clock set to its due time."""
    ran: list[Job] = []
    for _ in range(10_000):
        job = queue.pop_due(target)
        if job is None:
            break
        clock.set_now(max(job.due, clock.now))
        run(job)
        ran.append(job)
    else:  # pragma: no cover
        raise RuntimeError("job queue did not drain")
    clock.set_now(target)
    return ran
