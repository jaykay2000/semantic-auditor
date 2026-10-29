"""A bug ticket drafted from one issue of a review: what a product team needs to reproduce and judge it.

Everything in the ticket is read from the review JSON: the rule, who saw it, the steps they took, the exact text
each cited message showed (surface, moment, capture), the true value where the rule compares with one, how the
issue changed between the two releases, its verification, and the command that replays it. Nothing is inferred
beyond what the review records. The ticket is a draft: filing it is a person's decision.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

QUOTE_CHARS = 600


def _find(review: dict, issue_id: str) -> tuple[dict, bool]:
    for i in review.get("issues", []):
        if i["id"] == issue_id:
            return i, False
    for i in review.get("resolved", []) + review.get("unconfirmed", []):
        if i["id"] == issue_id:
            return i, True
    raise KeyError(f"no issue {issue_id!r} in this review")


def _forms(why: str) -> list[str]:
    """The figures the issue names, as a page may print them ("24500" -> "24,500", "24500", "24.5K")."""
    out = []
    for n in re.findall(r"\d+(?:\.\d+)?", why or ""):
        v = float(n)
        if v < 10:
            continue
        i = int(v) if v == int(v) else None
        out += [n] + ([f"{i:,}", f"{i/1000:g}K"] if i and i >= 1000 else [])
    return list(dict.fromkeys(out))


def _quote(text: str, why: str = "") -> str:
    t = (text or "").strip()
    if len(t) > QUOTE_CHARS:
        lines = t.splitlines()
        hit = [n for n, line in enumerate(lines) if any(f in line for f in _forms(why))]
        if hit:                                   # the lines that state the figures, with one line around each
            keep = sorted({k for n in hit for k in (n - 1, n, n + 1) if 0 <= k < len(lines)})
            parts, prev = [], None
            for k in keep:
                if prev is not None and k != prev + 1:
                    parts.append("…")
                parts.append(lines[k])
                prev = k
            t = ("…\n" if keep[0] > 0 else "") + "\n".join(parts) + ("\n…" if keep[-1] < len(lines) - 1 else "")
        else:
            t = t[:QUOTE_CHARS].rstrip() + " …"
    return "\n".join("> " + line if line else ">" for line in t.splitlines()) or "> (empty)"


def _steps(persona: dict, base: bool, until: str | None) -> list[str]:
    out = []
    for s in persona.get("base_steps" if base else "steps") or []:
        params = s.get("params") or {}
        p = ", ".join(f"{k}={v}" for k, v in params.items())
        status = "" if s.get("status") == "done" else f" ({s.get('status')})"
        out.append(f"{s.get('do')}{f'({p})' if p else ''}{status} at {s.get('at', '')[11:16]}")
        if until and s.get("step_id") == until:
            break
    return out


def ticket(review: dict, issue_id: str, persona: str | None = None) -> str:
    """`persona`: draft from this persona's occurrence (default: the first)."""
    issue, resolved = _find(review, issue_id)
    rel = review.get("release") or {}
    app = (review.get("app") or {}).get("name") or "app"
    rules = {r["id"]: r for r in review.get("rules", [])}
    rule = rules.get(issue["rule"], {})
    personas = {p["id"]: p for p in review.get("personas", [])}
    occ = next((o for o in issue["occurrences"] if o["persona"] == persona), issue["occurrences"][0])
    persona = personas.get(occ["persona"], {})
    evs = {e["id"]: e for e in persona.get("base_events" if resolved else "events") or []}
    cited = [evs[x] for x in occ["events"] if x in evs and evs[x].get("kind") == "message"]
    release = rel.get("base") if resolved else rel.get("head")
    title = f"[{app} {release}] {rule.get('title') or issue['rule']}: {issue.get('why', '')}"
    if len(title) > 140:
        title = title[:137].rstrip() + "…"

    sev = (issue.get("severity") or {}).get("level", "")
    conf = (issue.get("confidence") or {}).get("level", "")
    ver = (issue.get("verification") or {}).get("status", "not verified")
    delta = issue.get("delta", "")
    lines = [f"# {title}", "",
             f"**Release:** {release}" + (f" (compared with {rel.get('base')})" if not resolved else
                                          f" (gone in {rel.get('head')})"),
             f"**Change between releases:** {delta}" + (f" — {issue['delta_basis']}" if issue.get("delta_basis") else ""),
             f"**Severity:** {sev} · **Confidence:** {conf} · **Verification:** {ver}",
             f"**Personas affected:** {', '.join(issue.get('personas') or sorted({o['persona'] for o in issue['occurrences']}))}",
             "", "## What is wrong", "", issue.get("why", ""), "",
             f"Rule {issue['rule']}: {rule.get('text') or issue.get('rule_text', '')}", ""]
    also = {}
    for o in issue["occurrences"]:
        for a in o.get("also") or []:
            also.setdefault((a["rule"], a.get("note", "")), 0)
            also[(a["rule"], a.get("note", ""))] += 1
    n = len(issue["occurrences"])
    for (rule_id, note), k in also.items():
        lines.append(f"Also breaks {rule_id}: {note}" + (f" ({k} of {n} personas)" if n > 1 else ""))
    lines += ["", "## Steps to reproduce", "",
              f"Persona `{persona.get('id', occ['persona'])}` ({persona.get('role', '')}): "
              + "; ".join(persona.get("summary") or []), ""]
    last = max((e.get("step_id") for e in cited if e.get("step_id")), default=None)
    lines += [f"{n}. {s}" for n, s in enumerate(_steps(persona, resolved, last), 1)]
    lines += ["", "## What the user was shown", ""]
    for e in cited:
        ev = e.get("evidence") or {}
        lines += [f"**{e.get('surface')}** · {e.get('feature')} · {e.get('at', '')[:16].replace('T', ' ')} · "
                  f"capture `{ev.get('capture_id', '')}`", "", _quote(e.get("text", ""), issue.get("why", "")), ""]
    lines += ["## Reproduce", "", f"`{issue['repro']}`" if issue.get("repro") else "(no replay command recorded)", "",
              "---", f"Drafted by the Semantic Auditor from the review of {app} {rel.get('base')} → {rel.get('head')}"
              f" ({review.get('written_at', '')}). A draft: a person decides whether to file it."]
    return "\n".join(lines) + "\n"


def write_ticket(review_path: Path, issue_id: str, out: Path | None = None, persona: str | None = None) -> Path:
    review = json.loads(Path(review_path).read_text())
    md = ticket(review, issue_id, persona)
    out = out or Path(review_path).parent / "tickets" / f"{issue_id}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md)
    return out


def summary(review: dict) -> list[dict[str, Any]]:
    """One line per head and resolved issue, for choosing which to draft."""
    return [{"id": i["id"], "delta": i.get("delta"), "why": i.get("why", "")} for i in
            review.get("issues", []) + review.get("resolved", [])]
