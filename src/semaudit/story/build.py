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
KIND_CHANNEL = {"email": "email", "push": "push", "chat": "chat", "pdf": "pdf"}


def fact_value(fact: Fact, state: dict[str, OracleReading], feature: str | None = None) -> Any:
    """The fact's value in one state snapshot: the first source whose oracle reads. None if none applies.

    A source with match_feature keeps only list items belonging to `feature` (a fee claim is checked against
    the claiming feature's own charges, never another transaction's)."""
    for src in fact.sources:
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
    truth: dict[str, Any] = {}
    for f in contract.facts:
        if any(s.match_feature for s in f.sources):
            for feat in contract.features:
                if (v := fact_value(f, state, feat.id)) is not None:
                    truth[f"{f.id}@{feat.id}"] = v
        elif (v := fact_value(f, state)) is not None:
            truth[f.id] = v
    return {"at": at, "truth": truth}


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
            events.append(Event(id=f"a{st.seq:02d}_{st.do}", at=st.at, kind="user_action", action=st.do))

    seen = Counter()
    for m in ep.messages():
        cap = captures[m["capture"]]
        at = datetime.fromisoformat(m["shown_at"]) if m["shown_at"] else cap.at
        seen[m["key"]] += 1
        eid = m["key"] if seen[m["key"]] == 1 else f"{m['key']}#{seen[m['key']]}"
        channel = next((m["attrs"][a] for a in CHANNEL_ATTRS if a in m["attrs"]), None) \
            or KIND_CHANNEL.get(m["kind"], "page")
        user_turn = surfaces.get(cap.surface).user_turn if cap.surface in surfaces else {}
        prev = cap.elements[m["element"] - 1] if m["element"] > 0 else None
        initiated = bool(user_turn and prev and all(prev.attrs.get(k) == v for k, v in user_turn.items()))
        feat = features.get(m["feature"])
        el = cap.elements[m["element"]]
        attr_src = "dom_attr" if cap.kind in ("web", "chat") else "header"
        evidence = Evidence(episode=ep.id, step=m["step"], capture_id=cap.id, element=m["element"],
                            locator=el.locator, capture_sha256=dict(cap.sha256),
                            attribution={"method": attr_src, "confidence": 1.0})
        events.append(Event(
            id=eid, at=at, kind="message", feature=m["feature"], surface=cap.surface, channel=channel,
            component=m["component"] or default_component, topic=feat.topic if feat else None,
            user_initiated=initiated, copy_key=m["key"], text=m["text"], evidence=evidence))

    events.sort(key=lambda e: (e.at, 0 if e.kind == "user_action" else 1))
    snaps = [snapshot(scenario.day0, ep.initial_state, contract)] if ep.initial_state else []
    snaps += [snapshot(st.at, st.state, contract) for st in ep.steps if st.state]
    return Story(id=ep.id.replace("/", "__"), release=ep.release, persona=ep.persona, context=context,
                 snapshots=snaps, events=events)
