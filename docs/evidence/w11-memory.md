# W11: owner decisions become memory (Oct 27)

**Result: built.** `semaudit decide` (fix / not-an-issue / accept), `semaudit decide-release`
(ship / ship with notes / hold) and `semaudit serve` (the Release Story with working decision buttons; the static
page shows the equivalent commands). Decisions live in the contract's `dispositions.yaml`; code in
`src/semaudit/decide/memory.py`. `rule` and `expect` decisions are planned, not built.

## What a decision is pinned to
The review it was made on (sha256), the issue signature, the exact message texts per persona, and the rule's own
content (digest). A decision is refused if the contract changed since that review. Each later review records the
decisions it applied (`manifest.memory`, with a digest), so `repro` and `verify-report` replay exactly those;
editing the recorded decisions fails verify-report.

| Decision | Next review |
|---|---|
| fix | resolved → **fix confirmed**; still there → **still open**; back after a release without it → **regressed** |
| not an issue (reason required) | exact signature + same personas + same texts → set aside onto the not-raised list with the reason; a new persona or changed copy → raised as a **variant**, saying what differs; rule changed → **stale**, does not apply |
| accept (expiry required) | conditional rule, nearest exception failed on **scope alone** → new exception with the same conditions, scoped to exactly the issue's (feature, component, surface); the decision approves that exception item. Refused where it would drop a condition or clear a universal / coherence / load rule |

## Two changes the memory needed elsewhere
- **Nearest exception.** With more than one exception, the rule engine reported the *last* one it tried, so adding
  an exception would have changed other issues' signatures. It now reports the one with the most conditions met
  (ties keep contract order), and the issue detail and the defender use that one.
- **A rule's approval no longer covers its exceptions** (each exception is approved as its own item), so accepting
  an exception does not unapprove the rule. Removing an exception only makes the contract stricter.

## Evidence
- Tests (`tests/test_capture.py`, W11 section; real captured stories, gold extraction, no model): fix confirmed /
  still open; exact set-aside, variant, stale; accept narrows to Rina's hotel banner and every other issue keeps
  its signature; refusals (Hana's condition (a), a universal rule, a missing reason, an unknown issue, a changed
  contract) record nothing; the rule digest; tampered recorded decisions; the release decision leaves the review
  untouched; the page shows decisions statically and offers forms only when served; `serve` records through the
  same path and returns 400 with the reason on a refusal. 231 tests pass. Each new guard was mutation-checked
  (7 mutations, each turns a test red).
- **Live CLI rehearsal** on a scratch copy of the contract (decisions recorded as "claude (rehearsal, not the
  owner)", not in the repo), reusing the e2e-2 / e2e-3 captures:
  - 2.4: fix the tradeoff (D-001) and Kai's conflict (D-002); U4 not an issue (D-003); accepting Hana's banner
    refused ("P1-E1 failed on a, not on scope alone"); release decision hold.
  - 2.4 → 2.4.1: tradeoff **fix confirmed**; Kai **still open**; U4 set aside; Rina raised on scope.
  - accept Rina's banner from that review → P1-E2 `{features: [fare_lock], components: [hotel], surfaces:
    [hotel_detail]}`, conditions a, b, c, expires 2026-12-31, approved. Re-review: Rina **excepted by P1-E2**; Hana,
    Raj (both 72 h boundary runs) and Raj-x stay raised with unchanged signatures.
  - verify-report: all three reviews CONSISTENT. Pages render with no errors (static and served).
  - Spend $0.125 (the defender re-ran on the P1 issues because a second exception now exists).
