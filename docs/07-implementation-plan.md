# 7. Implementation plan (prioritized)

The building period runs **Tue Oct 27 – Wed Nov 4**. Submission is due at 9 PM ET; our internal deadline is **12 PM ET on Nov 4**.

How the work runs:
- Brainstorming, planning, critique, design, development and QA all happen in Claude Code sessions.
- Implementation agents work in their own worktrees.
- Model calls made by the auditor itself use the Meta credits ($150, with a spend limit set).

## Status

| Item | State | Evidence |
|---|---|---|
| W0 | done: docs, critic pass, D11 approved | `docs/decisions.md` |
| W1 | done: Muse Spark 1.3 / 1.2, structured output, images, tools verified ($0.06) | [evidence/w1-model-access.md](evidence/w1-model-access.md) |
| W1b | **accepted**: 15 stories × 5 fresh runs exact; all stubs fail | [evidence/w1b-semantic-core.md](evidence/w1b-semantic-core.md) |
| W3a | done: rule, decision and feature schema; Northbound contract | `examples/northbound/contract/` |
| W3b | **built**: surfaces, oracles, facts, derived-state model (moved out of the core), personas, scenarios, release policy (exhaustive, every row reachable), app hooks; validator; hash-pinned approvals; review page + `semaudit contract check/review/approve` | `src/semaudit/contract/`, `tests/test_contract.py` |
| W10a | **done**: spec + wireframe approved by the owner (2026-10-26); gates W10b | [design/release-story.md](design/release-story.md) |
| W2 | **built**: Northbound 2.3 with release/feature plugins, simulated clock, test hooks, oracles, markers, file sinks; NC6 works end to end ($0 of Meta budget) | `examples/northbound/`, 50 tests in `examples/northbound/tests/` |
| W5 | **built**: Northbound 2.4 (Fare Lock, Price Watch auto-enroll, Concierge 2.0 with the seeded bugs as settings) and 2.4.1 (the three fixes as named settings, Fare Lock on hotels); one test per README persona, mutation-checked ($0 of Meta budget) | `examples/northbound/`, `examples/northbound/tests/test_release_2_4.py` |
| W4 | **built**: scenario runner (`semaudit capture`): launches each release, drives every persona's scenario in Chromium on simulated time through the adapter, writes episodes (steps, captures with source-specific locators, oracle state); 15 stories match the hand-authored fixtures; deterministic; mutation-checked ($0 of Meta budget) | `src/semaudit/capture/`, `src/semaudit/story/episode.py`, `examples/northbound/adapter.py`, `tests/test_capture.py` |
| W6 | **accepted**: extraction from real captures, 55/55 distinct messages exact on 3/3 fresh repeats ($0.36) | [evidence/w6-extraction.md](evidence/w6-extraction.md) |
| W7 | **built**: base ↔ head alignment by event key; explicit added/removed; marked fuzzy pairs | `src/semaudit/story/align.py` |
| W8 | **accepted**: real captures → stories → rules + P2 interpretation; 31/31 × 5 fresh runs; stubs fail ($0.56). Re-accepted after the external audit fixes (lineage, liveness, expiry, pair kinds, supersession): 31/31 × 5 ($0.30) | [evidence/w8-real-captures.md](evidence/w8-real-captures.md) |
| W9 | **accepted**: `semaudit review` end to end (capture → stories → issues → re-capture → verify → policy → review.json) and `semaudit repro`; 2.3→2.4 Hold with 9 verified issues; 2.4→2.4.1 resolves the fixes and raises Rina on scope; verifier rejects 4/4 planted issues (~$0.79) | [evidence/w9-review.md](evidence/w9-review.md) |
| W10b | **built**: Release Story page from review.json (timeline, issue rail, detail, diff, persona switch, rule panel, resolved, deep links); 5+1 browser tests | [evidence/w10b-release-story.md](evidence/w10b-release-story.md) |
| Audit 2 | **fixed**: core generalized (persona context + `subject.yaml`; no app vocabulary in `src/`, guarded; a non-travel contract runs); fail closed on unmeasured oracles / missing episodes / unmeasured head; approval gate (provisional until owner-approved); repro re-derives the finding, checks base events for resolved issues, fails on zero checks; review manifest + `semaudit verify-report`; screenshots hashed; verifier per occurrence; same-family confidence capped at medium; count escalation removed; a reconciler must address both actions (Kai stays open on 2.4.1); LICENSE. Owner set P2 per label (Oct 27): conflict critical, unexplained tradeoff major; 2.4 policy says hold, fired by Kai; page names the trigger and the models ([w11b](evidence/w11b-severity-and-page.md)) | [evidence/audit-2-fixes.md](evidence/audit-2-fixes.md) |

## The minimum compelling version (MCV)

The MCV is everything the demo storyboard needs to be true ([06-demo-vision.md](06-demo-vision.md)). **Every item the storyboard marks "never cut" is P0.**

1. **Semantic core proof (W1b):** hand-authored stories → real generators → real Muse Spark extraction and interpretation → exact expected status vectors.
2. **Northbound** 2.3 / 2.4 / 2.4.1 ([examples/northbound](../examples/northbound/README.md)), with persona and clock hooks, attribution, event keys and oracles.
3. **Contract schema**, covering five rule kinds, exceptions, the decision vocabulary with preconditions and rationales, the strength rubric, feature lifetimes, personas with trips, scenarios and release policy. It comes with the Northbound reference contract and a **minimal review page** (render + approve).
4. **Capture:** a scenario runner on simulated time, producing episodes and derived state.
5. **Evidence:** extraction of message kind, directives (strength, `explains_own_tradeoff`, `reconciles`), claims and attribution.
6. **Stories:** time-ordered events, alignment by `event_key`, and a delta.
7. **Relations:** the W1b generators and interpretation, wired to real captures, plus the `model_open` pass.
8. **Issues:** severity, confidence and verification as three separate fields; a verifier; the policy-based recommendation; the *not raised* list.
9. **Release Story UI** (the hero) and `semaudit repro`.
10. **Memory:** dispositions, scoped exceptions, and a re-review of 2.4.1.
11. **Benchmark, minimal:** 3 sealed releases, one-shot and multi-pass judge baselines, and the explorer baseline.
12. **Finablo R1.**

**Not in the MCV:**
- voice-to-draft onboarding (W12, P1);
- Finablo R2;
- autonomous mapping of an unknown app;
- SAM 3.1, iOS, and a GitHub Action.

## Work items, in priority order

| P | ID | Work item | Depends on | Day |
|---|---|---|---|---|
| **P0** | W0 | Docs coherent; critic findings folded in; owner confirms Northbound rules (D11) | — | Oct 26 |
| **P0** | W1 | **Model access, verified by calls rather than assumed.** Muse Spark: latest official ID; image input; structured output; tool calling; Standard vs Contributor endpoints; real token costs on a sample story and capture. Muse Spark Open on Modal or Baseten. | credits | Oct 27 AM |
| **P0** | W3a | Rule and decision schema (Pydantic). Northbound reference contract: rules, vocabulary, rubric, copy keys. | — | Oct 27 |
| **P0** | **W1b** | **Semantic core proof, before any app exists** (spec below). | W1, W3a | **Oct 27–28** |
| **P0** | W2 | Northbound 2.3, with hooks, oracles, `data-feature` and `data-message-key`. | — | Oct 28 |
| **P0** | W10a | **Release Story design:** design spec → wireframe → **owner approval** (this gates W10b). Runs in parallel, through a design agent. | W3a | Oct 27–28 |
| **P0** | W3b | The rest of the contract (scenarios, features, surfaces, facts, release policy) + the **minimal review page**. | W3a | Oct 28 |
| **P0** | W4 | Scenario runner: episodes, captures, derived state, journey repair. | W2, W3b | Oct 28–29 |
| **P0** | W5 | Northbound 2.4 and 2.4.1, using the canonical copy keys. | W2 | Oct 29 |
| **P0** | W6 | Extraction, run on structured sources first: DOM with `data-*` attributes, plus the JSON email and push sinks. PDF and chat are text only. Cache and ledger. | W1, W4 | Oct 29–30 |
| **P0** | W7 | Stories, alignment, delta. | W6 | Oct 30 |
| **P0** | W8 | Wire W1b's generators and interpretation to real stories; `model_open`. | W7 | Oct 30 |
| **P0** | W9 | Issues: severity, confidence, verification; verifier; policy; the *not raised* list; `semaudit repro`. | W8 | Oct 30–31 |
| **P0** | W10b | Release Story UI, built to the approved wireframe. | W10a, W9 | Oct 31 |
| **P0** | W11 | Dispositions → memory; 2.4.1 re-review. **Built Oct 27**: fix / not-an-issue / accept (+ release decisions), `semaudit decide`, `decide-release`, `serve`; `rule` / `expect` decisions planned, not built ([evidence](evidence/w11-memory.md)). | W9 | Oct 31 |
| | | **Core feature freeze: Oct 31, end of day** | | |
| **P0** | W13a | **Sealed benchmark** (a separate session): bench-01..03 plus their contracts and ground truth, kept outside the repo; hashes committed to `bench/FROZEN.md`. | W2 | Oct 29–31 |
| **P0** | W13b | Baselines; prompts frozen on 2.4; scoring script; anonymized adjudication sheet. | W9, W13a | Nov 1 |
| **P0** | W14-R1 | Finablo: dated inputs, contract, owner review, the R1 run. | W9, W3b | Nov 2 |
| **P1** | W14-R2 | Finablo R2 + contextual adjudication. | W14-R1 | Nov 2 |
| **P1** | W12 | Voice → draft rules (onboarding enhancement). | W1, W3b | Nov 1–2 |
| **P0** | W15 | Packaging: README quickstart, `semaudit demo`, a static hosted report, LICENSE, public repo (on the owner's word). | all P0 | Nov 3 |
| **P0** | W16 | Video: record, review against the storyboard, re-record, submit. | W15 | Nov 3–4 |
| **P2** | — | Autonomous mapping · SAM 3.1 · iOS adapter · GitHub Action | — | after |

**Critical path:** W1 → W1b → W4 → W6 → W7 → W8 → W9 → W10b → W16.

The riskiest *reasoning* step, relation interpretation, is de-risked first by W1b. The riskiest *engineering* step is **W6 (extraction)**. It is narrowed to structured sources, because Northbound's attributes and JSON sinks make the locators trivial. It gets 1.5 days, and its acceptance is limited to the fields the rules actually read. If W6 slips, W7–W11 and the hero beat slip with it, so W6 gets the first available help, and the stretch items are cut before it.

## W1b: semantic core proof (specification)

**Input.** Hand-authored stories in `tests/fixtures/stories/`:
- Maya, Maya-R, Lena, Raj, Raj-X, Raj@72h, Raj@72h+30s, Raj@72h+1m, Kai, Hana, Omar, Sam & Alex, Theo, Rina (2.4.1), and the 2.3 Maya (NC6).
- Each holds the persona's trip, time-ordered events with **raw message text** (the canonical copy keys), feature, surface, time, user actions and oracle values.
- **Directive fields are not authored.** Strength, decision, action, `explains_own_tradeoff`, `reconciles` and message kind are **extracted by the model from the text**, which is the hard part being tested.

**Run.**
- Extraction runs, then the code generators, then rule evaluation, then interpretation (Muse Spark). Cross-checks run where the configuration allows.
- **5 fresh runs**, with the order of candidates and events shuffled in each run.

**Expected output.** `tests/fixtures/stories/<persona>.expected.json` lists every rule × event (or event pair) with its status, and every exception condition with its value. The output is compared as **exact sets**: the right issue *and* the right reason.
- A Maya run that raises a false-claim issue but not P2 fails. So does a Maya run that labels her pair `conflict` instead of `unexplained_tradeoff`, or a Kai run that labels his `unexplained_tradeoff` instead of `conflict`.
- A Raj run that passes because condition (a) was `unknown` fails.

**Falsifiability controls.** The test itself is tested:
- Two stub interpreters, *always-conflict* and *always-compatible*, must each **fail** the suite. The candidate-bearing negatives (Maya-R, Lena, Raj) and positives (Raj-X, Kai) make sure of this.
- A stub extractor that returns `strength: suggest` for everything must fail, on Raj-X, Hana and Omar.

**Acceptance.** All stories match on 5 of 5 fresh runs, and all three stubs fail.

**If it fails:** on Oct 28 we change the representation (rubric, schema, candidate framing), not the timeline.

## W9: issues, verification, policy, review.json, repro (specification)

The first end-to-end path. Northbound only; no new concepts until it runs:
`capture base + head → stories → rules → issues → verify → policy → review.json → semaudit repro`.

- **Issues.** A violated entry becomes an issue. Violations with the same signature (rule, feature(s), message
  key or P2 subject, failing exception conditions) are grouped across personas into one issue with its reach.
  If one event violates several rules, the issue is counted once under the rule the contract lists first and
  carries the others.
- **Delta.** Base stories are evaluated too. Each head issue is `new` or `pre_existing`; a base issue with no head
  counterpart is `resolved`.
- **Severity** (code, from the contract, never a model): the rule's owner-set level. *Superseded after the second
  audit (owner ruling, Oct 26):* count-based escalation is removed, because the number of test personas an issue
  reaches is a property of the fixtures, not of production. Factors record the tested-persona counts before and
  after the decision, for the reader only.
- **Confidence** (code, from a basis list): evidence kind (measured vs interpreted), cross-model extraction
  agreement on the cited messages, cross-model label agreement (P2), the defense outcome, unknown validity or
  unknown conditions. High: everything run agrees and nothing is unknown; medium: something not run or unknown;
  low: a disagreement or a successful defense.
- **Verification** (steps actually run, each pass / fail / not_run): `reproduced` (re-capture the persona's
  scenario, the same events appear with the same text), `evidence_linked` (fails closed), `cross_model`
  (the other model re-extracts the cited messages and, for P2, re-labels), `defended` (the defender cannot
  explain it away), `oracle_checked` (fact rules only). Status: verified / partially_verified / unverified /
  failed (`not_reproducible`, `disputed`). Failed issues are not open; they go on the not-raised list.
- **Not raised.** Every candidate cleared and why: explained tradeoffs (with the reconciler), exceptions applied
  (with conditions), failed verifications.
- **Recommendation** from `release_policy.yaml` over the open issues, with the row text verbatim.
- **Outputs.** `runs/<id>/review.json` in the shape the approved Release Story spec names; `semaudit review`
  and `semaudit repro <issue-id>`.

**Acceptance.** On Northbound 2.3 → 2.4: the issues are exactly the violated entries W8 accepted, grouped;
severity, confidence and verification are each shown (by tests) to change while the other two stay fixed;
every issue is reproduced and evidence-linked; `repro` re-finds the hero issue from a fresh capture;
2.4 → 2.4.1 marks the fixed issues `resolved` and raises Rina's hotel urgency with
"nearest exception P1-E1 does not apply: scope". Budget ≤ $2.

## Quality gates per work item

- **Tests:** each item gets its own tests. Guards are mutation-checked: delete the code a test guards, and the test must go red.
- **W6:** accepted when, on the 2.4 captures, message kind, strength, decision, action, `explains_own_tradeoff` and `reconciles` are all correct for **every** hero and boundary directive, and correct on at least 90% of the rest.
- **W8:** accepted when W1b's expected vectors are reproduced **from real captures** on 5 of 5 fresh runs.
- **W9:** accepted when severity, confidence and verification can each be shown to change independently, and the release policy is exhaustive (a test enumerates combinations of open issues).
- **W10b:** accepted when **someone who has not seen the project** can state the screen's four facts from a silent recording.

## Budget (Meta $150, plus any Modal or Baseten credits)

These are estimates until W1 measures real costs; the allocation is re-set on Oct 27.

| Item | Estimate |
|---|---|
| W1b: 15 stories × 5 runs | ≤ $8 |
| Development iterations | ≤ $25 |
| The auditor on 3 bench releases × 3 fresh runs | ≤ $18 |
| B-judge-1 (3 × 3) | ≤ $5 |
| B-judge-N (budget-matched, 3 × 3) | ≤ $18 |
| B-explore (3 × 3, capped at $3 each) | ≤ $27 |
| B-explore+scenarios (2 × 1) | ≤ $6 |
| Ablations: no-generators, no-exceptions, no-verifier (2 releases × 1 run) | ≤ $12 |
| Finablo | ≤ $10 |
| **Reserve** | **≥ $21** |

If open-weights credits are not granted, the extractor, defender and cross-checker roles move to Muse Spark. The Contributor endpoint is used only for fictional data, and every confidence basis records "reduced independence".

## Risks

| Risk | Mitigation |
|---|---|
| Extraction of strength or `reconciles` is unreliable | the strength rubric; hero and boundary directives gated at 100% in W6; cross-model agreement feeds confidence |
| Interpretation is unreliable | W1b on day 1–2, with stubs proving the test bites |
| The hero pair is judged "compatible" (a lock as a hedge) | the incompatibility rationale is in the contract; the owner confirms it in D11; adjudicators see the rationale |
| The baseline matches the auditor on judgment | a legitimate result; coverage and reproducibility are measured separately; we publish it |
| The benchmark looks self-graded | a separate seeding session, frozen hashes, negative and boundary controls, the stated limitation |
| Finablo R1's transient pending window | run local Finablo with AI generation disabled, so the pending state persists. No Claude spend |
| Disqualification over provenance | the provenance ledger; on-screen labels; no Finablo code in the repo |
| Video crunch | W16 starts on the morning of Nov 3, whatever is unfinished |

## Cut order

1. B-explore+scenarios.
2. Ablations, down to no-exceptions only.
3. The 2.4.1 hotel-scope moment (fixed → resolved is kept).
4. Finablo R2.
5. Voice onboarding.

**Never cut:** Maya's story, Raj's rule panel, Kai, repro, the honest baseline panel, Finablo R1.
