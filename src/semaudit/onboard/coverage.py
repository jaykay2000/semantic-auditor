"""`semaudit coverage`: what a review's personas never exercised, and drafts that would.

A rule the engine can check is silent when no persona showed it what it checks, and that silence reads like a pass.
The coverage map re-derives a review from its pinned episodes and recorded readings (offline, the way verify-report
does) and lists, from the contract's own model, each such gap:

  rule_never_exercised   a rule the engine evaluates that no message of any persona was evaluated under
  fact_never_checked     a figure or word a rule lists in check.claims that the rule never compared (a check counts
                         only for the fact it compared; the gap says how often the fact was shown at all)
  surface_never_reached  a surface no persona's episode captured (its reached_by verb, if any, in no scenario)
  exception_never_met    a rule exception whose conditions never all held for any message

Listed apart (`engine_gaps`), because a new persona cannot fix them: rules the engine does not evaluate, facts an
oracle rule lists that the oracle gave no true value for in any story (the contract or adapter must read them), and
text facts with no word list (the extraction cannot state their value).

`draft_personas` asks one model call to propose, for the gaps, new personas (and the scenario each joins, or a new
scenario built only from the contract's existing scenario verbs). Code checks every draft against the contract: the
persona's context fields must be ones the contract or its personas already use, every step verb must be one the
contract already uses, ids must be new. Drafts are written to a separate file, never into the contract; `accept`
copies one in, after which the contract's owner approval applies to it like any other change.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from semaudit.contract.schema import Contract, Persona, Scenario, load_contract
from semaudit.decide.pipeline import evaluate_release
from semaudit.models.router import ModelError, Router


class CannotMap(RuntimeError):
    pass


def _claim_facts(rule) -> list[str]:
    check = rule.check if isinstance(rule.check, dict) else {}
    return list(check.get("claims") or (rule.applies_to or {}).get("claims") or [])


def coverage_map(review_path: Path, *, root: Path | None = None, cache: Path | None = None,
                 index_readings: bool = False) -> dict:
    """The review's head release, re-derived offline from its manifest's inputs; every gap with what it is.
    `index_readings`: also add both releases' message readings to <cache>/readings/, so the run that tries a drafted
    persona reads only that persona's new messages (a review made before per-message readings has no other record
    of them)."""
    r = json.loads(review_path.read_text())
    m = r.get("manifest") or {}
    if not m:
        raise CannotMap("no manifest in this review")
    run_dir = Path(m["run_dir"])
    if not run_dir.is_absolute() and not (run_dir / "episodes").is_dir():
        run_dir = review_path.parent
    contract = load_contract(Path(m["contract"]["dir"]), memory=(m.get("memory") or {}).get("issues", []))
    router = Router(root=root or Path.cwd(), offline=True)
    router.pinned_readings = m.get("readings")
    beside = review_path.parent / "model-cache"
    if cache is not None or beside.is_dir():
        router.cache_dir = cache if cache is not None else beside
    head = r["release"]["head"]
    router.reading_index = router.index_offline = index_readings
    try:
        if index_readings:
            evaluate_release(run_dir, r["release"]["base"], contract, router,
                             readings={} if getattr(contract.app, "share_readings", False) else None)
        h = evaluate_release(run_dir, head, contract, router,
                             readings={} if getattr(contract.app, "share_readings", False) else None)
    except ModelError as e:
        raise CannotMap(f"cannot re-derive offline: {e}") from e
    return gaps_of(contract, h, head)


def gaps_of(contract: Contract, h, head: str) -> dict:
    from semaudit.relate.claims import TEXT_UNITS, unmeasurable_rules
    defs = {f.id: f for f in getattr(contract, "facts", [])}
    from semaudit.relate.rules import engine_support
    engine: dict[str, str] = {}
    for x in unmeasurable_rules(contract):
        engine[x["rule"]] = x["reason"]
    for rule in contract.rules:
        runs, gap = engine_support(rule)
        if gap and not runs:
            engine[rule.id] = f"not evaluated: {gap}"
    evaluated: dict[str, int] = {r.id: 0 for r in contract.rules}
    facts_seen: dict[str, set] = {r.id: set() for r in contract.rules}
    met: dict[tuple[str, str], int] = {}
    surfaces_captured: set[str] = set()
    stated: dict[str, int] = {}               # fact -> claims of it, in any message of any persona
    known: set[str] = set()                   # facts the oracle gave a true value for, in any story
    for story, entries in h.results.values():
        by = {e.id: e for e in story.events}
        for e in story.events:
            if e.surface:
                surfaces_captured.add(e.surface)
            for c in (e.extraction.claims if getattr(e, "extraction", None) else []):
                stated[c.get("type")] = stated.get(c.get("type"), 0) + 1
        known |= {n.split("@", 1)[0] for n in story.truth} | {
            n.split("@", 1)[0] for snap in story.snapshots for n in snap["truth"]}
        for x in entries:
            evaluated[x.rule] = evaluated.get(x.rule, 0) + 1
            fact = x.meta.get("fact")
            if fact:                          # the fact this check compared: only that one counts as checked
                facts_seen.setdefault(x.rule, set()).add(fact)
                continue
            ev = by.get(x.subject)            # a check that names no fact: every fact its message stated
            if ev is not None and ev.extraction is not None:
                facts_seen.setdefault(x.rule, set()).update(c.get("type") for c in ev.extraction.claims)
            if x.status == "excepted" and x.meta.get("exception"):
                met[(x.rule, x.meta["exception"])] = met.get((x.rule, x.meta["exception"]), 0) + 1
    for ep in h.episodes.values():
        for st in ep.steps:
            surfaces_captured.update(c.surface for c in st.captures if c.status == "captured")

    verbs = {s.do for sc in contract.scenarios for s in sc.steps}
    gaps: list[dict[str, Any]] = []
    unknowable: list[dict[str, Any]] = []
    for rule in contract.rules:
        if rule.id in engine:
            continue
        if evaluated.get(rule.id, 0) == 0:
            gaps.append({"id": f"{rule.id}:rule", "kind": "rule_never_exercised", "rule": rule.id,
                         "why": f"{rule.id} is evaluated by the engine, but no message of any persona was evaluated "
                                f"under it in release {head}"})
            continue
        oracle_rule = (rule.check or {}).get("must") == "match_oracle" if isinstance(rule.check, dict) else False
        for f in _claim_facts(rule):
            if f in facts_seen.get(rule.id, set()):
                continue
            n = stated.get(f, 0)
            d = defs.get(f)
            if d is not None and getattr(d, "unit", None) in TEXT_UNITS and not getattr(d, "words", None):
                unknowable.append({"rule": rule.id, "fact": f,
                                   "reason": f"{f} is text with no word list: the extraction cannot state its value, so "
                                             f"{rule.id} cannot compare it ({'shown ' + str(n) + ' time(s)' if n else 'never shown'}); "
                                             "give the fact a word list"})
                continue
            if oracle_rule and f not in known:
                unknowable.append({"rule": rule.id, "fact": f,
                                   "reason": f"the oracle gave no true value for {f} in any story, so {rule.id} cannot "
                                             f"compare it ({'shown ' + str(n) + ' time(s)' if n else 'never shown'}); "
                                             "give the fact an oracle field, or the adapter a reading of it"})
                continue
            gaps.append({"id": f"{rule.id}:fact:{f}", "kind": "fact_never_checked", "rule": rule.id, "fact": f,
                         "stated": n,
                         "why": (f"{rule.id} checks {f}; it was shown {n} time(s) but never compared "
                                 + ("(on one surface only, or never twice in the same state)" if not oracle_rule
                                    else "(no claim of it could be checked against the oracle)")) if n else
                                f"{rule.id} checks {f}, but no message of any persona stated it"})
        for ex in rule.exceptions:
            if not met.get((rule.id, ex.id)):
                gaps.append({"id": f"{rule.id}:exception:{ex.id}", "kind": "exception_never_met", "rule": rule.id,
                             "exception": ex.id,
                             "why": f"{rule.id}'s exception {ex.id} never applied: its conditions "
                                    f"({', '.join(c.id for c in ex.conditions)}) never all held"})
    for s in contract.surfaces:
        if s.id not in surfaces_captured:
            reach = (f"its verb {s.reached_by} is in no scenario" if s.reached_by and s.reached_by not in verbs
                     else f"reached by {s.reached_by}" if s.reached_by else "no reached_by verb")
            gaps.append({"id": f"surface:{s.id}", "kind": "surface_never_reached", "surface": s.id,
                         "why": f"no persona's episode captured {s.id} ({reach})"})
    axes: dict[str, set] = {}
    for p in contract.personas:
        for k, v in (p.axes or {}).items():
            axes.setdefault(k, set()).add(str(v))
    return {"release": head, "personas": sorted(h.results), "gaps": gaps,
            "engine_gaps": [{"rule": k, "reason": v} for k, v in engine.items()] + unknowable,
            "evaluated": evaluated, "persona_axes": {k: sorted(v) for k, v in sorted(axes.items())}}


# ---------------------------------------------------------------- drafting

DRAFT_INSTRUCTIONS = """You extend a release auditor's test personas so that rules it already checks get exercised.

You receive the contract (its rules, facts, surfaces, the subject's context fields), its existing personas and
scenarios, and a list of coverage gaps: things no existing persona ever showed the auditor. Propose the FEWEST new
personas that close as many gaps as possible.

Each new persona must be like the existing ones: the same context fields (use only field names that appear in the
subject's context or in an existing persona's context), realistic values for this app (take product names, codes,
methods and places from the existing personas, the rules' text and the facts; never invent a code, product or
option that nothing in the contract names), and a short `role` saying what it exercises. Prefer joining an existing
scenario. Propose a new scenario only if no existing one can reach the gap, and build it only from step verbs the
existing scenarios use, with a `day0` and the same `at` format as theirs.

For every gap you cannot close with a persona the contract can express, say so in `not_closable` with the reason
(e.g. the store would need data the contract does not name). For each persona, list `needs`: anything about the
app's data the persona depends on (e.g. "the app has the discount code that rule X names").
"""

DRAFT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["personas", "not_closable"],
    "properties": {
        "personas": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "name", "role", "axes_json", "context_json", "joins_scenario", "new_scenario_json",
                         "closes", "needs"],
            "properties": {
                "id": {"type": "string"}, "name": {"type": "string"}, "role": {"type": "string"},
                "axes_json": {"type": "string"},          # JSON object: the persona's axes
                "context_json": {"type": "string"},       # JSON object: the persona's context
                "joins_scenario": {"type": "string"},     # an existing scenario id, or "" with new_scenario_json
                "new_scenario_json": {"type": "string"},  # "" or a JSON scenario {id, description, steps}
                "closes": {"type": "array", "items": {"type": "string"}},   # gap ids
                "needs": {"type": "array", "items": {"type": "string"}}}}},
        "not_closable": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["gap", "reason"],
            "properties": {"gap": {"type": "string"}, "reason": {"type": "string"}}}}},
}


def _contract_view(contract: Contract) -> dict:
    return {
        "rules": [{"id": r.id, "kind": r.kind, "text": r.text, "check": r.check, "applies_to": r.applies_to,
                   "exceptions": [{"id": e.id, "conditions": [c.model_dump(exclude_none=True) for c in e.conditions]}
                                  for e in r.exceptions]} for r in contract.rules],
        "facts": [f.id for f in contract.facts],
        "surfaces": [{"id": s.id, "kind": s.kind, "reached_by": s.reached_by} for s in contract.surfaces],
        "subject_context": [c.model_dump(exclude_none=True) for c in contract.subject.context]
        if contract.subject else [],
        "personas": [p.model_dump(exclude_none=True, exclude_defaults=True) for p in contract.personas],
        "scenarios": [s.model_dump(mode="json", exclude_none=True, exclude_defaults=True) for s in contract.scenarios],
    }


def check_draft(d: dict, contract: Contract, gap_ids: set[str]) -> list[str]:
    """What is wrong with one drafted persona against the contract; [] when it can be offered to the owner."""
    problems = []
    ids = {p.id for p in contract.personas}
    if d["id"] in ids:
        problems.append(f"id {d['id']} is an existing persona")
    try:
        ctx = json.loads(d["context_json"] or "{}")
        axes = json.loads(d["axes_json"] or "{}")
    except json.JSONDecodeError as e:
        return problems + [f"context or axes is not JSON: {e}"]
    known = {c.id for c in (contract.subject.context if contract.subject else [])} | \
        {k for p in contract.personas for k in (p.context or {})}
    unknown = sorted(set(ctx) - known)
    if unknown:
        problems.append(f"context fields the contract does not use: {', '.join(unknown)}")
    known_axes = {k for p in contract.personas for k in (p.axes or {})}
    if known_axes and set(axes) - known_axes:
        problems.append(f"axes the contract's personas do not use: {', '.join(sorted(set(axes) - known_axes))}")
    try:
        Persona(id=d["id"], name=d["name"], role=d["role"], axes=axes, context=ctx)
    except Exception as e:
        problems.append(f"not a valid persona: {str(e)[:200]}")
    verbs = {s.do for sc in contract.scenarios for s in sc.steps}
    scen_ids = {s.id for s in contract.scenarios}
    if d["joins_scenario"]:
        if d["joins_scenario"] not in scen_ids:
            problems.append(f"joins unknown scenario {d['joins_scenario']}")
    elif d["new_scenario_json"]:
        try:
            raw = json.loads(d["new_scenario_json"])
        except json.JSONDecodeError as e:
            return problems + [f"new scenario is not JSON: {e}"]
        bad = sorted({str(s.get("do")) for s in raw.get("steps") or [] if isinstance(s, dict)} - verbs)
        if bad:
            problems.append(f"step verbs the contract does not use: {', '.join(bad)}")
        if raw.get("id") in scen_ids:
            problems.append(f"new scenario id {raw.get('id')} already exists")
        try:
            Scenario(**{**raw, "personas": [d["id"]]})
        except Exception as e:
            problems.append(f"not a valid scenario: {str(e)[:200]}")
    else:
        problems.append("joins no scenario and proposes none")
    stray = sorted(set(d["closes"]) - gap_ids)
    if stray:
        problems.append(f"claims to close gaps that are not in the list: {', '.join(stray)}")
    if not d["closes"]:
        problems.append("closes no gap")
    return problems


def draft_personas(contract: Contract, cov: dict, router: Router, *, fresh: bool = False) -> dict:
    gaps = cov["gaps"]
    payload = {"contract": _contract_view(contract), "gaps": gaps}
    res = router.complete("interpreter", [{"role": "system", "content": DRAFT_INSTRUCTIONS},
                                          {"role": "user", "content": json.dumps(payload, ensure_ascii=False,
                                                                                 default=str)}],
                          schema=DRAFT_SCHEMA, schema_name="coverage_drafts", fresh=fresh)
    gap_ids = {g["id"] for g in gaps}
    drafts = []
    for d in res.parsed["personas"]:
        problems = check_draft(d, contract, gap_ids)
        drafts.append({"id": d["id"], "name": d["name"], "role": d["role"],
                       "axes": _loads(d["axes_json"]), "context": _loads(d["context_json"]),
                       "joins_scenario": d["joins_scenario"] or None,
                       "new_scenario": _loads(d["new_scenario_json"]) if not d["joins_scenario"] else None,
                       "closes": d["closes"], "needs": d["needs"],
                       "check": "ok" if not problems else "refused", "problems": problems})
    closed = {g for d in drafts if d["check"] == "ok" for g in d["closes"]}
    return {"status": "DRAFT: not part of the contract until the owner accepts it", "release": cov["release"],
            "drafts": drafts, "not_closable": res.parsed["not_closable"],
            "gaps_left_open": sorted(gap_ids - closed), "model": router.roles["interpreter"]["model"],
            "cost_usd": round((res.cost_usd or 0.0) + res.unreadable_cost_usd, 6) if not res.cached else 0.0}


def _loads(s: str):
    try:
        return json.loads(s) if s else None
    except json.JSONDecodeError:
        return s


def accept(drafts_path: Path, draft_id: str, contract_dir: Path) -> list[str]:
    """Add one checked draft to the contract, as text appended to personas.yaml and scenarios.yaml (the owner's
    comments and layout stay as they are). A draft that joins an existing scenario gets that scenario's steps as a
    scenario of its own (`<scenario>.<persona>`), so no existing scenario is edited. Returns what changed."""
    data = yaml.safe_load(drafts_path.read_text())
    d = next((x for x in data["drafts"] if x["id"] == draft_id), None)
    if d is None:
        raise ValueError(f"no draft {draft_id} in {drafts_path}")
    if d["check"] != "ok":
        raise ValueError(f"draft {draft_id} was refused by the check: {'; '.join(d['problems'])}")
    contract = load_contract(contract_dir)
    problems = check_draft({**d, "axes_json": json.dumps(d["axes"] or {}), "context_json": json.dumps(d["context"] or {}),
                            "joins_scenario": d["joins_scenario"] or "",
                            # default=str: YAML reads a hand-edited day0 as a datetime
                            "new_scenario_json": json.dumps(d["new_scenario"], default=str) if d["new_scenario"] else ""},
                           contract, set(d["closes"]))
    if problems:
        raise ValueError(f"draft {draft_id} no longer fits the contract: {'; '.join(problems)}")
    if d["joins_scenario"]:
        base = next(s for s in contract.scenarios if s.id == d["joins_scenario"])
        scenario = {**base.model_dump(mode="json", exclude_none=True, exclude_defaults=True),
                    "id": f"{base.id}.{d['id']}", "personas": [d["id"]],
                    "description": f"{base.description or base.id} (steps of {base.id}, for {d['id']})"}
    else:
        scenario = {**d["new_scenario"], "personas": [d["id"]]}
    note = f"# added by `semaudit coverage accept` from {drafts_path.name}: closes {', '.join(d['closes'])}\n"
    persona = {"id": d["id"], "name": d["name"], "role": d["role"], "axes": d["axes"] or {}, "context": d["context"] or {}}
    files = {"personas.yaml": persona, "scenarios.yaml": scenario}
    before = {f: (contract_dir / f).read_text() for f in files}
    try:
        for f, item in files.items():
            text = before[f] if before[f].endswith("\n") else before[f] + "\n"
            (contract_dir / f).write_text(text + note + yaml.safe_dump([item], sort_keys=False, allow_unicode=True))
        load_contract(contract_dir)                       # still a valid contract, or nothing changes
    except Exception:
        for f, text in before.items():
            (contract_dir / f).write_text(text)
        raise
    return [f"personas.yaml: + {d['id']}", f"scenarios.yaml: + {scenario['id']}"]
