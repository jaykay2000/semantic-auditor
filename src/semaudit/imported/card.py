"""One static HTML page of imported-check cards (`semaudit checks card`), built only from stored records:

  (a) the agent's finding as written (kept as evidence only)        <- checks/<id>.yaml `source`
  (b) the converted journey (steps -> adapter verbs) and the kept rule / invariant, with the model that drafted it
  (c) the four statuses per release: replay, assertion, semantic confidence, evidence verification
  (d) base vs head: the memory outcome
  (e) for a check that did not convert: the gap card (what could not be mapped, and the verb it would need)

(c) and (d) come from a saved-checks run (`saved.py`) or recheck result files; nothing is recomputed here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from semaudit.contract.schema import load_contract

from .record import ImportedCheck

TEMPLATES = Path(__file__).resolve().parents[1] / "report" / "templates"


def _figures(result: dict) -> list[dict]:
    """The quotes the majority judgments cited (verified against the capture), de-duplicated, in order."""
    seen, out = set(), []
    outcome = result["assertion"].get("majority") or result["assertion"]["outcome"]
    for j in result.get("judgments", []):
        if j["outcome"] != outcome:
            continue
        for c in j.get("cited", []):
            if c["quote"] not in seen:
                seen.add(c["quote"])
                out.append(c)
    return out


def step_sources(check: ImportedCheck, contract_dir: Path) -> list[str | None]:
    """The clause text each scenario step carries out (None: an implied prerequisite). The record keeps the
    scenario the importer built, in which declared prerequisites may have been inserted, while clauses cite the
    draft's step indexes; the draft is recovered as the scenario minus the inserted steps, choosing (among the
    removals that `with_prerequisites` maps back to exactly this scenario) the one whose cited steps best match their
    clause's wording."""
    from itertools import combinations

    from .convert import cue_matches, load_catalogs, with_prerequisites
    from .record import load_spec
    spec = load_spec(contract_dir)
    cats = load_catalogs(spec, contract_dir)
    scen = [s["do"] for s in check.scenario.get("steps", [])]
    implied_pos = [k for k, v in enumerate(scen) if v in spec.implied_ok]
    best, best_score = None, -1
    for n in range(len(implied_pos) + 1):
        for drop in combinations(implied_pos, n):
            keep = [k for k in range(len(scen)) if k not in drop]
            cited = {k: c.text for c in check.clauses for k in c.steps}
            if any(k >= len(keep) for k in cited):
                continue
            draft = [{"do": scen[k], "clause": 0 if j in cited else -1} for j, k in enumerate(keep)]
            if [x["do"] for x in with_prerequisites(draft, spec)[0]] != scen:
                continue
            score = sum(cue_matches(spec, scen[keep[j]], t, cats) for j, t in cited.items())
            if score > best_score:
                best, best_score = (keep, cited), score
    out: list[str | None] = [None] * len(scen)
    if best:
        keep, cited = best
        for j, k in enumerate(keep):
            out[k] = cited.get(j)
    return out


def card_data(check: ImportedCheck, contract_dir: Path, results: dict[str, dict] | None = None,
              memory_outcome: dict | None = None, base: str | None = None, head: str | None = None) -> dict:
    contract = load_contract(contract_dir)
    clauses = [c.model_dump() for c in check.clauses]
    sources = step_sources(check, contract_dir)
    steps = [{"n": k + 1, "do": st["do"], "params": st.get("params") or {}, "from": sources[k]}
             for k, st in enumerate(check.scenario.get("steps", []))]
    rule = None
    if check.invariant:
        r = contract.rule(check.invariant.rule)
        rule = {"id": r.id, "title": r.title, "text": r.text}
    rows = []
    for rel in [x for x in (base, head) if x] or list((results or {}).keys()):
        r = (results or {}).get(rel)
        if r:
            rows.append({"release": rel, "r": r, "figures": _figures(r)})
    return {"check": check.model_dump(mode="json"), "clauses": clauses, "steps": steps, "rule": rule,
            "persona": {k: v for k, v in (check.persona.get("context") or {}).items()
                        if k not in ("component",) and v not in (None, "", [])},
            "rows": rows, "memory": memory_outcome, "base": base, "head": head}


def render(cards: list[dict], out: Path, *, title: str, label: str | None = None) -> Path:
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
    html = env.get_template("imported_checks.html").render(cards=cards, title=title, label=label)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    return out


def from_saved_run(saved: Path, contract_dir: Path) -> list[dict]:
    run = json.loads(Path(saved).read_text())
    out = []
    for row in run["checks"]:
        chk = ImportedCheck.read(Path(contract_dir) / "checks" / f"{row['id']}.yaml")
        d = card_data(chk, contract_dir, row["results"], row["memory"], run["base"], run["head"])
        d["run"] = {"id": run["run"], "at": run["at"], "loaded": run["loaded_from_storage"],
                    "approved_digest": row["approved_digest"], "approved_by": row["approved_by"]}
        out.append(d)
    return out
