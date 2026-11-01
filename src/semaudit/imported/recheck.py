"""Replay an imported check on a release and re-check its invariant. Four statuses, never merged:

  replay               succeeded | failed: every step ran ("done"), nothing was left unmeasured, no step note says
                       the app refused what the finding needs (imports.yaml `step_note_fails`), and the invariant's
                       surface was captured with at least one message. Deterministic given the app.
  assertion            pass | fail | not_measurable: the majority of N independent judgments (one small model call
                       each: the invariant, the rule, the surface's captured messages and the app's own record; never
                       the original quote). No majority -> not_measurable.
  semantic_confidence  how many of the N judgments agree with the majority (high: all, medium: >= 2/3, low:
                       otherwise). The replay can be deterministic while the judgment varies; this says how much.
  evidence             verified | partially_verified | unverified: the majority judgments' quotes are checked against
                       the captured messages on that surface (decide.reader.check_citations) and the record values
                       they cite against the record itself.

A replay that failed is never judged: its assertion is not_measurable, with the replay's reasons.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from semaudit.bench.findings import Cited, Finding, Target
from semaudit.capture.runner import Runner
from semaudit.contract.schema import Contract, Persona, Scenario, load_contract
from semaudit.decide.pipeline import measurement_problems
from semaudit.decide.reader import check_citations
from semaudit.models.router import Router, UnreadableReply
from semaudit.story.build import story_from_episode
from semaudit.story.episode import Episode

from .record import ImportedCheck, ImportSpec

ROLE = "check_judge"
PROMPT = Path(__file__).with_name("prompts") / "judge.md"


def with_checks(contract: Contract, checks: list[ImportedCheck]) -> Contract:
    """The contract plus each converted check's persona and scenario (nothing else changes)."""
    personas = [Persona(**c.persona) for c in checks]
    scenarios = [Scenario(**c.scenario) for c in checks]
    return contract.model_copy(update={"personas": list(contract.personas) + personas,
                                       "scenarios": list(contract.scenarios) + scenarios})


def replay(checks: list[ImportedCheck], contract_dir: Path, release: str, *, runs_dir: Path, run_id: str,
           approved_only: bool = True, approvals: dict | None = None) -> dict[str, Episode]:
    """Capture each check's scenario on `release`, fresh. Unapproved checks are refused unless approved_only=False
    (a measurement run, whose results then say approved: false)."""
    if approved_only:
        bad = [c.id for c in checks if not is_approved(c, approvals or {})]
        if bad:
            raise PermissionError("not approved by the owner at their current content: " + ", ".join(bad))
    contract = with_checks(load_contract(contract_dir), checks)
    by_persona = {c.persona["id"]: c.id for c in checks}
    out: dict[str, Episode] = {}
    with Runner(contract_dir, contract=contract, runs_dir=runs_dir, run_id=run_id) as run:
        for ep in run.capture(release, list(by_persona)):
            out[by_persona[ep.persona]] = ep
    return out


def is_approved(check: ImportedCheck, approvals: dict) -> bool:
    a = approvals.get(f"check:{check.id}")
    return bool(a) and a.get("hash") == check.digest()


# ---------- the replay's own status ----------

def replay_status(ep: Episode | None, check: ImportedCheck, contract: Contract, spec: ImportSpec) -> dict[str, Any]:
    if ep is None:
        return {"status": "failed", "reasons": ["no episode was captured"], "notes": []}
    reasons = list(measurement_problems(ep))
    reasons += [f"step {s.seq} ({s.do}) was {s.status}" + (f": {s.note}" if s.note else "")
                for s in ep.steps if s.status != "done" and s.status != "failed"]
    notes = [f"step {s.seq} ({s.do}): {s.note}" for s in ep.steps if s.note]
    for s in ep.steps:
        for pat in spec.step_note_fails:
            if s.note and re.search(pat, s.note, re.I):
                reasons.append(f"step {s.seq} ({s.do}) did not do what the finding needs: {s.note}")
    msgs = surface_messages(ep, check, contract)
    if not msgs:
        reasons.append(f"no message was captured on {check.invariant.surface}")
    return {"status": "failed" if reasons else "succeeded", "reasons": reasons, "notes": notes,
            "surface_messages": len(msgs)}


def _story(ep: Episode, check: ImportedCheck, contract: Contract):
    return story_from_episode(ep, with_checks(contract, [check]))


def surface_messages(ep: Episode, check: ImportedCheck, contract: Contract) -> list:
    return [e for e in _story(ep, check, contract).messages() if e.surface == check.invariant.surface]


def record_at(ep: Episode, msgs: list) -> dict[str, Any]:
    """The app's own record (every oracle read OK) at the last step at or before the surface's last message."""
    if not msgs:
        return {}
    last = max(m.at for m in msgs)
    out: dict[str, Any] = {}
    for st in ep.steps:
        if st.at <= last:
            for name, r in st.state.items():
                if r.status == "ok":
                    out[name] = r.values
    return out


# ---------- the judgment ----------

def _schema() -> dict:
    s = lambda: {"type": "string"}  # noqa: E731
    cited = {"type": "object", "additionalProperties": False, "required": ["event_id", "quote"],
             "properties": {"event_id": s(), "quote": s()}}
    rec = {"type": "object", "additionalProperties": False, "required": ["field", "value"],
           "properties": {"field": s(), "value": s()}}
    return {"type": "object", "additionalProperties": False, "required": ["outcome", "why", "cited", "record"],
            "properties": {"outcome": {"type": "string", "enum": ["pass", "fail", "not_measurable"]}, "why": s(),
                           "cited": {"type": "array", "items": cited}, "record": {"type": "array", "items": rec}}}


SCHEMA = _schema()


def judge_payload(check: ImportedCheck, contract: Contract, msgs: list, record: dict, persona_ctx: dict) -> dict:
    """What the judge sees. Deliberately NOT the original finding (its quote, claim or figures)."""
    rule = contract.rule(check.invariant.rule)
    surface = next(s for s in contract.surfaces if s.id == check.invariant.surface)
    return {"rule": {"id": rule.id, "title": rule.title, "text": rule.text},
            "invariant": check.invariant.statement,
            "surface": {"id": surface.id, "kind": surface.kind},
            "messages": [{"event_id": m.id, "text": m.text} for m in msgs],
            "persona": persona_ctx, "record": record}


def judge(router: Router, body: dict, *, seed: int, fresh: bool = False) -> dict[str, Any]:
    """One judgment. A reply that is still not JSON after the router's retries (the model ran away to its token cap)
    is a not_measurable vote with no evidence, never a crash and never a pass or a fail."""
    try:
        r = router.complete(ROLE, [{"role": "system", "content": PROMPT.read_text()},
                                   {"role": "user", "content": json.dumps(body, ensure_ascii=False, default=str)}],
                            schema=SCHEMA, schema_name="judgment", seed=seed, fresh=fresh)
    except UnreadableReply as e:
        return {"outcome": "not_measurable", "why": f"unreadable reply: {e}"[:300], "cited": [], "record": [],
                "seed": seed, "model": (getattr(router, "roles", {}).get(ROLE) or {}).get("model"), "cached": False,
                "cost_usd": None, "unreadable": True}
    out = dict(r.parsed or {"outcome": "not_measurable", "why": "unreadable reply", "cited": [], "record": []})
    out.update(seed=seed, model=r.model, cached=r.cached, cost_usd=r.cost_usd,
               runaway_retries=r.unreadable_attempts, runaway_cost_usd=round(r.unreadable_cost_usd, 6))
    return out


def needs_evidence(assertion: dict, evidence: str) -> dict:
    """A PASS needs both a satisfied rule and verified evidence. A majority pass whose majority judgments' evidence is
    not "verified" is not measurable (the votes stay as recorded, `majority` keeps what they said). FAIL is unchanged:
    this is stricter than the vote alone, so it can never turn a failing result into a pass."""
    if assertion["outcome"] != "pass" or evidence == "verified":
        return assertion
    return {**assertion, "outcome": "not_measurable", "majority": "pass",
            "why": f"pass without verified evidence ({evidence})"}


# ---------- evidence ----------

def _path(obj: Any, path: str) -> Any:
    """`a.b[0].c` (also `a[].b` for the first element) into nested dicts and lists; KeyError when absent."""
    cur = obj
    for part in re.findall(r"[^.\[\]]+|\[\d*\]", path):
        if part.startswith("["):
            if not isinstance(cur, list) or not cur:
                raise KeyError(path)
            idx = int(part[1:-1] or 0)
            if idx >= len(cur):
                raise KeyError(path)
            cur = cur[idx]
        elif isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise KeyError(path)
    return cur


def _same(want: Any, got: str) -> bool:
    """A number in the record matches the one number the judgment wrote (stray punctuation around it is ignored:
    the judge model sometimes writes ': 89.99'); anything else compares as trimmed, case-folded text."""
    nums = re.findall(r"-?\d[\d,]*(?:\.\d+)?", str(got))
    if isinstance(want, (int, float)) and not isinstance(want, bool):
        return len(nums) == 1 and abs(float(nums[0].replace(",", "")) - float(want)) < 0.005
    try:
        w = float(str(want).replace(",", "").replace("$", ""))
    except ValueError:
        return str(want).strip().lower() == str(got).strip().strip("'\"").lower()
    return len(nums) == 1 and abs(float(nums[0].replace(",", "")) - w) < 0.005


def _lookup(record: dict, field: str) -> tuple[bool, Any]:
    """(found, value) of a record path; the path may start with an oracle name."""
    for root in [record] + [record[k] for k in record]:
        try:
            return True, _path(root, field)
        except KeyError:
            continue
    return False, None


CLEAN_NUMBER = re.compile(r"\s*[:=]?\s*\$?\s*-?\$?\d[\d,]*(?:\.\d+)?\s*")
MALFORMED_REASKS = 3      # a judgment whose record values are garbage is asked again (fresh seed) up to this many times


def malformed_values(j: dict, record: dict) -> list[str]:
    """Record values a judgment wrote that are not a number at all where the record holds a number: model garbage
    (`'|1|7|9|.|9|8|'`, `'***REDACTED***'`, `'},{'`), not a reading. A clean number that is WRONG is not listed here:
    that is a misreading, and it still counts against the evidence."""
    bad = []
    for r in j.get("record", []):
        found, val = _lookup(record, r.get("field", ""))
        if (found and isinstance(val, (int, float)) and not isinstance(val, bool)
                and not CLEAN_NUMBER.fullmatch(str(r.get("value", "")))):
            bad.append(f"{r.get('field')}: {str(r.get('value'))[:40]!r}")
    return bad


def judge_clean(router: Router, body: dict, record: dict, *, seed: int, fresh: bool = False,
                reasks: int = MALFORMED_REASKS) -> dict[str, Any]:
    """One judgment; asked again with a fresh seed while its record values are garbage. The discarded judgments are
    kept (with what was malformed and what they cost). If garbage persists, the last one stands and its evidence is
    graded as it is (partially verified at best): nothing is ever loosened, only asked again."""
    j = judge(router, body, seed=seed, fresh=fresh)
    discarded = []
    for k in range(reasks):
        bad = malformed_values(j, record)
        if not bad:
            break
        discarded.append({"seed": j["seed"], "outcome": j["outcome"], "malformed": bad,
                          "cost_usd": 0.0 if j.get("cached") else (j.get("cost_usd") or 0.0)
                          + j.get("runaway_cost_usd", 0.0)})
        j = judge(router, body, seed=seed + 2000 + k, fresh=fresh)
    j["malformed_reasks"] = len(discarded)
    j["malformed_discarded"] = discarded
    return j


def record_checks(cited: list[dict], record: dict) -> tuple[list[str], list[str]]:
    """(ok, refused) for the record values a judgment says it used. A path may start with an oracle name."""
    ok, bad = [], []
    for r in cited:
        f, v = r.get("field", ""), r.get("value", "")
        found, val = _lookup(record, f)
        if not found:
            bad.append(f"{f}: not in the record")
        elif not _same(val, v):
            bad.append(f"{f}: judgment read {v!r}, record holds {val!r}")
        else:
            ok.append(f"{f} = {v}")
    return ok, bad


def evidence_of(j: dict, check: ImportedCheck, story, record: dict) -> dict[str, Any]:
    f = Finding(id="j", personas=[story.persona], rule=check.invariant.rule, target=Target(kind="story"),
                cited=[Cited(persona=story.persona, event_id=c["event_id"], quote=c["quote"]) for c in j["cited"]])
    found, refused, moved = check_citations(f, {story.persona: story})
    on_surface = [c for c in found.get(story.persona, []) if c[1] == check.invariant.surface]
    off = [f"{c[0]}: quote is on {c[1]}, not {check.invariant.surface}" for c in found.get(story.persona, [])
           if c[1] != check.invariant.surface]
    rok, rbad = record_checks(j.get("record", []), record)
    # a quote found in the capture but too bare to say anything (a label with no figure) is not evidence either way;
    # every other refusal (not in the capture, another message, another surface) counts against the judgment
    bare = [r for r in refused if "states no figure" in r]
    false = [r for r in refused if r not in bare]
    q_ok = len(on_surface) - len(moved)
    q_bad = len(false) + len(off) + len(moved)
    if q_ok >= 1 and q_bad == 0 and not rbad:
        status = "verified"
    elif q_ok >= 1:                       # record values alone say nothing about what the surface showed
        status = "partially_verified"
    else:
        status = "unverified"
    return {"status": status, "quotes_ok": q_ok, "quotes_bare": bare,
            "quotes_refused": false + off + [f"re-pointed {m}" for m in moved],
            "record_ok": rok, "record_refused": rbad}


# ---------- one check on one release ----------

def recheck(check: ImportedCheck, ep: Episode | None, contract: Contract, spec: ImportSpec, router: Router, *,
            judgments: int = 3, fresh: bool = True, approved: bool) -> dict[str, Any]:
    rs = replay_status(ep, check, contract, spec)
    base = {"check": check.id, "check_digest": check.digest(), "approved": approved,
            "models": {"conversion": check.conversion.model,
                       "judging": (getattr(router, "roles", {}).get(ROLE) or {}).get("model")},
            "release": ep.release if ep else None, "episode": ep.id if ep else None, "replay": rs}
    if rs["status"] != "succeeded":
        return {**base, "assertion": {"outcome": "not_measurable", "why": "the replay did not succeed",
                                      "votes": {}},
                "semantic_confidence": {"level": None, "agreement": None, "judgments": 0},
                "evidence": {"status": "unverified", "why": "nothing was judged"}, "judgments": [], "cost_usd": 0.0}
    story = _story(ep, check, contract)
    msgs = [e for e in story.messages() if e.surface == check.invariant.surface]
    record = record_at(ep, msgs)
    body = judge_payload(check, contract, msgs, record, story.context)
    js = [judge_clean(router, body, record, seed=k + 1, fresh=fresh) for k in range(judgments)]
    votes = Counter(j["outcome"] for j in js)
    top, n = votes.most_common(1)[0]
    outcome = top if n * 2 > judgments else "not_measurable"
    agree = n / judgments
    level = "high" if n == judgments else "medium" if agree >= 2 / 3 else "low"
    evs = [evidence_of(j, check, story, record) for j in js]
    for j, e in zip(js, evs):
        j["evidence"] = e
    maj = [e for j, e in zip(js, evs) if j["outcome"] == outcome] if n * 2 > judgments else evs
    rank = {"verified": 2, "partially_verified": 1, "unverified": 0}
    worst = min((e["status"] for e in maj), key=rank.get) if maj else "unverified"
    assertion = needs_evidence({"outcome": outcome, "votes": dict(votes),
                                **({} if n * 2 > judgments else {"why": "no majority among the judgments"})}, worst)
    return {**base,
            "assertion": assertion,
            "semantic_confidence": {"level": level, "agreement": f"{n}/{judgments}", "judgments": judgments},
            "evidence": {"status": worst, "per_judgment": [e["status"] for e in evs]},
            "judgments": js, "payload_sha256": hashlib.sha256(json.dumps(body, sort_keys=True,
                                                                         default=str).encode()).hexdigest()[:16],
            "runaway_retries": sum(j.get("runaway_retries", 0) for j in js),
            "malformed_reasks": sum(j.get("malformed_reasks", 0) for j in js),
            "cost_usd": round(sum(((j["cost_usd"] or 0.0) + j.get("runaway_cost_usd", 0.0) if not j["cached"] else 0.0)
                                  + sum(d["cost_usd"] for d in j.get("malformed_discarded", [])) for j in js), 6)}
