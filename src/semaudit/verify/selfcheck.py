"""Judge self-check: before a review may recommend Hold or Ship, its model judge answers a fixed set of known cases.

The judge is the `interpreter` role, the model step whose answer decides whether an issue is raised:
  rules mode   it labels each coherence-rule candidate (conflict / unexplained tradeoff / explained / compatible)
               with relate/interpret.py's prompt, and code turns the label into violated or passed (rules.eval_p2);
  reader mode  it reads every rule and every story and names the findings, with the frozen judge_one prompt
               (decide/reader.py), and code keeps a finding only when its quotes are in the cited message.
The self-check sends known cases through exactly that path: the same role, the same prompt text, the same code
after the model. The cases (one file, `examples/judge-self-check.yaml` by default, or `[self_check] cases` in
semaudit.toml) are of two kinds: one planted mistake the judge must catch, or a correct story it must clear.

Kept apart from the review on purpose:
  * separate calls through a separate router: no case is mixed into the review's own judging, and the review's
    accounting is unchanged. The self-check's budget is what is left of the review's --max-usd;
  * every call is fresh (never served from the cache), so each review measures the judge as it answers today;
  * it runs after the review's own judging, so a self-check that runs out of budget cannot change the review.

Scoring is code: a case is answered correctly when a planted mistake is flagged or a correct case is cleared. The
result is `passed` only when every case was answered correctly; `failed` when any was not; `not_run` (with the
reason) when any case could not be judged: no key, no budget, an unreadable reply, a missing case file. A
`not_run` is never a pass. report/review.py::outcome_of turns `failed` and `not_run` into a not-measurable outcome.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from semaudit.models.router import ModelError, Router
from semaudit.story.model import Event, Extraction, Story

REPO = Path(__file__).resolve().parents[3]
CASES = REPO / "examples" / "judge-self-check.yaml"
ROLE = "interpreter"
_AT = re.compile(r"D(\d+) (\d{1,2}):(\d{2})(?::(\d{2}))?$")


class CaseError(ValueError):
    """The case file is missing or does not describe a case the judge can be asked."""


def cases_path(root: Path | None = None) -> Path:
    """`[self_check] cases` in semaudit.toml (relative to the root), else the repository's case file."""
    import tomllib
    cfg = (root or Path.cwd()) / "semaudit.toml"
    if cfg.exists():
        rel = (tomllib.loads(cfg.read_text()).get("self_check") or {}).get("cases")
        if rel:
            return (root or Path.cwd()) / rel
    return CASES


def _at(day0: datetime, s: str) -> datetime:
    m = _AT.match(str(s).strip())
    if not m:
        raise CaseError(f"time {s!r} is not 'D<n> HH:MM[:SS]'")
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return day0 + timedelta(days=d, hours=h, minutes=mi, seconds=se)


def load_cases(path: Path, mode: str) -> tuple[list[dict], object, str]:
    """(cases of this mode, each with its built `story`; the contract they are judged against; the file's digest)."""
    from semaudit.contract.schema import load_contract
    if not path.is_file():
        raise CaseError(f"case file {path} not found")
    raw = path.read_bytes()
    spec = yaml.safe_load(raw)
    day0 = datetime.fromisoformat(spec["day0"]).replace(tzinfo=UTC)
    contract = load_contract(path.parent / spec["contract"])
    out = []
    for c in spec["cases"]:
        if c["mode"] != mode:
            continue
        if c.get("expect") not in ("flag", "clear"):
            raise CaseError(f"{c['id']}: expect must be flag or clear")
        events = []
        for e in c["events"]:
            at = _at(day0, e["at"])
            if "do" in e:
                events.append(Event(id=e["id"], at=at, kind="user_action", action=e["do"],
                                    effects=e.get("effects") or {}))
                continue
            x = (spec.get("extraction") or {}).get(e["msg"]) if mode == "rules" else None
            events.append(Event(id=e["id"], at=at, kind="message", feature=e["feature"], surface=e["surface"],
                                channel=e["channel"], component=e.get("component", spec.get("component")),
                                copy_key=e["msg"],
                                text=e.get("text", spec["copy"][e["msg"]]), user_initiated=e.get("user_initiated", False),
                                extraction=Extraction(**x) if x else None))
        ctx = {k: (_at(day0, v) if isinstance(v, str) and _AT.match(v) else v) for k, v in (c.get("context") or {}).items()}
        story = Story(id=c["id"], release="self-check", persona=c["id"], context=ctx, truth=c.get("truth") or {},
                      events=events)
        if c["expect"] == "flag" and mode == "reader" and not any(e.id == (c.get("planted") or {}).get("event")
                                                                    for e in events):
            raise CaseError(f"{c['id']}: a reader case to flag must name its planted event")
        out.append({**c, "story": story})
    if not out:
        raise CaseError(f"no {mode} cases in {path}")
    return out, contract, hashlib.sha256(raw).hexdigest()


def score(cases: list[dict], answers: dict[str, dict]) -> dict:
    """Deterministic: per case, was the planted mistake flagged / the correct case cleared? `answers`: case id ->
    {"flagged": bool, "detail": str} or {"error": str}. Any error makes the result not_run, never a pass."""
    rows, errors = [], []
    for c in cases:
        a = answers.get(c["id"]) or {"error": "no answer"}
        if "error" in a:
            errors.append(f"{c['id']}: {a['error']}")
            rows.append({"id": c["id"], "expect": c["expect"], "got": None, "correct": False, "detail": a["error"]})
            continue
        got = "flag" if a["flagged"] else "clear"
        rows.append({"id": c["id"], "expect": c["expect"], "got": got, "correct": got == c["expect"],
                     "detail": a.get("detail", "")})
    planted = [r for r in rows if r["expect"] == "flag"]
    right = [r for r in rows if r["expect"] == "clear"]
    out = {"cases_run": len(rows), "planted": len(planted), "caught": sum(r["correct"] for r in planted),
           "correct_cases": len(right), "cleared": sum(r["correct"] for r in right),
           "answered_correctly": sum(r["correct"] for r in rows),
           "failing": [r["id"] for r in rows if not r["correct"]], "cases": rows}
    if errors:
        out.update(status="not_run", reason="; ".join(errors))
    elif out["failing"]:
        out.update(status="failed", reason="judge self-check failed: " + ", ".join(out["failing"]))
    else:
        out.update(status="passed", reason="")
    return out


def _rules_answers(cases, contract, router) -> dict[str, dict]:
    from semaudit.relate.interpret import model_interpreter
    from semaudit.relate.rules import eval_p2
    rule = contract.rules_of("coherence")[0]
    out = {}
    for c in cases:
        interp = model_interpreter(router, fresh=True, rng=random.Random(f"self-check:{c['id']}"))
        entries = eval_p2(rule, c["story"], contract, interp)
        if len(entries) != 1:
            out[c["id"]] = {"error": f"the case gives {len(entries)} candidate pairs, not 1"}
            continue
        e = entries[0]
        out[c["id"]] = {"flagged": e.status == "violated",
                        "detail": f"{rule.id} {e.status} ({e.label})"
                                  + (f"; reconciler rejected: {e.meta['reconciler_rejected']}"
                                     if e.meta.get("reconciler_rejected") else "")}
    return out


def _reader_answers(cases, contract, router) -> dict[str, dict]:
    from semaudit.bench import judge
    from semaudit.decide.reader import check_citations
    stories = {c["id"]: c["story"] for c in cases}
    found, dropped = judge.judge_one(stories, contract, router, release="self-check", fresh=True, run="self-check")
    if found.truncated:
        return {c["id"]: {"error": "the judge's reply was cut off"} for c in cases}
    cited: dict[str, list[tuple[str, str]]] = {k: [] for k in stories}      # case -> [(rule, event id)] accepted
    for f in found.findings:
        accepted, _, _ = check_citations(f, stories)
        for persona, cs in accepted.items():
            cited.setdefault(persona, []).extend((f.rule, x[0]) for x in cs)
    out = {}
    for c in cases:
        hits = cited.get(c["id"], [])
        planted = (c.get("planted") or {}).get("event")
        flagged = any(ev == planted for _, ev in hits) if c["expect"] == "flag" else bool(hits)
        detail = ", ".join(sorted({f"{r} on {ev}" for r, ev in hits})) or "no finding with a checked quote"
        out[c["id"]] = {"flagged": flagged, "detail": detail}
    if dropped:
        for v in out.values():
            v["detail"] += f" ({len(dropped)} malformed finding(s) dropped)"
    return out


def _why_not(e: Exception) -> str:
    s = str(e)
    if "is not set" in s:
        return "no key: " + s
    if s.startswith("budget exhausted") or "could not count it" in s:
        return "budget: " + s
    return f"{type(e).__name__}: {s}"[:300]


def run(mode: str, *, root: Path | None = None, max_usd: float | None, tag: str = "",
        path: Path | None = None) -> dict:
    """The self-check for a review in `mode` ("rules" or "reader"). `max_usd`: what is left of the review's budget.
    Never raises: anything that stops a case from being judged is reported as not_run with the reason."""
    from semaudit.bench.judge import prompt
    from semaudit.relate.interpret import INSTRUCTIONS
    path = path or cases_path(root)
    text = INSTRUCTIONS if mode == "rules" else prompt("judge_one")
    rec = {"role": ROLE, "mode": mode,
           "prompt": "relate/interpret.py INSTRUCTIONS" if mode == "rules" else "bench/conditions/prompts/judge_one.md",
           "prompt_sha256": hashlib.sha256(text.encode()).hexdigest()[:16],
           "cases_file": str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path),
           "calls": 0, "cost_usd": 0.0}
    try:
        cases, contract, digest = load_cases(path, mode)
    except (CaseError, OSError, KeyError, ValueError) as e:
        out = {**rec, "status": "not_run", "reason": f"cases: {e}", "cases_run": 0, "failing": []}
        return {**out, "line": line(out)}
    rec["cases_sha256"] = digest[:16]
    if max_usd is not None and max_usd <= 0:
        out = {**rec, **score(cases, {c["id"]: {"error": "budget: nothing left of --max-usd"} for c in cases}),
               "reason": "budget: nothing left of --max-usd"}
        return {**out, "line": line(out)}
    router = Router(root=root or Path.cwd(), max_usd=max_usd)
    router.tag = f"judge-self-check:{mode}" + (f":{tag}" if tag else "")
    spec = router.roles.get(ROLE, {})
    rec["model"], rec["provider"] = spec.get("model"), spec.get("provider")
    try:
        answers = (_rules_answers if mode == "rules" else _reader_answers)(cases, contract, router)
    except (ModelError, KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
        answers = {c["id"]: {"error": _why_not(e)} for c in cases}
    out = {**rec, **score(cases, answers)}
    acct = router.accounting()
    out["calls"], out["cost_usd"] = acct["calls"], round(router.spent_usd, 6)
    if out["status"] == "not_run" and len({a.get("error") for a in answers.values()}) == 1:
        out["reason"] = next(iter(answers.values()))["error"]          # one cause for every case: say it once
    return {**out, "line": line(out)}


def off(reason: str = "turned off with --no-self-check") -> dict:
    out = {"status": "off", "reason": reason, "role": ROLE, "cases_run": 0, "failing": [], "calls": 0,
           "cost_usd": 0.0}
    return {**out, "line": line(out)}


def line(sc: dict | None) -> str:
    """The one plain line the CLI and the page show."""
    if not sc:
        return "Judge self-check: not run (none recorded in this review)"
    n, ok = sc.get("cases_run", 0), sc.get("answered_correctly", 0)
    cost = f" · ${sc.get('cost_usd', 0):.3f}"
    if sc["status"] == "passed":
        return (f"Judge self-check: {ok} of {n} planted cases answered correctly ({sc['caught']} of {sc['planted']} "
                f"planted mistakes caught, {sc['cleared']} of {sc['correct_cases']} correct cases cleared){cost}")
    if sc["status"] == "failed":
        return (f"Judge self-check FAILED: {ok} of {n} answered correctly; wrong on {', '.join(sc['failing'])}. "
                f"No Hold or Ship is given{cost}")
    if sc["status"] == "off":
        return f"Judge self-check: off ({sc['reason']})"
    return f"Judge self-check: not run ({sc['reason']})"
