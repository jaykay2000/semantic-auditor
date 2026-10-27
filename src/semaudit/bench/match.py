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

from .findings import Finding, Findings, Truth, TruthItem


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
    tp, fp = len(matched), len(nc_hits) + len(unmatched)
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
        "by_kind": {k: {**v, "recall": _ratio(v["found"], v["truth"])} for k, v in sorted(by_kind.items())},
        "negative_controls": {p: {"total": n, "false_positives": nc_hit[p], "fp_rate": _ratio(nc_hit[p], n)}
                              for p, n in sorted(nc_total.items())},
        "label_confusion": {f"{a}->{b}": n for (a, b), n in sorted(confusion.items())},
        "label_accuracy": _ratio(sum(n for (a, b), n in confusion.items() if a == b), sum(confusion.values())),
        "severity_agreement": _ratio(sum(a == b for a, b in sev), len(sev)),
        "calibration_high": _ratio(high_tp, len(high)),
        "evidence_support": evidence_support(fs.findings, evidence) if evidence is not None else None,
        "matched": [[f.ref, f.persona, t.ref] for f, t in matched],
        "negative_control_hits": [[f.ref, f.persona, t.ref] for f, t in nc_hits],
        "unmatched": [[f.ref, f.persona] for f in unmatched],   # to adjudication
        "cost_usd": fs.cost_usd, "calls": fs.calls,
    }


def evidence_support(findings: list[Finding], evidence: dict[tuple[str, str], str]) -> dict[str, Any]:
    """A finding is supported when it cites at least one event and every cited event exists in the captured
    stories with its quote verbatim in that event's text."""
    bad = []
    for f in findings:
        ok = bool(f.cited) and all((c.persona, c.event_id) in evidence and c.quote in evidence[(c.persona, c.event_id)]
                                   for c in f.cited)
        if not ok:
            bad.append(f.id)
    return {"supported": len(findings) - len(bad), "total": len(findings),
            "share": _ratio(len(findings) - len(bad), len(findings)), "unsupported": bad}


def jaccard(runs: list[Findings]) -> float | None:
    """E3: mean pairwise Jaccard of the unit sets across runs (persona, rule, target, label)."""
    sets = [{(u.persona, u.rule, u.target, u.label) for u in finding_units(r)} for r in runs]
    pairs = [(a, b) for i, a in enumerate(sets) for b in sets[i + 1:]]
    if not pairs:
        return None
    return round(sum(len(a & b) / len(a | b) if a | b else 1.0 for a, b in pairs) / len(pairs), 4)


def evidence_index(review: dict) -> dict[tuple[str, str], str]:
    return {(p["id"], e["id"]): e.get("text") or "" for p in review.get("personas", []) for e in p.get("events", [])}


def _ratio(a: int, b: int) -> float | None:
    return round(a / b, 4) if b else None
