# Second external audit: what was fixed, and the evidence (Oct 26)

The audit raised 3 P0 and 5 P1 findings. All were reproduced against the code before fixing. Owner rulings
(Oct 26): drop count-based severity escalation; the owner records approvals themself; tighten the auditor on
Kai rather than change the app copy. Also done: the core was generalized so other apps (Finablo next) need no
core change.

| Finding | Fix | Evidence |
|---|---|---|
| P0 resolved-issue repro checked nothing | repro reads `base_events` for resolved issues, fails on an unrecorded event or zero checks, and re-derives the finding from a fresh capture (same signature, rule, severity, personas; a resolved issue must also be absent from fresh head) | `tests/test_repro.py`; live: U3 (resolved) now checks 3 events, re-derives on 2.4, absent on 2.4.1 |
| P0 page said "owner-approved" | the badge reads each rule's real approval status; `review` gives only a **provisional** answer until every contract item (now 43, incl. rubric and subject) is approved at its current content | `tests/test_fail_closed.py`, page test |
| P0 "could not measure" could become Ship or Resolved | unread oracles and missing episodes make a persona unmeasured; an absent issue is resolved only if every persona it reached was measured in head; `not_measurable` outcome, exit 2 | `tests/test_fail_closed.py` (each guard mutation-checked) |
| P1 Kai's conflict "resolved" on 2.4.1 | the interpreter is told each candidate's action and must list which actions a reconciler addresses; code rejects a reconciler that does not address both actions of a pair | new fixture `kai_241`; W1b 17/17 × 5; W8 32/32 × 5 with Kai 2.4.1 graded |
| P1 severity from fixture multiplicity; timing bug | escalation removed; severity is the rule's owner-set level; tested-persona counts before/after the decision recorded per occurrence | `tests/test_issues.py` |
| P1 "verified, high" stronger than established | cross-check and defense run on every occurrence; same-family agreement capped at medium; the defense is structured (named ground) and adjudicated by code against what was measured | `tests/test_issues.py` (adjudication); `scripts/w9_falsify.py` 5/5 incl. a false occurrence in a real group |
| P1 evidence incomplete as an exported artifact | review manifest (contract and adapter files, episodes, code revision, models, prompt digests, verifier settings, spend cap, all by digest); `semaudit verify-report`; screenshots hashed | live: both reviews CONSISTENT; a tampered copy fails with 3 named differences; repro refuses a changed rubric (exit 2) |
| P1 storyboard beats missing; no LICENSE | LICENSE (Apache-2.0); README license and model claims corrected. W11 / W13b / W14 remain planned work | — |

## Live results after the fixes (Muse Spark only; Meta spend this round $2.86, total $7.76)

- **W1b:** 17 hand-authored stories × 5 fresh runs exact; all stubs fail ($0.88).
- **W8:** 32 real captured stories × 5 fresh runs exact (18 against fixtures, 14 negative controls); all stubs fail ($0.54).
- **2.3 → 2.4** (`runs/e2e-2`): 9 issues, all verified, confidence medium (capped: one model family). Outcome
  **provisional**; the policy would say **ship with notes** (row 4), because with escalation removed nothing is critical.
  *Superseded Oct 27:* the owner set P2 to `critical`; regenerated from cache at $0, the 2.4 policy now says **hold**
  (row 1: both P2 issues critical, verified, medium). On 2.4.1 Kai's P2 is critical but partially verified, so it
  says **needs owner review** (row 2). Both reviews pass `semaudit verify-report`.
- **2.4 → 2.4.1** (`runs/e2e-3`): 4 issues resolved (U2, P2 tradeoff, U3, P3); Rina raised new on scope; Kai's
  conflict pre-existing, **partially verified, low confidence**: the defender (Muse Spark 1.2) argues the reconcile
  message covers "Book now", the interpreter (1.3) says it does not on 5/5 runs. The policy would say needs owner review.
- **verify-report:** both CONSISTENT. **repro:** hero P2 and resolved U3 reproduce; contract change refused.

## What the per-occurrence checks found first

Running the defense on every occurrence (instead of the first) exposed a weak defender: it "won" on true P1
issues by arguing that "Book now" is a standard call to action and that P1 permits sharing inventory, both
contradicting the contract's own classification. The defense now names its ground, and code overrules claims
that contradict measured data: a data condition claimed met that was measured not met; a disputed reading both
models share; a reconciler that is late or does not address both actions; a scope argument against a rule that
code applies from the contract's definitions.

## Open, for the owner

1. **Approve the contract** (`semaudit contract review examples/northbound/contract`, then approve): until then every
   recommendation is provisional.
2. **P2's severity:** ~~it is `major`~~ ~~decided Oct 27: `critical`~~ **decided Oct 27 (later): per label** (owner): `conflict` critical, `unexplained_tradeoff` major. 2.4 still says hold, now fired by Kai's conflict; Maya's tradeoff is major. P1(a) stays `major`. See [w11b-severity-and-page.md](w11b-severity-and-page.md).
3. **Kai on 2.4.1:** a short blind human judgement of whether the reconcile message reconciles "wait" against
   "Book now".
