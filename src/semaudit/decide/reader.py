"""The reader: a review mode in which the model reads SRA's context and names what is wrong (`review --reader`).

The context is what SRA builds: the parsed contract (rules, facts, features, surfaces) and every captured story of a
release, each message beside the oracle readings at that moment. The model reads it with the same prompt the
B-judge-1 benchmark froze (bench/conditions/prompts/judge_one.md), in chunks of at most `chunk` personas so a large
persona set fits. SRA then does the parts the model is not trusted with:

  evidence   every cited quote must appear, whitespace-insensitively, in the text of the event it cites in that
             persona's captured story. A quote found only in another message of the same persona is kept but
             marked re-pointed; a quote found nowhere is dropped; a finding left with no citation is not raised (it
             is listed in not_raised with the reason);
  grouping   one issue per wrong figure and the messages it appears in: the fact a finding names first (a contract
             fact id in its explanation) and the messages it targets or cites, by message key without the #N
             occurrence suffix (as story/align.py matches messages across releases). Findings that share a
             (fact, message) pair are one issue, across chunks and rules, so the same email bug reported by U1 on
             the email and by U2 on the order page against the email is one issue. Relation and story findings
             group by their target. The contract's first rule among the group's is the issue's rule; the others
             are listed as "also". The issue's identity across releases is its fact and the message most personas
             cite;
  delta      decided on the message, and checked against the captures, because one reading may name a fact the
             other leaves unnamed, or skip a defect the other reports. A head issue is pre_existing when base has
             an issue on the same message, or when every quote it cites was already shown to the same persona in
             base, in the same message (the base reading missed it); otherwise new. A base issue is resolved only
             when head has no issue on its message, every persona it reached was measured in head, and its quotes
             are no longer shown to that persona in that message; otherwise it is "unconfirmed", with the reason;
  severity   the rule's owner-set level, as for every other issue; the model's own rating is recorded, not used;
  confidence at most medium: no replay, no second model and no defense run on a reader issue. An issue whose
             citations were only partly found is low.

No extraction runs in this mode: the reader reads raw message text with the oracle readings, which is the context
that measured best (docs/evidence/w13b-sealed-followups.md).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from semaudit.bench import judge
from semaudit.bench.findings import Finding
from semaudit.contract.schema import CONFIDENCE, Contract
from semaudit.decide.issues import FACTUAL_CHECKS, Issue, Occurrence, severity_of
from semaudit.decide.pipeline import ReleaseEval, load_release
from semaudit.models.router import Router
from semaudit.relate.rules import Entry
from semaudit.story.model import Story

PROMPT = "judge_one"          # the frozen benchmark prompt, reused verbatim so the measured context is what ships


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def _base(key: str | None) -> str:
    return (key or "").split("#")[0]


def _fact(f: Finding, facts: list[str]) -> str | None:
    """The contract fact the finding's explanation names first, if any."""
    why = re.sub(r"[\s-]+", "_", (f.why or "").lower())          # "line amount", "Line-amount" -> line_amount
    hits = [(m.start(), x) for x in facts if (m := re.search(rf"(?<![a-z0-9]){re.escape(x)}(?![a-z0-9])", why))]
    return min(hits)[1] if hits else None


def group(findings: list[Finding], facts: list[str]) -> list[tuple[tuple, list[Finding]]]:
    """[(identity, findings)]: event findings joined by shared (fact, message); others by their target."""
    out: dict[tuple, list[Finding]] = {}
    events = []
    for f in findings:
        t = f.target
        if t.kind == "relation":
            out.setdefault(("relation", *sorted(t.features), t.decision, f.label), []).append(f)
        elif t.kind == "story":
            out.setdefault(("story", f.rule), []).append(f)
        else:
            events.append(f)
    parent = list(range(len(events)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    owner: dict[tuple, int] = {}
    for n, f in enumerate(events):
        fact = _fact(f, facts)
        for k in {_base(f.target.message_key)} | {_base(c.event_id) for c in f.cited}:
            node = (fact, k)
            if node in owner:
                parent[find(n)] = find(owner[node])
            else:
                owner[node] = n
    comps: dict[int, list[Finding]] = {}
    for n, f in enumerate(events):
        comps.setdefault(find(n), []).append(f)
    for fs in comps.values():
        fact = _fact(fs[0], facts)
        cites: dict[str, set] = {}
        for f in fs:
            for c in f.cited:
                cites.setdefault(_base(c.event_id), set()).add(c.persona)
        targets = {_base(f.target.message_key) for f in fs}
        anchor = (max(sorted(cites), key=lambda k: (len(cites[k]), k in targets)) if cites
                  else _base(fs[0].target.message_key))
        out.setdefault(("event", fact, anchor), []).extend(fs)
    for key in [k for k in out if k[0] == "event" and k[1] is None]:
        named = [k for k in out if k[0] == "event" and k[1] is not None and k[2] == key[2]]
        if len(named) == 1:                       # "the same limit reads differently" beside "limit_401k is wrong"
            out[named[0]].extend(out.pop(key))
    return list(out.items())


def read_release(run_dir: Path, release: str, contract: Contract, router: Router, *, chunk: int = 11,
                 fresh: bool = False) -> tuple[ReleaseEval, list[Finding], dict]:
    """Every measured story of `release`, read in chunks. Returns the release (stories with no rule entries, so the
    page can still show each persona), the model's findings, and the reading's accounting."""
    episodes, not_measured, stories = load_release(run_dir, release, contract)
    ids = sorted(stories)
    findings, acct = [], {"chunks": 0, "calls": 0, "cached_calls": 0, "spent_usd": 0.0, "dropped": [],
                          "truncated": False}
    tag = router.tag
    for n in range(0, len(ids), chunk):
        part = {k: stories[k] for k in ids[n:n + chunk]}
        fs, dropped = judge.judge_one(part, contract, router, release=release, fresh=fresh,
                                      run=f"reader{n // chunk + 1}")
        findings += fs.findings
        acct["chunks"] += 1
        acct["calls"] += fs.calls or 0
        acct["cached_calls"] += fs.cached_calls or 0
        acct["spent_usd"] += fs.cost_usd or 0.0
        acct["dropped"] += dropped
        acct["truncated"] = acct["truncated"] or fs.truncated
    router.tag = tag
    results = {p: (s, []) for p, s in stories.items()}
    return ReleaseEval(release, episodes, results, not_measured), findings, acct


def check_citations(f: Finding, stories: dict[str, Story]) -> tuple[dict[str, list[str]], list[str]]:
    """persona -> event ids whose captured text holds the cited quote; the citations found nowhere; and the
    citations whose quote is in another message of that persona than the one cited (re-pointed there)."""
    found: dict[str, list[str]] = {}
    failed, moved = [], []
    for c in f.cited:
        s = stories.get(c.persona)
        q = _norm(c.quote)
        e = next((x for x in s.events if x.id == c.event_id), None) if s else None
        at = c.event_id
        if s is None:
            failed.append(f"{c.persona}/{c.event_id}: no captured story for this persona")
            continue
        if not q:
            failed.append(f"{c.persona}/{c.event_id}: no quote given")
            continue
        if e is None or e.kind != "message" or q not in _norm(e.text):
            other = next((x for x in s.events if x.kind == "message" and q in _norm(x.text)), None)
            if other is None:
                failed.append(f"{c.persona}/{c.event_id}: quote not in any captured message")
                continue
            moved.append(f"{c.persona}/{c.event_id} -> {other.id}")
            at = other.id
        found.setdefault(c.persona, [])
        if at not in found[c.persona]:
            found[c.persona].append(at)
    return found, failed, moved


def build_reader_issues(findings: list[Finding], ev: ReleaseEval, contract: Contract) -> tuple[list[Issue], list[dict]]:
    """Group, check and turn the model's findings into issues. Returns (issues, not_raised rows)."""
    stories = {p: s for p, (s, _) in ev.results.items()}
    order = {r.id: k for k, r in enumerate(contract.rules)}
    issues, refused = [], []
    for key, fs in group([f for f in findings if f.rule in order], [x.id for x in contract.facts]):
        fs.sort(key=lambda f: order[f.rule])
        primary = fs[0]
        rule = contract.rule(primary.rule)
        evidence: dict[str, list[str]] = {}
        quotes: dict[str, list[str]] = {}
        failed: list[str] = []
        moved: list[str] = []
        rated = []
        for f in fs:
            found, bad, mv = check_citations(f, stories)
            failed += bad
            moved += mv
            rated.append(f.confidence or "low")
            for c in f.cited:
                if c.persona in found and _norm(c.quote):
                    quotes.setdefault(c.persona, []).append(c.quote)
            for p, evs in found.items():
                evidence.setdefault(p, [])
                evidence[p] += [x for x in evs if x not in evidence[p]]
        others = sorted({f.rule for f in fs if f.rule != rule.id}, key=order.get)
        sig = ("reader", *key)
        if not evidence:
            refused.append({"persona": ",".join(sorted({p for f in fs for p in f.personas})), "rule": rule.id,
                            "subjects": [f.id for f in fs], "status": "not_raised", "label": primary.label,
                            "conditions": [], "reason": "evidence check failed: " + "; ".join(failed[:5])})
            continue
        occ = []
        for p in sorted(evidence):
            entry = Entry(rule.id, evidence[p][0], "violated", primary.label, note=primary.why,
                          meta={"quotes": quotes.get(p, [])})
            also = [Entry(r, evidence[p][0], "violated", None, note="also named by the reader") for r in others]
            occ.append(Occurrence(p, stories[p].id, evidence[p], entry, "", also))
        named_only = sorted({p for f in fs for p in f.personas} - set(evidence))
        detail = []
        if failed:
            detail.append(f"{len(failed)} citation(s) found in no captured message: " + "; ".join(failed[:5]))
        if moved:
            detail.append(f"{len(moved)} citation(s) found in another message than cited: " + "; ".join(moved[:5]))
        steps = {"evidence_linked": {"result": "fail" if (failed or moved) else "pass",
                                     "detail": " · ".join(detail) or "every citation's quote is in the cited message"},
                 "reproduced": {"result": "not_run"}, "cross_model": {"result": "not_run"},
                 "defended": {"result": "not_run"}}
        model_level = max(rated, key=CONFIDENCE.index)
        level = "low" if failed else min(model_level, "medium", key=CONFIDENCE.index)
        basis = [f"reader's own rating: {model_level}", "quotes checked against the captures"
                 + ("; some found in no message" if failed else "") + ("; some in another message than cited"
                                                                      if moved else ""),
                 "no replay, second model or defense on reader issues"]
        if named_only:
            basis.append("also named without a quote (not counted): " + ", ".join(named_only))
        digest = hashlib.sha1(repr(sig).encode()).hexdigest()[:8]
        what = f"{key[1] or 'unnamed-fact'}-{key[2]}" if key[0] == "event" else "-".join(str(x) for x in key[1:] if x)
        it = Issue(id=f"R-{ev.release}-{rule.id}-{re.sub(r'[^a-z0-9]+', '-', str(what).lower()).strip('-')[:40]}"
                      f"-{digest}",
                   signature=sig, rule=rule.id, rule_kind=rule.kind,
                   layer="factual" if rule.check.get("must") in FACTUAL_CHECKS else "release",
                   label=primary.label, occurrences=occ, severity=severity_of(rule, occ), why=primary.why,
                   confidence={"level": level, "basis": basis},
                   verification={"status": "unverified", "reason": "reader issue: evidence checked, not re-derived",
                                 "steps": steps})
        it.severity["factors"]["reader_rating"] = primary.severity
        it._features = sorted({x for f in fs for x in ([f.target.feature] if f.target.feature else
                                                         f.target.features)})
        issues.append(it)
    return issues, refused


def _shown(o: Occurrence, story) -> bool:
    """Every quote of this occurrence is in the same message (by message key, #N suffix aside) in `story`."""
    keys = {_base(x) for x in o.events}
    texts = [_norm(e.text) for e in story.events if e.kind == "message" and _base(e.id) in keys]
    quotes = o.entry.meta.get("quotes", [])
    return bool(quotes) and bool(texts) and all(any(_norm(q) in t for t in texts) for q in quotes)


def _anchor(i: Issue):
    return i.signature[3] if i.signature[1] == "event" else i.signature


def reader_delta(head: list[Issue], base: list[Issue], head_ev: ReleaseEval,
                 base_ev: ReleaseEval) -> tuple[list[Issue], list[Issue]]:
    """Mark head issues new / pre_existing; return (resolved, unconfirmed) base issues (see the module notes)."""
    base_at = {_anchor(i): i for i in base}
    head_at = {_anchor(i): i for i in head}
    for i in head:
        b = base_at.get(_anchor(i))
        if b is not None:
            i.delta, i.delta_basis = "pre_existing", f"base has an issue on the same message: {b.id}"
            continue
        old = [o for o in i.occurrences if o.persona in base_ev.results
               and _shown(o, base_ev.results[o.persona][0])]
        if old and len(old) == len(i.occurrences):
            i.delta, i.delta_basis = "pre_existing", ("every quote was already shown to the same persona in base; "
                                                      "the base reading did not report it")
        else:
            i.delta, i.delta_basis = "new", "no base issue on this message, and the quoted text is new in head"
    resolved, unconfirmed = [], []
    for b in base:
        h = head_at.get(_anchor(b))
        missing = [p for p in b.personas if p not in head_ev.results]
        still = [o.persona for o in b.occurrences if o.persona in head_ev.results
                 and _shown(o, head_ev.results[o.persona][0])]
        if h is not None:
            continue                                  # the head issue carries it as pre_existing
        if missing:
            b.delta, b.delta_basis = "not_measured_in_head", "head not measured for " + ", ".join(missing)
            unconfirmed.append(b)
        elif still:
            b.delta, b.delta_basis = "unconfirmed", ("the quoted text is still shown in head to " + ", ".join(still)
                                                     + "; the head reading did not report it")
            unconfirmed.append(b)
        else:
            b.delta, b.delta_basis = "resolved", ("no head issue on this message, every affected persona measured, "
                                                  "and none of the quoted text is still shown")
            resolved.append(b)
    return resolved, unconfirmed
