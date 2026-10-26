# 7. Implementation plan (prioritized)

Building period **Tue Oct 27 – Wed Nov 4**. Submission is due 9 PM ET; our internal deadline is **12 PM ET, Nov 4**.

How work runs: brainstorming, planning, critique, design, development and QA all happen in Claude Code sessions. Implementation agents work in their own worktrees. Model calls for the auditor itself use the Meta credits ($150, with a spend limit set).

## The minimum compelling version (MCV)

The MCV is everything the demo storyboard needs to be true ([06-demo-vision.md](06-demo-vision.md)):

1. **Northbound** 2.3 / 2.4 / 2.4.1, with persona and clock hooks, feature attribution and oracles ([examples/northbound](../examples/northbound/README.md)).
2. **Contract schema**, covering principles with conditions and scoped exceptions, features, decisions, personas with state, scenarios, facts and oracles, rules and release policy, plus a hand-written Northbound reference contract.
3. **Capture**: a scenario runner (simulated time) producing episodes and state snapshots.
4. **Evidence**: extraction of messages, directives and claims, with feature attribution.
5. **Stories**: time-ordered events, base ↔ head alignment and delta.
6. **Relations**: code generators, model interpretation, and exception evaluation (data conditions in code, soft conditions judged).
7. **Issues**: severity, confidence and verification as three separate fields; a verifier; a policy-based recommendation; a rejected list.
8. **Release Story UI** (the hero screen), plus `sra repro`.
9. **Memory**: dispositions, scoped exceptions and the 2.4.1 re-review.
10. **Onboarding (demo depth)**: voice note → drafted P1 / P1-E1 → review page → approved contract.
11. **Benchmark**: a sealed fixture, B-explore / B-judge / B-repeat, scoring and adjudication ([08-evaluation.md](08-evaluation.md)).
12. **Finablo**: a contract from dated inputs, with R1 (and R2 if it survives adjudication).

**Not in the MCV:** autonomous mapping of an unknown app (beyond a recorded walk with journey repair), SAM 3.1, iOS, a GitHub Action, hosted multi-user service.

## Work items, in priority order

| P | ID | Work item | Depends on | Day |
|---|---|---|---|---|
| **P0** | W0 | Foundation: these docs coherent; open decisions in decisions.md settled; one critic pass over the docs | — | Oct 26 |
| **P0** | W1 | **Model access, verified by calls, not assumed**. Muse Spark: latest official ID, image input, structured output, tool calling, Standard vs Contributor endpoints, real token costs on a sample capture. Muse Spark Open on Modal and/or Baseten. Muse Voice Transcribe | credits | Oct 27 AM |
| **P0** | W2 | Northbound 2.3 with the persona and clock hooks, oracles and `data-feature` attribution | — | Oct 27 |
| **P0** | W3 | Contract schema (Pydantic) + Northbound reference contract (P1–P4, P1-E1, decisions, scenarios) | — | Oct 27–28 |
| **P0** | W10a | **Release Story design**: design spec → wireframe → **owner approval** (it gates W10b) | W3 shape | Oct 27–28 |
| **P0** | W4 | Scenario runner: episodes, captures, state snapshots, journey repair | W2, W3 | Oct 28 |
| **P0** | W5 | Northbound 2.4 and 2.4.1 | W2 | Oct 28 |
| **P0** | W6 | Extraction: messages, directives, claims, attribution; cache; ledger | W1, W4 | Oct 28–29 |
| **P0** | W7 | Stories, alignment, delta | W6 | Oct 29 |
| **P0** | W8 | Generators, interpretation, exception evaluation, `model_open` pass | W7 | Oct 29–30 |
| **P0** | W9 | Issues: severity, confidence, verification; verifier; release policy; rejected list; `sra repro` | W8 | Oct 30 |
| **P0** | W10b | Release Story UI build (to the approved wireframe) | W10a, W9 | Oct 30–31 |
| **P0** | W11 | Dispositions → memory; 2.4.1 re-review | W9 | Oct 31 |
| **P1** | W12 | Onboarding at demo depth: voice → principles draft → review page. A demo enhancement, not a prerequisite; the core runs on the written draft contract from W3 | W1, W3 | Nov 1–2 |
| | | **Core feature freeze: Oct 31, end of day** | | |
| **P1** | W13a | **Sealed benchmark** (a separate session): bench-01…06 + ground truth outside the repo; hashes committed to `bench/FROZEN.md` | W2 (2.3 exists) | Oct 28–31 |
| **P1** | W13b | Baselines B-explore / B-judge / B-repeat; prompts frozen on 2.4; scoring; ablations; adjudication sheet | W9, W13a | Nov 1 |
| **P1** | W14 | Finablo: dated inputs, contract, owner review, R1 + R2 runs, adjudication | W9, W12 | Nov 2 |
| **P0** | W15 | Packaging: README quickstart, `sra demo`, static hosted report, license, public repo (on the owner's word) | all P0 | Nov 3 |
| **P0** | W16 | Video: record, review against the storyboard, re-record; submit | W15 | Nov 3–4 |
| **P2** | — | Autonomous mapping of unknown apps · SAM 3.1 grounding · iOS adapter · GitHub Action | — | after |

**Critical path:** W1 → W4 → W6 → W7 → W8 → W9 → W10b → W16. Its riskiest link is W8, the relation interpretation. W8 gets one day of slack, which is the reason the freeze is Oct 31 and not Nov 1.

## Quality gates per work item

- Each item gets its own tests. Guards are mutation-checked: delete the code a test guards, and the test must go red.
- W6 is accepted when directive extraction on the 2.4 narrative captures matches the reference labels on ≥ 90% of directives (decision + action + urgency).
- W8 is accepted when, on the narrative fixture, **every** narrative negative control (NC1–NC6) is *not* raised and every seeded narrative issue is raised. This is development evidence, not a benchmark claim.
- W9 is accepted when severity, confidence and verification can each be shown to change independently. Test cases: high severity with low confidence; high confidence with an unverified status.
- W10b is accepted when a viewer who has not heard the narration can state the four things in the screen spec. The check: the owner watches a silent screen recording.

## Budget (Meta $150, plus any Modal/Baseten credits)

| Item | Cap |
|---|---|
| A full 2.3 → 2.4 review (8 personas, ~2 scenarios, 2 releases): extraction mostly cached after the first run | ≤ $3 per cold run |
| Development iterations | ≤ $30 |
| B-judge: 6 bench releases × 3 runs | ≤ $15 |
| B-explore: 3 bench releases × 3 runs, each capped at $3 | ≤ $27 |
| Auditor on bench (6 × 3) + ablations | ≤ $25 |
| Finablo runs | ≤ $10 |
| Reserve | ≥ $40 |

The Standard-mode price for Muse Spark ($1.25 / $4.25 per million input / output tokens) is to be re-measured in W1 on real captures, because images and reasoning tokens dominate. Every run takes `--max-usd`. If open-weights hosting credits are not granted, the extractor and defender roles move to Muse Spark (with the Contributor endpoint for fictional Northbound data only), and the open-weights bonus is dropped. The demo is unaffected.

## Risks

| Risk | Mitigation |
|---|---|
| Relation interpretation is unreliable (W8) | Generators narrow it to small, well-typed candidates; the schema forces a label plus reasons; the narrative controls catch regressions; cross-model check |
| Directive extraction mislabels decisions or actions | contract vocabulary constraint; `action: other` becomes an owner question; two-model agreement feeds confidence |
| Real apps lack a clock hook | report time-triggered surfaces as *not measured*; Northbound has one; for Finablo, use its existing dev and cron endpoints locally only |
| The baseline does as well as the auditor on judgment | that is a legitimate result; E1 and E3 measure coverage and reproducibility separately; we publish what we find |
| The benchmark is seen as self-graded | separate seeding session, frozen hashes, negative controls, owner plus independent adjudication, stated limitation |
| Finablo R2 fails adjudication | R1 is the real-product validation; the video says the experience-level capability is shown on Northbound |
| Disqualification over provenance | provenance ledger, on-screen labels, no Finablo code in the repo |
| Video crunch | W16 starts Nov 3 morning regardless |

## Cut order

1. B-explore is reduced to 2 bench releases.
2. Ablations are reduced to no-exceptions and no-verifier.
3. The 2.4.1 hotel-scope moment is cut (fixed → resolved is kept).
4. Finablo R2 is cut.
5. Onboarding drops to a typed interview (the transcript step is dropped).

**Never cut:** Maya's story, Raj's exception, repro, the honest baseline panel, Finablo R1.
