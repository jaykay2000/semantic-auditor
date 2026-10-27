"""Blind adjudication sheets, applying verdicts, and agreement (docs/08-evaluation.md, "Ground truth and adjudication").

Every finding from every system, plus every seeded SUBJECTIVE item, becomes one row in ONE neutral template: no
system name, no confidence, no severity, no system wording. Evidence is the verbatim text of the captured events
the row is about: the union of every source's citations, sorted (so no system's choice of evidence wins), or,
for a seeded item no system raised, the captured events its target names. Rows are shuffled with a recorded
seed; the key (row -> sources) is a separate file the adjudicators never see. Objective kinds are decided by the
oracle and never appear.

`apply_verdicts` turns one adjudicator's verdicts into the truth every system is then rescored against:
  seeded item judged not_real  -> that persona's unit leaves the denominator
  seeded item judged real      -> stays; label_if_real, when given, replaces the seeded label
  unseeded finding judged real -> a new issue unit, in EVERY system's denominator
  unsure                       -> recorded; a seeded hypothesis stands, an unseeded finding is not added
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
from pathlib import Path
from typing import Any

from .findings import Findings, Target, Truth, TruthItem

VERDICTS = ("real", "not_real", "unsure")
COLUMNS = ("row", "persona", "rule", "rule_text", "about", "label", "evidence", "verdict", "label_if_real", "note")
SHOWN = ("persona", "rule", "rule_text", "about", "label", "evidence")
MAX_EVIDENCE = 8


def _about(target: Target) -> str:
    if target.kind == "relation":
        return f"{target.features[0]} and {target.features[1]} on {target.decision}"
    if target.kind == "event":
        return f"{target.feature} on {target.surface}: {target.message_key}"
    return "the whole experience"


def persona_events(review: dict) -> dict[str, list[dict]]:
    """The captured stories as the adjudicator sees them: persona -> message events (time, feature, text)."""
    return {p["id"]: [e for e in p.get("events", []) if e.get("kind") == "message"] for p in review.get("personas", [])}


def _target_texts(events: list[dict], targets: list[Target]) -> list[str]:
    out = []
    for t in targets:
        for e in events:
            hit = (t.kind == "event" and (e.get("feature"), e.get("surface"), e.get("message_key")) ==
                   (t.feature, t.surface, t.message_key)) or \
                  (t.kind == "relation" and e.get("feature") in t.features) or t.kind == "story"
            if hit and e.get("text"):
                out.append(f'{e["at"]} {e.get("feature")}: {e["text"]}')
    return out


def build(systems: list[Findings], truth: Truth, rules: dict[str, str], *, seed: int,
          events: dict[str, list[dict]], objective_rules: set[str]) -> tuple[list[dict], list[dict]]:
    """Returns (sheet rows, key rows). One row per (persona, rule, target, label); identical rows from several
    systems are merged, so an adjudicator cannot tell how many systems raised it."""
    by_event = {(p, e["id"]): e for p, es in events.items() for e in es}
    merged: dict[tuple, dict[str, Any]] = {}

    def row(p, rule, target, label):
        return merged.setdefault((p, rule, target.key(), label), {
            "persona": p, "rule": rule, "rule_text": rules.get(rule, ""), "about": _about(target),
            "label": (label or "").replace("_", " "), "texts": set(), "sources": [],
            "target": target.model_dump(), "raw_label": label})

    for fs in systems:
        for f in fs.findings:
            if f.rule in objective_rules:
                continue
            for p in f.personas:
                r = row(p, f.rule, f.target, f.label)
                for c in f.cited:
                    e = by_event.get((c.persona, c.event_id)) if c.persona == p else None
                    if e and e.get("text"):
                        r["texts"].add(f'{e["at"]} {e.get("feature")}: {e["text"]}')
                r["sources"].append({"system": fs.system, "run": fs.run, "finding": f.id})
    for i in truth.items:
        if i.kind != "issue" or i.objective:
            continue
        for p in i.personas:
            r = row(p, i.rule, i.target, i.label)
            r["sources"].append({"system": "seeded", "finding": i.id})
    for (p, *_), r in merged.items():
        if not r["texts"]:
            r["texts"] = set(_target_texts(events.get(p, []), [Target.model_validate(r["target"])]))
    rows = sorted(merged.values(), key=lambda r: json.dumps([r["persona"], r["rule"], r["about"], r["label"]]))
    random.Random(seed).shuffle(rows)
    sheet, key = [], []
    for n, r in enumerate(rows, 1):
        ev = sorted(r["texts"])
        r["evidence"] = " | ".join(ev[:MAX_EVIDENCE]) + (f" | (+{len(ev) - MAX_EVIDENCE} more)" if len(ev) > MAX_EVIDENCE else "")
        sheet.append({"row": n, **{c: r[c] for c in SHOWN}, "verdict": "", "label_if_real": "", "note": ""})
        key.append({"row": n, "persona": r["persona"], "rule": r["rule"], "label": r["raw_label"],
                    "target": r["target"], "sources": r["sources"]})
    return sheet, key


def write(sheet: list[dict], key: list[dict], out_dir: Path, *, seed: int) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "sheet.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(sheet)
    (out_dir / "key.json").write_text(json.dumps({"seed": seed, "rows": key}, indent=1) + "\n")
    return {n: hashlib.sha256((out_dir / n).read_bytes()).hexdigest() for n in ("sheet.csv", "key.json")}


def read_verdicts(path: Path) -> dict[int, dict[str, str]]:
    with path.open() as fh:
        rows = {int(r["row"]): r for r in csv.DictReader(fh)}
    for n, r in rows.items():
        if r["verdict"] and r["verdict"] not in VERDICTS:
            raise ValueError(f"row {n}: verdict {r['verdict']!r} is not one of {VERDICTS}")
    return rows


def apply_verdicts(truth: Truth, key: list[dict], verdicts: dict[int, dict[str, str]],
                   *, adjudicator: str) -> tuple[Truth, dict[str, Any]]:
    """The adjudicated truth, and a record of what changed. Rows left blank change nothing and are counted."""
    items = [i.model_copy(deep=True) for i in truth.items]
    by_id = {i.id: i for i in items}
    log = {"adjudicator": adjudicator, "removed": [], "relabelled": [], "added": [], "unsure": [], "blank": []}
    for k in key:
        v = verdicts.get(k["row"], {})
        verdict, new_label = (v.get("verdict") or "").strip(), (v.get("label_if_real") or "").strip() or None
        seeded = [s["finding"] for s in k["sources"] if s["system"] == "seeded"]
        if not verdict:
            log["blank"].append(k["row"])
        elif verdict == "unsure":
            log["unsure"].append(k["row"])
        elif seeded:
            item = by_id[seeded[0]]
            if verdict == "not_real":
                item.personas = [p for p in item.personas if p != k["persona"]]
                log["removed"].append([item.id, k["persona"]])
            elif new_label and new_label != item.label:
                if len(item.personas) > 1:          # relabel only this persona's unit
                    item.personas = [p for p in item.personas if p != k["persona"]]
                    clone = item.model_copy(update={"id": f"{item.id}@{k['persona']}", "personas": [k["persona"]],
                                                    "label": new_label})
                    items.append(clone)
                    by_id[clone.id] = clone
                else:
                    item.label = new_label
                log["relabelled"].append([item.id, k["persona"], new_label])
        elif verdict == "real":
            n = len(log["added"]) + 1
            items.append(TruthItem(id=f"ADJ-{n:03d}", kind="issue", personas=[k["persona"]], rule=k["rule"],
                                   label=new_label or k["label"], target=Target.model_validate(k["target"]),
                                   pattern="unseeded"))
            log["added"].append([f"ADJ-{n:03d}", k["persona"], k["rule"]])
    items = [i for i in items if i.personas]
    out = truth.model_copy(update={"items": items, "source": f"{truth.source}; adjudicated by {adjudicator}"})
    return out, log


def kappa(a: list[str], b: list[str]) -> float | None:
    """Cohen's kappa for two adjudicators' verdicts on the same rows (rows either left blank are dropped)."""
    pairs = [(x, y) for x, y in zip(a, b) if x and y]
    if not pairs:
        return None
    n = len(pairs)
    po = sum(x == y for x, y in pairs) / n
    cats = sorted({x for x, _ in pairs} | {y for _, y in pairs})
    pe = sum((sum(x == c for x, _ in pairs) / n) * (sum(y == c for _, y in pairs) / n) for c in cats)
    return round((po - pe) / (1 - pe), 4) if pe < 1 else 1.0
