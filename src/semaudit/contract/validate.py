"""Cross-reference checks on a loaded contract. A contract with problems is not auditable."""

from __future__ import annotations

from itertools import product

from .schema import CONFIDENCE, SEVERITY, VERIFICATION, Contract, ReleasePolicy, resolve_time

DATA_TESTS = {"time_until", "claim_matches_oracle"}     # condition tests the core knows how to evaluate


def policy_coverage(policy: ReleasePolicy) -> tuple[bool, set[int]]:
    """Enumerate every set of up to two open issues over severity x confidence x verification.

    Returns (exhaustive, rows that ever fire). Top-down first-match means "exactly one row" holds
    whenever some row fires, so exhaustive == no combination falls through.
    """
    kinds = [dict(severity=s, confidence=c, verification=v) for s, c, v in product(SEVERITY, CONFIDENCE, VERIFICATION)]
    sets = [[]] + [[k] for k in kinds] + [[a, b] for a in kinds for b in kinds]
    fired: set[int] = set()
    for issues in sets:
        try:
            _, i = policy.evaluate(issues)
        except ValueError:
            return False, fired
        fired.add(i)
    return True, fired


def validate(c: Contract) -> list[str]:
    p: list[str] = []
    features = {f.id for f in c.features}
    decisions = {d.id for d in c.decisions}
    surfaces = {s.id for s in c.surfaces}
    oracles = {o.id for o in c.oracles}
    facts = {f.id for f in c.facts}
    state = {v.id for v in c.state}
    personas = {x.id for x in c.personas}
    verbs = {s.do for sc in c.scenarios for s in sc.steps} | {a for v in c.state for a in v.set_by} \
        | {v.opens_on for v in c.state if v.opens_on}

    def need(kind: str, value, known: set, where: str):
        if known and value not in known:
            p.append(f"{where}: unknown {kind} {value!r}")

    for coll, what in ((c.rules, "rule"), (c.decisions, "decision"), (c.features, "feature"),
                       (c.personas, "persona"), (c.scenarios, "scenario")):
        seen = [x.id for x in coll]
        for dup in {i for i in seen if seen.count(i) > 1}:
            p.append(f"duplicate {what} id {dup!r}")

    for r in c.rules:
        if "decision" in r.applies_to:
            need("decision", r.applies_to["decision"], decisions, f"rule {r.id}")
        for k in (r.applies_to.get("state") or {}):
            need("state variable", k, state, f"rule {r.id} applies_to.state")
        if "oracle" in r.check:
            need("oracle", r.check["oracle"], oracles, f"rule {r.id} check")
        for claim in r.check.get("claims", []):
            need("fact", claim, facts, f"rule {r.id} check")
        for e in r.exceptions:
            for f in e.scope.get("features", []):
                need("feature", f, features, f"exception {e.id} scope")
            for s in e.scope.get("surfaces", []):
                need("surface", s, surfaces, f"exception {e.id} scope")
            if not e.approved.get("expires"):
                p.append(f"exception {e.id}: no expiry (exceptions must expire)")
            for cond in e.conditions:
                if cond.test == "time_until":
                    f = c.subject.field(cond.context_field or "")
                    if f is None or f.type != "time":
                        p.append(f"exception {e.id} condition {cond.id}: time_until needs context_field naming a "
                                 f"time field of subject.context (got {cond.context_field!r})")
                    if cond.hours is None:
                        p.append(f"exception {e.id} condition {cond.id}: time_until needs hours")
                if cond.kind == "data" and cond.test not in DATA_TESTS:
                    p.append(f"exception {e.id} condition {cond.id}: unknown data test {cond.test!r}")
                if cond.kind == "judged" and not cond.field:
                    p.append(f"exception {e.id} condition {cond.id}: judged condition needs a field")
                if cond.claim:
                    need("fact", cond.claim, facts, f"exception {e.id} condition {cond.id}")
                if cond.oracle:
                    need("oracle", cond.oracle, oracles, f"exception {e.id} condition {cond.id}")

    for d in c.decisions:
        for pre in d.preconditions.values():
            for k in pre:
                need("state variable", k, state, f"decision {d.id} precondition")
        for a in d.decided_by:
            need("action", a, verbs, f"decision {d.id} decided_by")
        for pair in d.incompatible + d.tradeoffs:
            for a in pair.pair:
                need("action", a, set(d.actions), f"decision {d.id} pair")

    for v in c.state:
        if v.hours_from_context:
            f = c.subject.field(v.hours_from_context)
            if f is None or f.type not in ("int", "float"):
                p.append(f"state {v.id}: hours_from_context must name a numeric field of subject.context")
    if c.subject.component_from and c.subject.field(c.subject.component_from) is None:
        p.append(f"subject.component_from: {c.subject.component_from!r} is not a context field")

    for f in c.facts:
        for src in f.sources:
            need("oracle", src.oracle, oracles, f"fact {f.id}")
            o = next((o for o in c.oracles if o.id == src.oracle), None)
            if o and src.field not in o.fields:
                p.append(f"fact {f.id}: oracle {src.oracle} has no field {src.field!r}")

    scheduled = set()
    for sc in c.scenarios:
        for x in sc.personas:
            need("persona", x, personas, f"scenario {sc.id}")
            if x in scheduled:      # a story is one episode; two scenarios would silently overwrite each other
                p.append(f"persona {x}: in more than one scenario (one scenario per persona is supported)")
            scheduled.add(x)
        try:
            times = sc.times()
        except ValueError as e:
            p.append(f"scenario {sc.id}: {e}")
            continue
        if any(b < a for a, b in zip(times, times[1:])):
            p.append(f"scenario {sc.id}: steps are not in time order")
    fields = {f.id: f for f in c.subject.context}
    for x in c.personas:
        for k in x.context:
            if k not in fields:
                p.append(f"persona {x.id}: context field {k!r} is not declared in subject.context")
        for f in fields.values():
            v = x.value(f.id, c.subject)
            if v is None:
                if f.required:
                    p.append(f"persona {x.id}: required context field {f.id!r} missing")
                continue
            bad = _type_problem(f, v, c.scenarios[0].day0 if c.scenarios else _epoch())
            if bad:
                p.append(f"persona {x.id}: context {f.id}: {bad}")
        if c.scenarios and x.id not in scheduled:
            p.append(f"persona {x.id}: in no scenario")

    if c.policy:
        exhaustive, fired = policy_coverage(c.policy)
        if not exhaustive:
            p.append("release policy is not exhaustive: some set of open issues fires no row")
        for i, row in enumerate(c.policy.rows):
            if exhaustive and i not in fired:
                p.append(f"release policy row {i + 1} ({row.recommendation}) can never fire")
    return p


def _type_problem(f, v, day0) -> str | None:
    if f.type == "time":
        try:
            resolve_time(str(v), day0)
        except ValueError as e:
            return str(e)
    elif f.type == "bool" and not isinstance(v, bool):
        return f"expected true/false, got {v!r}"
    elif f.type == "int" and (isinstance(v, bool) or not isinstance(v, int)):
        return f"expected an integer, got {v!r}"
    elif f.type == "float" and (isinstance(v, bool) or not isinstance(v, (int, float))):
        return f"expected a number, got {v!r}"
    elif f.type == "str" and not isinstance(v, str):
        return f"expected text, got {v!r}"
    elif f.type == "enum" and v not in f.values:
        return f"{v!r} is not one of {f.values}"
    return None


def _epoch():
    from datetime import datetime, timezone
    return datetime(2000, 1, 1, tzinfo=timezone.utc)
