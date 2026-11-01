"""Convert an agent finding into a check: a model drafts, a deterministic gate decides.

The model reads the finding's own reproduction text (as written; nothing is rewritten by hand) and drafts clauses,
steps, persona and invariant (prompts/convert.md). The gate then refuses, with a reason, anything it cannot verify:

  coverage    the clauses, in order, are verbatim pieces of the reproduce text and together cover every letter and
              digit of it, so no instruction can be dropped silently;
  verbs       every step uses a verb the adapter has AND the contract describes; a step either carries out an action
              clause or is a declared prerequisite (implied_ok) or a read verb reaching the invariant's surface;
  actions     every action clause is carried out by steps or named unmapped (no_verb with the verb it would need, or
              cannot_map); a "missing" verb that exists is refused;
  persona     only contract context fields, valid values (enums, list fields against the catalog); a material field
              comes from a clause or equals its declared default;
  invariant   a contract rule, a contract surface reached by a step, and a statement with none of the quote's figures.

If the draft fails the gate it is redrafted once with the gate's errors; if it still fails the import is
`not_converted`. Otherwise it is classified, fail-closed:
  adapter_gap          an action clause needs a verb the adapter does not have, or the surface is not one it reaches;
  partially_converted  an action clause could not be mapped, or an observation clause reads like a hidden action;
  converted            everything maps; the check is ready to replay (replayed / replay_failed after the replay).
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from semaudit.adapters.base import load_adapter
from semaudit.contract.schema import Contract
from semaudit.models.router import Router

from .record import Clause, Conversion, ImportedCheck, ImportSpec, Invariant, Source

ROLE = "importer"
PROMPT = Path(__file__).with_name("prompts") / "convert.md"


def prompt_sha() -> str:
    return hashlib.sha256(PROMPT.read_bytes()).hexdigest()[:16]


def adapter_verbs(contract: Contract, contract_dir: Path) -> set[str]:
    """The verbs the app adapter actually implements (its do_<verb> methods)."""
    a = load_adapter(contract.app.adapter, contract_dir)
    return {n[3:] for n in dir(a) if n.startswith("do_") and callable(getattr(a, n))}


def load_catalogs(spec: ImportSpec, contract_dir: Path) -> dict[str, list[dict]]:
    return {f: json.loads((Path(contract_dir) / lf.catalog).read_text()) for f, lf in spec.list_fields.items()}


# ---------- the draft ----------

def _schema() -> dict:
    s = lambda: {"type": "string"}  # noqa: E731
    clause = {"type": "object", "additionalProperties": False,
              "required": ["text", "kind", "steps", "sets", "unmapped_reason", "missing_verb", "why"],
              "properties": {"text": s(), "kind": {"type": "string",
                                                   "enum": ["action", "context", "observation", "alternative"]},
                             "steps": {"type": "array", "items": {"type": "integer"}},
                             "sets": {"type": "array", "items": s()},
                             "unmapped_reason": {"type": "string", "enum": ["", "no_verb", "cannot_map"]},
                             "missing_verb": s(), "why": s()}}
    step = {"type": "object", "additionalProperties": False, "required": ["do", "clause"],
            "properties": {"do": s(), "clause": {"type": "integer"}}}
    field = {"type": "object", "additionalProperties": False, "required": ["field", "value", "values", "clause"],
             "properties": {"field": s(), "value": s(), "values": {"type": "array", "items": s()},
                            "clause": {"type": "integer"}}}
    inv = {"type": "object", "additionalProperties": False,
           "required": ["rule", "surface", "missing_surface", "statement"],
           "properties": {"rule": s(), "surface": s(), "missing_surface": s(), "statement": s()}}
    return {"type": "object", "additionalProperties": False, "required": ["clauses", "steps", "persona", "invariant"],
            "properties": {"clauses": {"type": "array", "items": clause}, "steps": {"type": "array", "items": step},
                           "persona": {"type": "array", "items": field}, "invariant": inv}}


SCHEMA = _schema()


def payload(src: Source, spec: ImportSpec, contract: Contract, verbs: set[str],
            catalogs: dict[str, list[dict]]) -> dict[str, Any]:
    fields = []
    for f in contract.subject.context:
        if f.id in spec.unique_fields:
            continue
        row = {"id": f.id, "type": f.type, "required": f.required}
        if f.values:
            row["values"] = f.values
        fields.append(row)
    lists = {}
    for name, lf in spec.list_fields.items():
        keep = [lf.key_attr] + ([lf.members_attr] if lf.members_attr else []) + lf.show_attrs
        lists[name] = {"format": lf.pattern, "catalog": [{k: e.get(k) for k in keep} for e in catalogs[name]]}
    aliases: dict[str, list[str]] = {}
    for a, r in spec.rule_aliases.items():
        aliases.setdefault(r, []).append(a)
    return {
        "finding": {k: getattr(src, k) for k in ("claim", "where", "shown", "should_be", "reproduce", "rule")},
        "verbs": {v: d for v, d in spec.verbs.items() if v in verbs},
        "implied_ok": spec.implied_ok, "read_verbs": spec.read_verbs,
        "persona_fields": fields, "list_fields": lists, "persona_defaults": spec.persona_defaults,
        "rules": [{"id": r.id, "aliases": aliases.get(r.id, []), "title": r.title, "text": r.text}
                  for r in contract.rules],
        "surfaces": [{"id": s.id, "kind": s.kind, "reached_by": s.reached_by} for s in contract.surfaces],
    }


def draft(router: Router, body: dict, *, previous: dict | None = None, errors: list[str] | None = None,
          fresh: bool = False):
    msgs = [{"role": "system", "content": PROMPT.read_text()},
            {"role": "user", "content": json.dumps(body, ensure_ascii=False)}]
    if previous is not None:
        msgs += [{"role": "assistant", "content": json.dumps(previous, ensure_ascii=False)},
                 {"role": "user", "content": "The checker refused this draft:\n- " + "\n- ".join(errors or [])
                  + "\nReturn a corrected, complete draft. Do not drop instructions to make it pass: an action "
                    "no verb does stays an unmapped action clause."}]
    return router.complete(ROLE, msgs, schema=SCHEMA, schema_name="draft", fresh=fresh)


# ---------- the gate ----------

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def coverage_errors(reproduce: str, clauses: list[dict]) -> list[str]:
    """Clauses must be verbatim, in order, non-overlapping pieces of `reproduce` that together hold every letter
    and digit of it (whitespace and punctuation between clauses are free)."""
    text = _norm(reproduce)
    if not text:
        return ["the finding has no reproduction text"]
    errs, pos, covered = [], 0, [False] * len(text)
    for i, c in enumerate(clauses):
        piece = _norm(c.get("text", ""))
        if not piece:
            errs.append(f"clause {i} is empty")
            continue
        at = text.find(piece, pos)
        if at < 0:
            where = "earlier in the text (out of order or overlapping)" if piece in text else "nowhere in the text"
            errs.append(f"clause {i} is not a verbatim piece of the reproduce text after clause {i - 1}: found "
                        f"{where}: {piece[:80]!r}")
            continue
        for k in range(at, at + len(piece)):
            covered[k] = True
        pos = at + len(piece)
    missing = "".join(ch if not covered[k] and ch.isalnum() else " " for k, ch in enumerate(text))
    left = [w for w in missing.split() if w]
    if left and not errs:
        errs.append(f"the clauses leave out part of the reproduce text: {' '.join(left)[:200]!r}")
    return errs


def _figures(s: str) -> set[str]:
    return {m.group().replace(",", "") for m in re.finditer(r"\d[\d,]*\.\d+|\d{2,}[\d,]*", s or "")}


def gate(d: dict, src: Source, spec: ImportSpec, contract: Contract, verbs: set[str],
         catalogs: dict[str, list[dict]]) -> list[str]:
    errs = coverage_errors(src.reproduce, d.get("clauses", []))
    clauses, steps = d.get("clauses", []), d.get("steps", [])
    usable = {v for v in spec.verbs if v in verbs}
    inv = d.get("invariant") or {}
    surfaces = {s.id: s for s in contract.surfaces}
    rule = spec.rule_aliases.get(inv.get("rule", ""), inv.get("rule", ""))
    inv_surface = surfaces.get(inv.get("surface", ""))
    for k, st in enumerate(steps):
        do, ci = st.get("do"), st.get("clause")
        if do not in usable:
            errs.append(f"step {k}: verb {do!r} is not a verb the adapter has" if do not in verbs else
                        f"step {k}: verb {do!r} is not described in imports.yaml")
            continue
        if ci == -1:
            reach = inv_surface is not None and (inv_surface.reached_by == do
                                                 or inv_surface.id in spec.read_verbs.get(do, []))
            if do not in spec.implied_ok and not (do in spec.read_verbs and reach):
                errs.append(f"step {k} ({do}) carries out no clause and is not a declared prerequisite"
                            + (" or a read verb reaching the invariant's surface" if do in spec.read_verbs else ""))
        elif not (isinstance(ci, int) and 0 <= ci < len(clauses)):
            errs.append(f"step {k} ({do}) cites clause {ci}, which does not exist")
        elif clauses[ci].get("kind") != "action" or k not in clauses[ci].get("steps", []):
            errs.append(f"step {k} ({do}) cites clause {ci}, which is not an action clause listing it")
        elif do not in spec.implied_ok and not cue_matches(spec, do, clauses[ci].get("text", ""), catalogs):
            errs.append(f"step {k} ({do}) cites clause {ci} ({clauses[ci].get('text','')[:60]!r}), whose words do "
                        f"not describe {do}; an action no verb does is an unmapped clause, not another verb")
        need = (spec.verb_args.get(do or "", {}) or {}).get("from_persona")
        for f in ([need] if isinstance(need, str) else need or []):
            if f not in spec.unique_fields and f not in _persona_fields(d) and f not in spec.persona_defaults:
                errs.append(f"step {k} ({do}) needs persona field {f!r}, which the draft does not set")
    for i, c in enumerate(clauses):
        kind, mapped = c.get("kind"), c.get("steps", [])
        reason, missing = c.get("unmapped_reason", ""), c.get("missing_verb", "")
        if kind == "action":
            if mapped and reason:
                errs.append(f"clause {i} is both mapped to steps and marked unmapped")
            if not mapped and not reason:
                errs.append(f"action clause {i} has no steps and no unmapped reason: {c.get('text','')[:60]!r}")
            for k in mapped:
                if not (0 <= k < len(steps)) or steps[k].get("clause") != i:
                    errs.append(f"clause {i} lists step {k}, which does not cite it back")
            if reason == "no_verb" and not missing:
                errs.append(f"clause {i} is unmapped for want of a verb but names none")
            if reason == "no_verb" and missing in verbs:
                errs.append(f"clause {i} says verb {missing!r} is missing, but the adapter has it")
        elif mapped or reason:
            errs.append(f"clause {i} is {kind}, so it cannot carry steps or an unmapped reason")
    errs += _persona_errors(d, spec, contract, catalogs, len(clauses), src.where)
    if rule not in {r.id for r in contract.rules}:
        errs.append(f"invariant rule {inv.get('rule')!r} is not a contract rule")
    if inv.get("surface"):
        if inv_surface is None:
            errs.append(f"invariant surface {inv.get('surface')!r} is not a contract surface")
        elif not reached(inv_surface, {s.get("do") for s in steps}, spec):
            errs.append(f"invariant surface {inv_surface.id} is reached by {inv_surface.reached_by}, which no step does")
    elif not inv.get("missing_surface"):
        errs.append("the invariant names no surface and does not describe the missing one")
    if not errs:                                       # what the replay would actually type and choose
        persona, _, _ = build("gate", d, spec, contract)
        for f in contract.subject.context:
            if f.required and persona["context"].get(f.id) in (None, "", []):
                errs.append(f"persona field {f.id!r} is required and neither the finding nor a default gives it")
    if not _norm(inv.get("statement", "")):
        errs.append("the invariant has no statement")
    copied = _figures(inv.get("statement", "")) & _figures(src.shown)
    if copied:
        errs.append(f"the invariant statement copies figures from the quote ({', '.join(sorted(copied))}); state "
                    "the property, not the old values")
    return errs


def reached(surface, verbs_done: set[str], spec: ImportSpec) -> bool:
    return surface.reached_by in verbs_done or any(surface.id in spec.read_verbs.get(v, []) for v in verbs_done)


def cue_matches(spec: ImportSpec, verb: str, text: str, catalogs: dict[str, list[dict]]) -> bool:
    """Does the clause's own wording describe this verb? A verb with no declared cue never matches (fail closed)."""
    cue = spec.verb_cues.get(verb)
    if not cue:
        return False
    if "{catalog}" in cue:
        names = [str(e.get(a) or "") for name, lf in spec.list_fields.items() for e in catalogs.get(name, [])
                 for a in [lf.key_attr, *lf.show_attrs[:1]]]
        low = text.lower()
        if any(n and n.lower() in low for n in names):
            return True
        cue = cue.replace("{catalog}", "(?!x)x")
    return re.search(cue, text, re.I) is not None


def _persona_fields(d: dict) -> set[str]:
    return {p.get("field") for p in d.get("persona", [])}


def _persona_errors(d: dict, spec: ImportSpec, contract: Contract, catalogs: dict, n_clauses: int,
                    src_where: str = "") -> list[str]:
    errs = []
    sub = {f.id: f for f in contract.subject.context}
    clauses = d.get("clauses", [])
    for p in d.get("persona", []):
        fid, ci = p.get("field"), p.get("clause")
        f = sub.get(fid)
        if f is None:
            errs.append(f"persona field {fid!r} is not a contract context field")
            continue
        if fid in spec.unique_fields:
            errs.append(f"persona field {fid!r} is set by the importer, not the draft")
            continue
        if ci == -2:                                   # from the finding's own `where` text
            if not _norm(src_where):
                errs.append(f"persona field {fid!r} cites the finding's `where`, which is empty")
        elif ci != -1 and not (isinstance(ci, int) and 0 <= ci < n_clauses):
            errs.append(f"persona field {fid!r} cites clause {ci}, which does not exist")
        elif ci != -1 and fid not in clauses[ci].get("sets", []) and clauses[ci].get("kind") != "action":
            errs.append(f"persona field {fid!r} cites clause {ci}, which does not list it in `sets`")
        if ci == -1 and fid in spec.material_fields and _value(p, f) != spec.persona_defaults.get(fid):
            errs.append(f"material field {fid!r} = {_value(p, f)!r} comes from no clause and is not its default")
        if f.type == "list":
            lf = spec.list_fields.get(fid)
            for v in p.get("values", []):
                errs += _list_value_errors(fid, v, lf, catalogs.get(fid, []))
        elif f.type == "enum" and p.get("value") not in f.values:
            errs.append(f"persona field {fid!r} = {p.get('value')!r} is not one of {f.values}")
    for c in clauses:
        for fid in c.get("sets", []):
            if fid not in _persona_fields(d):
                errs.append(f"a context clause sets {fid!r} but the persona has no value for it")
    return errs


def _list_value_errors(fid: str, v: str, lf, catalog: list[dict]) -> list[str]:
    if lf is None:
        return []
    m = re.fullmatch(lf.pattern, v or "")
    if not m:
        return [f"persona field {fid!r}: {v!r} does not match {lf.pattern}"]
    entry = next((e for e in catalog if str(e.get(lf.key_attr)) == m.group(lf.key_group)), None)
    if entry is None:
        return [f"persona field {fid!r}: {m.group(lf.key_group)!r} is not in the catalog"]
    if lf.member_group and m.group(lf.member_group) and m.group(lf.member_group) not in (entry.get(lf.members_attr)
                                                                                           or []):
        return [f"persona field {fid!r}: {m.group(lf.member_group)!r} is not an option of "
                f"{m.group(lf.key_group)!r} ({entry.get(lf.members_attr)})"]
    return []


def _value(p: dict, f) -> Any:
    if f.type == "list":
        return list(p.get("values", []))
    v = p.get("value")
    if f.type == "int":
        return int(v)
    if f.type == "float":
        return float(v)
    if f.type == "bool":
        return str(v).lower() in ("1", "true", "yes")
    return None if v in ("", "null", None) else v


# ---------- building and classifying ----------

def suspect_observations(clauses: list[dict], spec: ImportSpec) -> list[str]:
    """Observation / context clauses that read like an action of the tester's (fail closed: partially_converted)."""
    out = []
    for c in clauses:
        if c.get("kind") in ("observation", "context"):
            for w in spec.action_words:
                if re.search(w, c.get("text", ""), re.I):
                    out.append(f"{c['kind']} clause reads like an action ({w}): {c['text'][:90]!r}")
                    break
    return out


def classify(d: dict, spec: ImportSpec, contract: Contract, verbs: set[str]) -> tuple[str, Conversion]:
    clauses = d.get("clauses", [])
    conv = Conversion(status="converted")
    for c in clauses:
        if c.get("kind") == "action" and c.get("unmapped_reason"):
            conv.unmapped.append(c["text"])
            if c["unmapped_reason"] == "no_verb":
                conv.gaps.append(c["missing_verb"])
                conv.reasons.append(f"needs verb {c['missing_verb']!r}: {c['text'][:90]!r}")
            else:
                conv.reasons.append(f"could not map: {c['text'][:90]!r} ({c.get('why','')[:120]})")
        if c.get("kind") == "alternative":
            conv.alternatives.append(c["text"])
    inv = d.get("invariant") or {}
    if not inv.get("surface"):
        conv.gaps.append(f"surface: {inv.get('missing_surface','')}")
        conv.reasons.append(f"the cited surface is not one the harness reaches: {inv.get('missing_surface','')!r}")
    sus = suspect_observations(clauses, spec)
    conv.reasons += sus
    if not any(c.get("kind") == "action" and c.get("steps") for c in clauses):
        conv.reasons.append("no action clause is carried out by any step")
    full, inserted, missing = with_prerequisites(d.get("steps", []), spec)
    conv.reasons += missing
    if conv.gaps:
        conv.status = "adapter_gap"
    elif conv.reasons:
        conv.status = "partially_converted"
    conv.implied_steps = [s["do"] for s in full if s.get("clause") == -1]
    return conv.status, conv


def with_prerequisites(steps: list[dict], spec: ImportSpec) -> tuple[list[dict], list[str], list[str]]:
    """Insert each step's declared prerequisites that have not happened yet, when they are implied_ok (a verb the
    finding may leave unsaid). Returns (steps, inserted verbs, missing non-implied prerequisites)."""
    out, inserted, missing, done = [], [], [], set()
    for st in steps:
        for pre in spec.prerequisites.get(st["do"], []):
            if pre in done:
                continue
            if pre in spec.implied_ok:
                out.append({"do": pre, "clause": -1})
                inserted.append(pre)
                done.add(pre)
            else:
                missing.append(f"{st['do']} needs {pre} before it, which the finding does not do")
        out.append(st)
        done.add(st["do"])
    return out, inserted, sorted(set(missing))


def build(check_id: str, d: dict, spec: ImportSpec, contract: Contract) -> tuple[dict, dict, list[str]]:
    """The persona and scenario the replay runs, and which persona fields came from defaults."""
    sub = {f.id: f for f in contract.subject.context}
    given = {p["field"]: (p, sub[p["field"]]) for p in d.get("persona", []) if p.get("field") in sub}
    ctx: dict[str, Any] = dict(spec.persona_defaults)
    defaulted = sorted(k for k in spec.persona_defaults if k not in given or given[k][0].get("clause") == -1)
    place = given.get(spec.place_field or "")
    if place is not None:
        pd = spec.place_defaults.get(str(_value(*place)), {})
        for k, v in pd.items():
            if k not in given:
                ctx[k] = v
                defaulted.append(k)
    for fid, (p, f) in given.items():
        ctx[fid] = _value(p, f)
    for fid, tmpl in spec.unique_fields.items():
        ctx[fid] = tmpl.format(id=check_id.lower())
    pid = f"ic_{check_id.lower()}"
    persona = {"id": pid, "name": str(ctx.get("name") or pid), "role": "imported", "context": ctx}
    steps = []
    for k, st in enumerate(with_prerequisites(d.get("steps", []), spec)[0]):
        h, m = divmod(10 * 60 + k, 60)
        steps.append({"at": f"D0 {h:02d}:{m:02d}", "do": st["do"],
                      "params": copy.deepcopy(spec.verb_args.get(st["do"], {}))})
    scenario = {"id": f"IC-{check_id}", "description": f"imported check {check_id}", "day0": spec.day0,
                "personas": [pid], "steps": steps}
    return persona, scenario, sorted(set(defaulted))


def convert(check_id: str, src: Source, contract: Contract, contract_dir: Path, spec: ImportSpec, router: Router,
            *, fresh: bool = False, max_rounds: int = 2, converter: dict | None = None) -> ImportedCheck:
    verbs = adapter_verbs(contract, contract_dir)
    catalogs = load_catalogs(spec, contract_dir)
    body = payload(src, spec, contract, verbs, catalogs)
    spent, model, errors_by_round, d = 0.0, None, [], None
    errs: list[str] = []
    for rnd in range(max_rounds):
        r = draft(router, body, previous=d if rnd else None, errors=errs if rnd else None, fresh=fresh)
        spent += 0.0 if r.cached else (r.cost_usd or 0.0)
        model, d = r.model, r.parsed or {}
        errs = gate(d, src, spec, contract, verbs, catalogs)
        errors_by_round.append(errs)
        if not errs:
            break
    meta = dict(converter or {}, prompt_sha=prompt_sha())
    if errs:
        conv = Conversion(status="not_converted", reasons=errs, gate_rounds=len(errors_by_round),
                          gate_errors=errors_by_round, model=model, cost_usd=round(spent, 6))
        return ImportedCheck(id=check_id, source=src, conversion=conv, converter=meta,
                             clauses=[Clause(**_clause(c)) for c in d.get("clauses", []) if _clause(c)])
    _, conv = classify(d, spec, contract, verbs)
    conv.gate_rounds, conv.gate_errors, conv.model, conv.cost_usd = len(errors_by_round), errors_by_round, model, \
        round(spent, 6)
    persona, scenario, conv.defaulted = build(check_id, d, spec, contract)
    inv = d["invariant"]
    invariant = Invariant(rule=spec.rule_aliases.get(inv["rule"], inv["rule"]), surface=inv["surface"],
                          statement=_norm(inv["statement"]))
    return ImportedCheck(id=check_id, source=src, clauses=[Clause(**_clause(c)) for c in d["clauses"]],
                         persona=persona, scenario=scenario, invariant=invariant, conversion=conv, converter=meta)


def _clause(c: dict) -> dict:
    if not isinstance(c, dict) or "text" not in c or c.get("kind") not in ("action", "context", "observation",
                                                                          "alternative"):
        return {}
    un = None
    if c.get("unmapped_reason"):
        un = {"reason": c["unmapped_reason"], "missing_verb": c.get("missing_verb") or None, "why": c.get("why", "")}
    return {"text": c["text"], "kind": c["kind"], "steps": list(c.get("steps", [])), "sets": list(c.get("sets", [])),
            "unmapped": un}
