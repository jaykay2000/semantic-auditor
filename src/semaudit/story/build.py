"""Episode -> User Experience Story: the time-ordered events one persona lived through.

Everything here is structural (no model): messages come from the app's own markers, actions from the
scenario steps that ran, and the truth snapshots from the oracles read after each step. W6 then extracts
what each message means; the rules read the result.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from semaudit.contract.schema import Contract, Fact, resolve_context
from semaudit.story.episode import Episode, OracleReading
from semaudit.story.model import Event, Evidence, Story

CHANNEL_ATTRS = ("data-channel",)
KIND_CHANNEL = {"email": "email", "push": "push", "chat": "chat", "pdf": "pdf", "text": "text"}


def fact_value(fact: Fact, state: dict[str, OracleReading], feature: str | None = None,
               oracle: str | None = None) -> Any:
    """The fact's value in one state snapshot: the first source whose oracle reads. None if none applies.
    `oracle`: only that oracle's sources (a rule that names the oracle it is checked against).

    A source with match_feature keeps only list items belonging to `feature` (a fee claim is checked against
    the claiming feature's own charges, never another transaction's)."""
    for src in fact.sources:
        if oracle is not None and src.oracle != oracle:
            continue
        reading = state.get(src.oracle)
        if reading is None or reading.status != "ok" or src.field not in reading.values:
            continue
        v = reading.values[src.field]
        if src.where or src.match_feature:
            items = [x for x in (v or []) if all(x.get(k) == w for k, w in src.where.items())
                     and (not src.match_feature or x.get(src.match_feature) == feature)]
            if not items:
                continue
            v = sum(x[src.take] for x in items) if src.take else items
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            v = round(v * src.scale, 2) if src.scale != 1.0 else v
        return v
    return None


def snapshot(at: datetime, state: dict[str, OracleReading], contract: Contract) -> dict[str, Any]:
    """`truth`: each fact's value (first source that reads). `by_oracle`: for a fact with sources on more than one
    oracle, each oracle's own value, so a rule that names its oracle (`check.oracle`) is checked against that one
    and not against whichever source happens to come first. Kept apart from `truth`, so nothing that reads
    `truth` (the extraction schema, the report's state rows) changes."""
    truth: dict[str, Any] = {}
    by_oracle: dict[str, dict[str, Any]] = {}
    for f in contract.facts:
        oracles = list(dict.fromkeys(s.oracle for s in f.sources))
        names = ([(f"{f.id}@{feat.id}", feat.id) for feat in contract.features]
                 if any(s.match_feature for s in f.sources) else [(f.id, None)])
        for name, feat in names:
            if (v := fact_value(f, state, feat)) is not None:
                truth[name] = v
            if len(oracles) > 1:
                per = {o: v for o in oracles if (v := fact_value(f, state, feat, o)) is not None}
                if per:
                    by_oracle[name] = per
    out: dict[str, Any] = {"at": at, "truth": truth}
    if by_oracle:
        out["by_oracle"] = by_oracle
    return out


SHORT_WORDS = 4      # a block this short ("$860K", "Net worth") is read with its neighbours


def around(cap, index: int, width: int = 1) -> str | None:
    """For a short block on a page, the readable text just before and after it: a figure's label often sits in
    its own block, and "$860K" alone cannot be told from any other amount. Context only, never a claim source.
    Only for blocks the contract map cut out of a page; a message the app marks itself is already a whole unit.
    A section mapped with `each` bounds the context at each matched element (one labelled row), not at the selector."""
    el = cap.elements[index]
    if cap.kind != "web" or len((el.text or "").split()) > SHORT_WORDS:
        return None
    sec = lambda e: ((getattr(e, "attribution", None) or {}).get("section"),  # noqa: E731
                     (getattr(e, "attribution", None) or {}).get("root"))      # set only for a section with `each`
    readable = lambda e: (bool((e.text or "").strip()) and not e.obscured  # noqa: E731
                          and sec(e) == sec(el))                                  # never across a section boundary
    clip = lambda t: " ".join(t.split())[:80]  # noqa: E731
    before = [clip(e.text) for e in reversed(cap.elements[:index]) if readable(e)][:width][::-1]
    after = [clip(e.text) for e in cap.elements[index + 1:] if readable(e)][:width]
    if not before and not after:
        return None
    return " | ".join(before or [""]) + " | [this] | " + " | ".join(after or [""])


def _around_width(surface, el) -> int:
    i = (getattr(el, "attribution", None) or {}).get("section")
    secs = getattr(surface, "sections", None) or []
    return secs[i].around if isinstance(i, int) and 0 <= i < len(secs) else 1


def story_from_episode(ep: Episode, contract: Contract) -> Story:
    persona = contract.persona(ep.persona)
    scenario = next(s for s in contract.scenarios if s.id == ep.scenario)
    context = resolve_context(persona, contract.subject, scenario.day0)
    default_component = context.get(contract.subject.component_from) if contract.subject.component_from else None
    features = {f.id: f for f in contract.features}
    surfaces = {s.id: s for s in contract.surfaces}
    captures = {c.id: c for c in ep.captures()}

    events: list[Event] = []
    for st in ep.steps:
        if st.status == "done":
            events.append(Event(id=f"a{st.seq:02d}_{st.do}", at=st.at, kind="user_action", action=st.do,
                                params=dict(st.params)))
        elif st.status == "app_failed":
            # never a user_action: it changed no state. copy_key names the action, so the same failure in base and
            # head is one issue whatever the app's wording
            shot = next((c for c in st.captures if c.kind == "web" and c.status != "not_measured"), None)
            ev = Evidence(episode=ep.id, step=st.seq, capture_id=shot.id, element=0, locator={},
                          capture_sha256=dict(shot.sha256), attribution={"method": "step", "confidence": 1.0}) \
                if shot else None
            events.append(Event(id=f"a{st.seq:02d}_{st.do}", at=st.at, kind="failed_action", action=st.do,
                                params=dict(st.params), surface=shot.surface if shot else None,
                                copy_key=f"action:{st.do}", text=st.error, evidence=ev))

    seen = Counter()
    for m in ep.messages():
        cap = captures[m["capture"]]
        # A time the app states (data-shown-at, an email's sent_at) is on the episode's clock only when the app
        # runs on the simulated clock; otherwise it is wall time, days away from the steps, and the capture's
        # (step) time places the message.
        at = datetime.fromisoformat(m["shown_at"]) if m["shown_at"] and ep.clock_measured else cap.at
        seen[m["key"]] += 1
        eid = m["key"] if seen[m["key"]] == 1 else f"{m['key']}#{seen[m['key']]}"
        channel = next((m["attrs"][a] for a in CHANNEL_ATTRS if a in m["attrs"]), None) \
            or KIND_CHANNEL.get(m["kind"], "page")
        user_turn = surfaces.get(cap.surface).user_turn if cap.surface in surfaces else {}
        prev = cap.elements[m["element"] - 1] if m["element"] > 0 else None
        initiated = bool(user_turn and prev and all(prev.attrs.get(k) == v for k, v in user_turn.items()))
        feat = features.get(m["feature"])
        el = cap.elements[m["element"]]
        attr_src = m.get("attribution") if m.get("attribution") not in (None, "dom_attr") else \
            ("dom_attr" if cap.kind in ("web", "chat") else "header")
        evidence = Evidence(episode=ep.id, step=m["step"], capture_id=cap.id, element=m["element"],
                            locator=el.locator, capture_sha256=dict(cap.sha256),
                            attribution={"method": attr_src, "confidence": 1.0})
        events.append(Event(
            id=eid, at=at, kind="message", feature=m["feature"], surface=cap.surface, channel=channel,
            component=m["component"] or default_component, topic=feat.topic if feat else None,
            user_initiated=initiated, copy_key=m["key"], text=m["text"],
            before_action=bool(cap.surface in surfaces and surfaces[cap.surface].shown_before_action),
            alternate_format=bool(cap.surface in surfaces and surfaces[cap.surface].format_of),
            around=around(cap, m["element"], _around_width(surfaces.get(cap.surface), el))
            if attr_src == "contract_map" else None,
            evidence=evidence))

    events.sort(key=lambda e: (e.at, 0 if e.kind == "user_action" else 1))
    snaps = [snapshot(scenario.day0, ep.initial_state, contract)] if ep.initial_state else []
    snaps += [snapshot(st.at, st.state, contract) for st in ep.steps if st.state]
    return Story(id=ep.id.replace("/", "__"), release=ep.release, persona=ep.persona, context=context,
                 truth=dict(persona.reference), snapshots=snaps, events=events)
