"""Align a base-release story with a head-release story of the same persona and scenario (W7).

Events are paired by a stable event_key: feature / surface / message key / occurrence (user actions:
action / occurrence). Events left over are paired FUZZILY only when they are the same feature, surface and
channel at the same simulated moment (a reply to the same question, the card in the same slot), and are
marked fuzzy. Everything else is explicitly unmatched: `added` in head or `removed` from base, never forced.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

from semaudit.story.model import Event, Story

PairStatus = Literal["unchanged", "changed", "fuzzy"]


def event_keys(story: Story) -> dict[str, str]:
    """event id -> event_key, with an occurrence index so repeats stay distinct."""
    seen: Counter = Counter()
    out = {}
    for e in story.events:
        base = (f"action/{e.action}" if e.kind == "user_action"
                else f"{e.feature}/{e.surface}/{e.copy_key}")
        seen[base] += 1
        out[e.id] = f"{base}#{seen[base]}"
    return out


@dataclass
class Pair:
    base: str
    head: str
    status: PairStatus
    event_key: str


@dataclass
class StoryDiff:
    base_release: str
    head_release: str
    persona: str
    pairs: list[Pair] = field(default_factory=list)
    added: list[str] = field(default_factory=list)      # head event ids with no base partner
    removed: list[str] = field(default_factory=list)    # base event ids with no head partner

    def head_status(self, head_id: str) -> str:
        """added | unchanged | changed | fuzzy, for one head event."""
        if head_id in self.added:
            return "added"
        return next(p.status for p in self.pairs if p.head == head_id)

    def base_of(self, head_id: str) -> str | None:
        return next((p.base for p in self.pairs if p.head == head_id), None)


def _slot(e: Event) -> tuple:
    return (e.feature, e.surface, e.channel, e.at)


def align(base: Story, head: Story) -> StoryDiff:
    if base.persona != head.persona:
        raise ValueError(f"cannot align {base.persona} with {head.persona}")
    bk, hk = event_keys(base), event_keys(head)
    b_by_key = {k: i for i, k in bk.items()}
    bev = {e.id: e for e in base.events}
    hev = {e.id: e for e in head.events}
    diff = StoryDiff(base.release, head.release, head.persona)
    used: set[str] = set()
    unmatched_head: list[str] = []
    for e in head.events:
        key = hk[e.id]
        bid = b_by_key.get(key)
        if bid is None:
            unmatched_head.append(e.id)
            continue
        used.add(bid)
        same = e.kind == "user_action" or bev[bid].text == e.text
        diff.pairs.append(Pair(bid, e.id, "unchanged" if same else "changed", key))
    leftover = [i for i in bk if i not in used]
    for hid in unmatched_head:
        h = hev[hid]
        cand = next((b for b in leftover if h.kind == "message" and bev[b].kind == "message"
                     and _slot(bev[b]) == _slot(h)), None)
        if cand:
            leftover.remove(cand)
            diff.pairs.append(Pair(cand, hid, "fuzzy", f"≈{hk[hid]}"))
        else:
            diff.added.append(hid)
    diff.removed = leftover
    return diff
