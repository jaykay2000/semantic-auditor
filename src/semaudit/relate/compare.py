"""Compare an evaluated status vector with an authored expected vector, as exact sets."""

from __future__ import annotations

from semaudit.relate.rules import Entry


def entry_key(rule, subject, status, label=None, conditions=()) -> tuple:
    return (rule, subject, status, label, tuple(tuple(c) for c in (conditions or ())))


def expected_keys(expected: list[dict]) -> set[tuple]:
    return {entry_key(e["rule"], e["subject"], e["status"], e.get("label"), e.get("conditions", ()))
            for e in expected}


def actual_keys(entries: list[Entry]) -> set[tuple]:
    return {entry_key(*e.key()) for e in entries}


def diff(entries: list[Entry], expected: list[dict]) -> dict:
    got, want = actual_keys(entries), expected_keys(expected)
    return {"match": got == want, "missing": sorted(map(str, want - got)), "unexpected": sorted(map(str, got - want))}
