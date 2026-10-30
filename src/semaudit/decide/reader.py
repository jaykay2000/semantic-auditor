"""The reader: a review mode in which the model reads SRA's context and names what is wrong (`review --reader`).

The context is what SRA builds: the parsed contract (rules, facts, features, surfaces) and every captured story of a
release, each message beside the oracle readings at that moment. The model reads it with the same prompt the
B-judge-1 benchmark froze (bench/conditions/prompts/judge_one.md), in chunks of at most `chunk` personas so a large
persona set fits. SRA then does the parts the model is not trusted with:

  evidence   every cited quote must appear, whitespace-insensitively, in the message it cites in that persona's
             captured story, and state a figure or two words. A quote found only in one other message of the
             persona, and specific (a figure and two words), is kept but marked re-pointed; any other is refused; a finding
             left with no accepted citation is not raised (it is listed in not_raised with the reason);
  grouping   one issue per wrong figure and the messages it appears in: the fact a finding names first (a contract
             fact id in its explanation) and the messages it targets or cites, by message key without the #N
             occurrence suffix (as story/align.py matches messages across releases), on its surface. Findings that
             share a (fact, message) pair are one issue, across chunks and rules, so the same email bug reported by U1 on
             the email and by U2 on the order page against the email is one issue. Relation and story findings
             group by their target. The contract's first rule among the group's is the issue's rule; the others
             are listed as "also". The issue's identity across releases is its fact and the message most personas
             cite;
  delta      matched on the anchor message and the fact (an unnamed fact matches any), and checked against the
             captures, because one reading may skip a defect the other reports. A head issue is pre_existing when a
             base issue matches, or when every quote it cites was already shown to the same persona in the same
             message in base; otherwise new. A base issue is resolved only when no head issue matches, every
             persona it reached was measured in head, its cited message is still shown, and none of its quotes is
             shown anywhere in that persona's head story; otherwise "unconfirmed", with the reason;
  severity   the rule's owner-set level, as for every other issue; the model's own rating is recorded, not used;
  confidence at most medium: no replay, no second model and no defense run on a reader issue. An issue with a
             refused or re-pointed citation is low.

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
from semaudit.relate.rules import Entry, engine_support
from semaudit.story.model import Story

TWO_SIDED = {"agree_across_surfaces", "agree_across_states"}   # a disagreement needs both messages evidenced
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


Cite = tuple  # (event_id, surface, message key without #N, quote)


def _msg(surface, key) -> tuple:
    return (surface or "", _base(key))


def check_citations(f: Finding, stories: dict[str, Story]) -> tuple[dict[str, list[Cite]], list[str], list[str]]:
    """persona -> accepted citations; the citations refused (with why); the citations re-pointed.

    A quote in the cited message (event ids can repeat in a story, so any message with that id counts) must state a
    figure or at least two words: a bare price message is quoted by its price, but "Shipping" alone says nothing.
    A quote not in the cited message is re-pointed only when it holds a figure and two words and exactly one
    message of the persona holds it ("$15.00" alone appears in dozens)."""
    found: dict[str, list[Cite]] = {}
    failed, moved = [], []
    for c in f.cited:
        s = stories.get(c.persona)
        q = _norm(c.quote)
        if s is None:
            failed.append(f"{c.persona}/{c.event_id}: no captured story for this persona")
            continue
        if not q:
            failed.append(f"{c.persona}/{c.event_id}: no quote given")
            continue
        holding = [x for x in s.events if x.kind == "message" and q in _norm(x.text)]
        same_id = [x for x in holding if x.id == c.event_id]       # ids can repeat across captures
        at = next((x for x in same_id if x.surface == f.target.surface), same_id[0] if same_id else None)
        words = len(re.findall(r"[a-z]{3,}", q))
        if at is not None and not (re.search(r"\d", q) or words >= 2):
            failed.append(f"{c.persona}/{c.event_id}: quote {c.quote[:30]!r} states no figure (in {len(holding)} "
                          f"messages)")
            continue
        if at is None:
            if len(holding) != 1 or not (re.search(r"\d", q) and words >= 2):
                failed.append(f"{c.persona}/{c.event_id}: quote " + ("in no captured message" if not holding else
                                                                     f"not in the cited message, and in {len(holding)} others"))
                continue
            at = holding[0]
            moved.append(f"{c.persona}/{c.event_id} -> {at.id}")
        cite = (at.id, at.surface, _base(at.id), c.quote)
        if cite not in found.setdefault(c.persona, []):
            found[c.persona].append(cite)
    return found, failed, moved


def group(checked: list[tuple[Finding, dict]], facts: list[str]) -> list[tuple[tuple, list[tuple[Finding, dict]]]]:
    """[(identity, [(finding, accepted citations)])]: event findings joined by a shared (fact, message), message =
    (surface, message key without #N); relation and story findings by their target."""
    out: dict[tuple, list] = {}
    events = []
    for f, found in checked:
        t = f.target
        if t.kind == "relation":
            out.setdefault(("relation", *sorted(t.features), t.decision, f.label), []).append((f, found))
        elif t.kind == "story":
            out.setdefault(("story", f.rule), []).append((f, found))
        else:
            events.append((f, found))
    parent = list(range(len(events)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    owner: dict[tuple, int] = {}
    for n, (f, found) in enumerate(events):
        fact = _fact(f, facts)
        msgs = {_msg(f.target.surface, f.target.message_key)} | {(c[1], c[2]) for cs in found.values() for c in cs}
        for m in msgs:
            node = (fact, m)
            if node in owner:
                parent[find(n)] = find(owner[node])
            else:
                owner[node] = n
    comps: dict[int, list] = {}
    for n, item in enumerate(events):
        comps.setdefault(find(n), []).append(item)
    for items in comps.values():
        fact = _fact(items[0][0], facts)
        cites: dict[tuple, set] = {}
        for f, found in items:
            for p, cs in found.items():
                for c in cs:
                    cites.setdefault((c[1], c[2]), set()).add(p)
        targets = {_msg(f.target.surface, f.target.message_key) for f, _ in items}
        anchor = (max(sorted(cites), key=lambda m: (len(cites[m]), m in targets)) if cites
                  else _msg(items[0][0].target.surface, items[0][0].target.message_key))
        out.setdefault(("event", fact, anchor), []).extend(items)
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


def build_reader_issues(findings: list[Finding], ev: ReleaseEval, contract: Contract) -> tuple[list[Issue], list[dict]]:
    """Check, group and turn the model's findings into issues. Returns (issues, not_raised rows).

    An issue's evidence is what its primary rule's findings cite. A finding under another rule in the same group
    (typically "the same figure reads differently on two surfaces") adds its citations of the issue's own messages;
    its citations of other messages are the other side of the comparison, kept as compared_with, never as
    evidence of the violation."""
    stories = {p: s for p, (s, _) in ev.results.items()}
    order = {r.id: k for k, r in enumerate(contract.rules)}
    checked, problems = [], {}
    for f in findings:
        if f.rule not in order:
            continue
        found, bad, mv = check_citations(f, stories)
        checked.append((f, found))
        problems[id(f)] = (bad, mv)          # by object: finding ids restart in every chunk
    issues, refused = [], []
    for key, items in group(checked, [x.id for x in contract.facts]):
        items.sort(key=lambda it: order[it[0].rule])
        primary = items[0][0]
        rule = contract.rule(primary.rule)
        own = {(c[1], c[2]) for f, found in items if f.rule == rule.id for cs in found.values() for c in cs}
        if key[0] == "event":
            own.add(key[2])
        evidence: dict[str, list[Cite]] = {}
        compared: dict[str, list[Cite]] = {}
        failed: list[str] = []
        moved: list[str] = []
        rated = []
        for f, found in items:
            bad, mv = problems[id(f)]
            failed += bad
            moved += mv
            rated.append(f.confidence or "low")
            for p, cs in found.items():
                for c in cs:
                    side = evidence if (f.rule == rule.id or (c[1], c[2]) in own) else compared
                    if c not in side.setdefault(p, []):
                        side[p].append(c)
        evidence = {p: cs for p, cs in evidence.items() if cs}
        if rule.check.get("must") in TWO_SIDED and items and all(f.rule == rule.id for f, _ in items):
            sides = {p: {(c[1], c[2]) for c in evidence.get(p, []) + compared.get(p, [])} for p in evidence}
            one_sided = sorted(p for p, ms in sides.items() if len(ms) < 2)
            for p in one_sided:
                failed.append(f"{p}: only one side of the comparison has an accepted quote")
                evidence.pop(p)
        others = sorted({f.rule for f, _ in items if f.rule != rule.id}, key=order.get)
        sig = ("reader", *key)
        if not evidence:
            refused.append({"persona": ",".join(sorted({p for f, _ in items for p in f.personas})), "rule": rule.id,
                            "subjects": [f.id for f, _ in items], "status": "not_raised", "label": primary.label,
                            "conditions": [], "release": ev.release,
                            "reason": "evidence check failed: " + "; ".join(failed[:5])})
            continue
        occ = []
        for p in sorted(evidence):
            ids = list(dict.fromkeys(c[0] for c in evidence[p]))
            entry = Entry(rule.id, ids[0], "violated", primary.label, note=primary.why,
                          meta={"quotes": [c[3] for c in evidence[p]],
                                "messages": sorted({(c[1], c[2]) for c in evidence[p]}),
                                "compared_with": [{"event": c[0], "quote": c[3]} for c in compared.get(p, [])]})
            also = [Entry(r, ids[0], "violated", None, note=next(f.why for f, _ in items if f.rule == r))
                    for r in others]
            occ.append(Occurrence(p, stories[p].id, ids, entry, "", also))
        named_only = sorted({p for f, _ in items for p in f.personas} - set(evidence))
        detail = []
        if failed:
            detail.append(f"{len(failed)} citation(s) refused: " + "; ".join(failed[:5]))
        if moved:
            detail.append(f"{len(moved)} citation(s) found in another message than cited: " + "; ".join(moved[:5]))
        steps = {"evidence_linked": {"result": "fail" if (failed or moved) else "pass",
                                     "detail": " · ".join(detail) or "every citation's quote is in the cited message"},
                 "reproduced": {"result": "not_run"}, "cross_model": {"result": "not_run"},
                 "defended": {"result": "not_run"}}
        model_level = max(rated, key=CONFIDENCE.index)
        level = "low" if (failed or moved) else min(model_level, "medium", key=CONFIDENCE.index)
        basis = [f"reader's own rating: {model_level}", "quotes checked against the captures"
                 + ("; some refused" if failed else "") + ("; some in another message than cited" if moved else ""),
                 "no replay, second model or defense on reader issues"]
        if named_only:
            basis.append("also named without a usable quote (not counted): " + ", ".join(named_only))
        digest = hashlib.sha1(repr(sig).encode()).hexdigest()[:8]
        what = f"{key[1] or 'unnamed-fact'}-{key[2][1]}" if key[0] == "event" else "-".join(str(x) for x in key[1:] if x)
        it = Issue(id=f"R-{ev.release}-{rule.id}-{re.sub(r'[^a-z0-9]+', '-', str(what).lower()).strip('-')[:40]}"
                      f"-{digest}",
                   signature=sig, rule=rule.id, rule_kind=rule.kind, layer=_layer(rule),
                   label=primary.label, occurrences=occ, severity=severity_of(rule, occ), why=primary.why,
                   confidence={"level": level, "basis": basis},
                   verification={"status": "unverified", "reason": "reader issue: evidence checked, not re-derived",
                                 "steps": steps})
        it.severity["factors"]["reader_rating"] = primary.severity
        it._features = sorted({x for f, _ in items for x in ([f.target.feature] if f.target.feature else
                                                               f.target.features)})
        issues.append(it)
    return issues, refused


def _layer(rule) -> str:
    """factual (a figure or a detail is wrong) or release (how the release behaves over time), as rules mode sets it.
    A universal rule whose verb the engine has no code for is read as factual: the engine's release-layer universal
    rules are named by verbs it knows (actionability, message kind), and an owner's other universal rules say what a
    figure, a total or a record must show (Spree's U3-U8). Any other kind of rule is release."""
    if rule.check.get("must") in FACTUAL_CHECKS:
        return "factual"
    if rule.kind == "universal" and not engine_support(rule)[0]:
        return "factual"
    return "release"


def _specific(q: str) -> bool:
    q = _norm(q)
    return bool(re.search(r"\d", q)) and len(re.findall(r"[a-z]{3,}", q)) >= 2


def _quotes_shown(o: Occurrence, story, *, same_message: bool) -> bool:
    """Every quote of this occurrence is in `story`: in the same message (surface + key), or, when
    same_message is False, anywhere for a specific quote (a figure and two words). A bare figure is only looked for
    in the same message: "$43.19" may be a correct total elsewhere."""
    msgs = {tuple(m) for m in o.entry.meta.get("messages", [])}
    own = [_norm(e.text) for e in story.events if e.kind == "message" and (e.surface or "", _base(e.id)) in msgs]
    every = [_norm(e.text) for e in story.events if e.kind == "message"]
    quotes = o.entry.meta.get("quotes", [])
    return bool(quotes) and all(any(_norm(q) in t for t in (every if (not same_message and _specific(q)) else own))
                                for q in quotes)


def _has_messages(o: Occurrence, story) -> bool:
    msgs = {tuple(m) for m in o.entry.meta.get("messages", [])}
    return any(e.kind == "message" and (e.surface or "", _base(e.id)) in msgs for e in story.events)


def _matches(a: Issue, b: Issue) -> bool:
    """Same issue across releases: same relation/story target, or same anchor message with the same fact (a fact
    one reading left unnamed matches any)."""
    if a.signature[1] != "event" or b.signature[1] != "event":
        return a.signature == b.signature
    fa, fb = a.signature[2], b.signature[2]
    return a.signature[3] == b.signature[3] and (fa == fb or fa is None or fb is None)


def reader_delta(head: list[Issue], base: list[Issue], head_ev: ReleaseEval,
                 base_ev: ReleaseEval) -> tuple[list[Issue], list[Issue]]:
    """Mark head issues new / pre_existing; return (resolved, unconfirmed) base issues. Every base issue ends in
    exactly one place: named in a matching head issue's delta_basis, resolved, or unconfirmed."""
    matched: set[int] = set()
    for i in head:
        bs = [b for b in base if _matches(i, b)]
        matched |= {id(b) for b in bs}
        if bs:
            i.delta, i.delta_basis = "pre_existing", "also in base as " + ", ".join(b.id for b in bs)
            continue
        old = [o for o in i.occurrences if o.persona in base_ev.results
               and _quotes_shown(o, base_ev.results[o.persona][0], same_message=True)]
        if old and len(old) == len(i.occurrences):
            qs = [q for o in i.occurrences for q in o.entry.meta.get("quotes", [])]
            bare = sum(not _specific(q) for q in qs)
            i.delta, i.delta_basis = "pre_existing", ("every quote was already shown to the same persona in the "
                                                      "same message in base; the base reading did not report it"
                                                      + (f" ({bare} of {len(qs)} quotes are bare figures, weaker "
                                                         f"evidence)" if bare else ""))
        else:
            i.delta, i.delta_basis = "new", "no matching base issue, and the quoted text is not in base"
    resolved, unconfirmed = [], []
    for b in base:
        if id(b) in matched:
            continue
        missing = [p for p in b.personas if p not in head_ev.results]
        here = [o for o in b.occurrences if o.persona in head_ev.results]
        still = [o.persona for o in here if _quotes_shown(o, head_ev.results[o.persona][0], same_message=False)]
        gone = [o.persona for o in here if not _has_messages(o, head_ev.results[o.persona][0])]
        if missing:
            b.delta, b.delta_basis = "not_measured_in_head", "head not measured for " + ", ".join(missing)
            unconfirmed.append(b)
        elif still:
            b.delta, b.delta_basis = "unconfirmed", ("the quoted text is still shown in head to " + ", ".join(still)
                                                     + "; the head reading did not report it")
            unconfirmed.append(b)
        elif gone:
            b.delta, b.delta_basis = "unconfirmed", ("the cited message is not in head in this form for "
                                                     + ", ".join(gone) + " (reworded or removed): fixed or not "
                                                     "cannot be told from the text")
            unconfirmed.append(b)
        else:
            b.delta, b.delta_basis = "resolved", ("no matching head issue; every affected persona measured; the "
                                                  "cited message is still shown and no longer holds the quoted text")
            resolved.append(b)
    return resolved, unconfirmed
