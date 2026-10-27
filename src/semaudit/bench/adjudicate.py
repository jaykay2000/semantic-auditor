"""Blind adjudication sheets and agreement (docs/08-evaluation.md, "Ground truth and adjudication").

Every finding from every system, plus every seeded subjective item, becomes one row in ONE neutral template:
no system name, no confidence, no severity, no system-specific wording beyond the cited evidence. Rows are
shuffled with a recorded seed. The key (row -> system and finding) is written to a separate file that the
adjudicators never see. Objective kinds are not adjudicated: the oracle decides them.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
from pathlib import Path
from typing import Any

from .findings import Findings, Truth

VERDICTS = ("real", "not_real", "unsure")
COLUMNS = ("row", "persona", "rule", "rule_text", "about", "label", "evidence", "verdict", "label_if_real", "note")


def _about(target) -> str:
    if target.kind == "relation":
        return f"{target.features[0]} and {target.features[1]} on {target.decision}"
    if target.kind == "event":
        return f"{target.feature}: {target.message_key}"
    return "the whole experience"


def build(systems: list[Findings], truth: Truth, rules: dict[str, str], *, seed: int,
          evidence: dict[tuple[str, str], str], objective_rules: set[str]) -> tuple[list[dict], list[dict]]:
    """Returns (sheet rows, key rows). One row per (finding, persona); identical rows from several systems are
    merged, so an adjudicator cannot tell how many systems raised a finding."""
    merged: dict[tuple, dict[str, Any]] = {}
    for fs in systems:
        for f in fs.findings:
            if f.rule in objective_rules:
                continue
            for p in f.personas:
                k = (p, f.rule, f.target.key(), f.label)
                cites = [c for c in f.cited if c.persona == p]
                row = merged.setdefault(k, {"persona": p, "rule": f.rule, "rule_text": rules.get(f.rule, ""),
                                            "about": _about(f.target), "label": (f.label or "").replace("_", " "),
                                            "evidence": " | ".join(evidence.get((p, c.event_id), "") for c in cites),
                                            "sources": []})
                row["sources"].append({"system": fs.system, "run": fs.run, "finding": f.id})
    for i in truth.items:
        if i.kind != "issue" or i.objective:
            continue
        for p in i.personas:
            k = (p, i.rule, i.target.key(), i.label)
            row = merged.setdefault(k, {"persona": p, "rule": i.rule, "rule_text": rules.get(i.rule, ""),
                                        "about": _about(i.target), "label": (i.label or "").replace("_", " "),
                                        "evidence": "", "sources": []})
            row["sources"].append({"system": "seeded", "finding": i.id})
    rows = sorted(merged.values(), key=lambda r: json.dumps([r["persona"], r["rule"], r["about"], r["label"]]))
    random.Random(seed).shuffle(rows)
    sheet, key = [], []
    for n, r in enumerate(rows, 1):
        sheet.append({"row": n, **{c: r.get(c, "") for c in COLUMNS[1:6]}, "verdict": "", "label_if_real": "",
                      "note": ""})
        key.append({"row": n, "sources": r["sources"]})
    return sheet, key


def write(sheet: list[dict], key: list[dict], out_dir: Path, *, seed: int) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "sheet.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(sheet)
    (out_dir / "key.json").write_text(json.dumps({"seed": seed, "rows": key}, indent=1) + "\n")
    return {n: hashlib.sha256((out_dir / n).read_bytes()).hexdigest() for n in ("sheet.csv", "key.json")}


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
