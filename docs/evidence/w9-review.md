# W9: issues, verification, policy, review.json, repro (2026-10-26)

**Result: ACCEPTED.** The first end-to-end path runs on Northbound:
`semaudit review --contract examples/northbound/contract --base 2.3 --head 2.4 --max-usd 1` captures both
releases, builds stories, evaluates the rules, groups issues, re-captures the affected personas, verifies
every issue, applies the release policy and writes `runs/<id>/review-2.3-2.4.json` (14 s end to end from
fresh captures; model calls cached by content). `semaudit repro <issue-id>` re-captures and re-finds every
cited moment.

## 2.3 → 2.4
Recommendation **Hold** (policy row 1: "an open issue is critical, verified, with confidence at least medium").

| Issue | Personas | Severity | Confidence | Verification | Delta |
|---|---|---|---|---|---|
| P2 unexplained tradeoff (Price Watch × Fare Lock) | family, maya, sam_alex | critical | high | verified | new |
| P1 urgency, (a) departs > 72 h | hana, raj_72h_30s, raj_72h_1m | critical | high | verified | new |
| U1 false seat count | omar | major | high | verified | new |
| U2 fee shown ≠ charged | sam_alex | major | high | verified | new |
| P1 urgency, (c) tradeoff not explained | raj_x | major | high | verified | new |
| P2 conflict (book now ⟂ wait) | kai | major | high | verified | new |
| U3 stale guidance after booking | family, maya, maya_r | minor | high | verified | new |
| U4 second-guessing after purchase | family, maya, maya_r | minor | high | verified | new |
| P3 three outbound contacts in 24 h | family, maya, maya_r | minor | high | verified | new |

Not raised (5): Lena and Maya-R (explained tradeoff, with the reconciler and time), Raj, Raj@72h and Kai's P1
(exception P1-E1, every condition met). Severity: each rule's owner-set base level, raised one level by the
policy's escalation ("two or more travellers before they decide").

## 2.4 → 2.4.1
The three fixes come back **resolved** (P2 tradeoff and conflict, U2, U3, P3); U4, U1 and both P1 groups are
**pre_existing**; Rina is **new**: "urge book_now on when_to_book; nearest exception P1-E1 does not apply: scope
(fare_lock on a hotel hotel detail; the exception covers features: fare_lock / components: flight / surfaces:
fare_detail, checkout)", with a, b and c all met.

## The verifier had to be made to bite
`scripts/w9_falsify.py` plants four bad issues; all four must be rejected.

| Planted | First version | Now |
|---|---|---|
| a real issue with an altered quote | failed (evidence_unresolved) | same |
| a real issue whose event is missing from the re-capture | failed (not_reproducible) | same |
| a P2 on Lena, whose tradeoff was reconciled in time | failed (disputed), confidence low | same |
| a U4 ("second-guessing") on a plain booking confirmation | **verified, confidence high** | failed, confidence low |

Two defects behind the miss, both fixed: the cross-check compared the second model's reading with the first
model's reading (both said "information", so they "agreed") instead of re-deriving the violation from the
second reading; and the defender's `stands` flag contradicted its own argument. The cross-check now re-runs
the rules on the other model's reading and passes only if the same violation (and P2 label) comes out; the
defender writes its defense first and then answers `defense_succeeds`.

Also fixed during W9: Muse Spark 1.2 (low effort) put `lock_fare` under the `fare_type` decision. The contract
gives each action exactly one decision, so the decision is now derived from the action in code and a
contradicting model decision is overruled and recorded (`normalized`). The cross-check compares only the
fields a rule reads, and the oracle check only the rule's own fact types. Features a release does not have
(Fare Lock in 2.3, hotels before 2.4.1) are recorded as not offered, not as unmeasured.

## Tests
Offline: severity moves with reach alone, confidence with unknown validity alone, verification with a skipped
reproduction alone; the policy changes with each field alone; failure kinds; measured vs interpreted evidence.
From real captures with gold extraction: the 2.4 issue set, personas and severities exactly; "one event, one
issue" (Omar: U1 first, P1 carried); the 2.4.1 delta. Five mutation checks turn the suite red.
W9 spend: about $0.79 (development and the falsifiability runs included).

## Limits and open questions (for the next audit)
- On 2.4.1 the model treats the reconcile message ("if you can move your dates, wait; if not, locking protects
  this price") as also resolving Kai's *book now ⟂ wait* conflict. Arguable; worth an adjudicator's view.
- Both models are Muse Spark (1.3 and 1.2): every cross-check records "reduced independence".
- Text deadlines are not read yet (validity ends only by precondition, lifetime or supersession).
