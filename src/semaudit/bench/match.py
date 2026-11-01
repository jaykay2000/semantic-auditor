"""Score findings against ground truth: one matcher for every condition (docs/08-evaluation.md).

Scoring is per PERSONA-OCCURRENCE. A finding about three personas is three units, and so is a ground-truth
item that names three. This makes grouping neutral: a system that groups the same three occurrences into one
finding, or reports them separately, scores identically.

A finding unit MATCHES a truth unit when the persona, the rule and the target agree, and the label agrees where
the truth carries one (`conflict` and `unexplained_tradeoff` are different answers). Each truth unit is matched
at most once. A unit that lands on a negative control (ignoring label) is a false positive on that pattern. A
unit that matches nothing is a false positive unless adjudication later accepts it as a real, unseeded issue.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from .findings import Finding, Findings, Truth


@dataclass(frozen=True)
class Unit:
    persona: str
    rule: str
    target: frozenset   # a finding has one target; a truth item may be about several events
    label: str | None
    ref: str          # the finding or truth item id this unit came from


def finding_units(fs: Findings) -> list[Unit]:
    return [Unit(p, f.rule, frozenset([f.target.key()]), f.label, f.id) for f in fs.findings for p in f.personas]


def truth_units(t: Truth, kind: str) -> list[Unit]:
    return [Unit(p, i.rule, i.target_keys(), i.label, i.id) for i in t.items if i.kind == kind for p in i.personas]


def _pair(found: list[Unit], truth: list[Unit], *, with_label: bool) -> tuple[list[tuple[Unit, Unit]], list[Unit]]:
    """One-to-one matching on persona, rule and target; with_label also requires the label where the truth has
    one. A truth unit with the same label is preferred over an unlabelled one, so no labelled match is lost."""
    pool = list(truth)
    pairs, rest = [], []
    for f in found:
        cands = [t for t in pool if (t.persona, t.rule) == (f.persona, f.rule) and f.target <= t.target
                 and (not with_label or t.label is None or t.label == f.label)]
        if cands:
            t = min(cands, key=lambda t: t.label != f.label)
            pool.remove(t)
            pairs.append((f, t))
        else:
            rest.append(f)
    return pairs, rest


def score(fs: Findings, truth: Truth, *, evidence: dict[tuple[str, str], str] | None = None) -> dict[str, Any]:
    found = [u for u in finding_units(fs) if truth.personas is None or u.persona in truth.personas]
    issues, ncs = truth_units(truth, "issue"), truth_units(truth, "negative_control")
    matched, rest = _pair(found, issues, with_label=True)
    nc_hits, unmatched = _pair(rest, ncs, with_label=False)

    items = {i.id: i for i in truth.items}
    tp, fp = len(matched), len(nc_hits) + len(unmatched) + len(fs.dropped)
    by_kind: dict[str, dict[str, int]] = defaultdict(lambda: {"truth": 0, "found": 0})
    for t in issues:
        by_kind[items[t.ref].pattern or t.rule]["truth"] += 1
    for _, t in matched:
        by_kind[items[t.ref].pattern or t.rule]["found"] += 1

    nc_total = Counter(items[t.ref].pattern or "unspecified" for t in ncs)
    nc_hit = Counter(items[t.ref].pattern or "unspecified" for _, t in nc_hits)

    # label accuracy on coherence truth: pair ignoring label, then compare
    coh_truth = [t for t in issues + ncs if items[t.ref].label]
    lab_pairs, _ = _pair([u for u in found if u.label], coh_truth, with_label=False)
    confusion = Counter((t.label, f.label) for f, t in lab_pairs)

    by_id = {f.id: f for f in fs.findings}
    sev = [(by_id[f.ref].severity, items[t.ref].severity) for f, t in matched if items[t.ref].severity]
    high = [u for u in found if by_id[u.ref].confidence == "high"]
    high_tp = sum(1 for f, _ in matched if by_id[f.ref].confidence == "high")

    return {
        "system": fs.system, "release": fs.release, "run": fs.run,
        "units": {"found": len(found), "truth_issues": len(issues), "negative_controls": len(ncs)},
        "tp": tp, "fp": fp, "fn": len(issues) - tp,
        "precision": _ratio(tp, tp + fp), "recall": _ratio(tp, len(issues)),
        "intervals": {"precision": wilson(tp, tp + fp), "recall": wilson(tp, len(issues)),
                      "negative_control_fp": wilson(len(nc_hits), len(ncs))},
        "by_kind": {k: {**v, "recall": _ratio(v["found"], v["truth"])} for k, v in sorted(by_kind.items())},
        "negative_controls": {p: {"total": n, "false_positives": nc_hit[p], "fp_rate": _ratio(nc_hit[p], n),
                                  "ci95": wilson(nc_hit[p], n)["ci95"]}
                              for p, n in sorted(nc_total.items())},
        "label_confusion": {f"{a}->{b}": n for (a, b), n in sorted(confusion.items())},
        "label_accuracy": _ratio(sum(n for (a, b), n in confusion.items() if a == b), sum(confusion.values())),
        "severity_agreement": _ratio(sum(a == b for a, b in sev), len(sev)),
        "calibration_high": _ratio(high_tp, len(high)),
        "evidence_support": evidence_support(fs.findings, evidence) if evidence is not None else None,
        "attribution": attribution(fs, truth, matched),
        "matched": [[f.ref, f.persona, t.ref] for f, t in matched],
        "negative_control_hits": [[f.ref, f.persona, t.ref] for f, t in nc_hits],
        "unmatched": [[f.ref, f.persona] for f in unmatched],   # to adjudication
        "malformed": list(fs.dropped),                           # false positives the format cannot express
        "cost_usd": fs.cost_usd, "cost_if_fresh_usd": fs.cost_if_fresh_usd, "calls": fs.calls,
        "cached_calls": fs.cached_calls, "fresh": fs.fresh, "truncated": fs.truncated,
    }


def evidence_support(findings: list[Finding], evidence: dict[tuple[str, str], str | None]) -> dict[str, Any]:
    """A finding is supported when (1) every persona it names has at least one cited event, (2) every cited event
    exists in the captured stories, and (3) a cited MESSAGE carries a non-empty quote found verbatim in its text.
    User actions have no text (evidence value None), so they need only exist. An empty quote never supports a
    message: "" is a substring of everything."""
    bad = []
    for f in findings:
        def ok(c):
            if (c.persona, c.event_id) not in evidence:
                return False
            text = evidence[(c.persona, c.event_id)]
            return text is None or (bool(c.quote.strip()) and c.quote in text)
        covered = {c.persona for c in f.cited}
        if not (f.cited and set(f.personas) <= covered and all(ok(c) for c in f.cited)):
            bad.append(f.id)
    return {"supported": len(findings) - len(bad), "total": len(findings),
            "share": _ratio(len(findings) - len(bad), len(findings)), "unsupported": bad}


def attribution(fs: Findings, truth: Truth, matched: list[tuple[Unit, Unit]]) -> dict[str, Any]:
    """E3 attribution, over matched units whose truth carries a delta: is the finding's new/changed/existing
    right, and does it name every responsible feature? A system that reports no delta scores as not reporting."""
    by_id, items = {f.id: f for f in fs.findings}, {i.id: i for i in truth.items}
    rows = [(by_id[f.ref], items[t.ref]) for f, t in matched if items[t.ref].delta]
    reported = [(f, i) for f, i in rows if f.delta]
    return {"units": len(rows), "reported": len(reported),
            "delta_correct": sum(f.delta == i.delta for f, i in reported),
            "delta_accuracy": wilson(sum(f.delta == i.delta for f, i in reported), len(rows)),
            "features_correct": wilson(sum(set(i.features) <= set(f.features) for f, i in reported), len(rows))}


def wilson(k: int, n: int, z: float = 1.96) -> dict[str, Any]:
    """A proportion with its raw counts and a 95% Wilson interval, so small denominators read as small."""
    if not n:
        return {"k": k, "n": n, "value": None, "ci95": None}
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * ((ph * (1 - ph) / n + z * z / (4 * n * n)) ** 0.5) / d
    return {"k": k, "n": n, "value": round(ph, 4), "ci95": [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]}


def jaccard(runs: list[Findings], *, require_fresh: bool = True) -> float | None:
    """E3: mean pairwise Jaccard of the unit sets across runs (persona, rule, target, label). Stability is a claim
    about inference, so every run must be fresh; a cached replay measures replay determinism instead."""
    if require_fresh and not all(r.fresh for r in runs):
        raise ValueError("stability needs fresh runs; a cached replay measures replay determinism, not stability")
    sets = [{(u.persona, u.rule, u.target, u.label) for u in finding_units(r)} for r in runs]
    pairs = [(a, b) for i, a in enumerate(sets) for b in sets[i + 1:]]
    if not pairs:
        return None
    return round(sum(len(a & b) / len(a | b) if a | b else 1.0 for a, b in pairs) / len(pairs), 4)


def evidence_index(review: dict) -> dict[tuple[str, str], str | None]:
    """(persona, event id) -> the message text, or None for a user action (which has no text to quote)."""
    return {(p["id"], e["id"]): (None if e.get("kind") == "user_action" else e.get("text") or "")
            for p in review.get("personas", []) for e in p.get("events", [])}


def _ratio(a: int, b: int) -> float | None:
    return round(a / b, 4) if b else None
