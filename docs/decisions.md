# Decisions

## Settled

| Date | Decision | Source |
|---|---|---|
| 2026-10-26 | Standalone open-source repo; Finablo is a consumer, never a dependency | owner |
| 2026-10-26 | No code copied from Finablo's harness; ideas only, recorded in HACKATHON.md | hackathon "new work only" rule |
| 2026-10-26 | Solo entry (Indie Developer track) | owner |
| 2026-10-26 | Skip Finablo's Sage chat surface | owner |
| 2026-10-26 | Mobile is a generic adapter for later | owner |
| 2026-10-26 | Name **Semantic Auditor** (CLI `semaudit`); license **Apache-2.0**; published under the **`finablo`** GitHub account, with only this repo made public | owner |
| 2026-10-26 | Build priority: prove Maya's conflict detection and Raj's allowed exception first, using a **written draft** of the Northbound principles. Voice onboarding is a demo enhancement, recorded once the principles are final | owner |
| 2026-10-26 | Push and publish only on the owner's word | owner standing rule |
| 2026-10-26 | **Thesis:** the auditor reconstructs a user's experience across a release, finds conflicting behaviour and messages, and gives reproducible evidence for a shipping decision. The User Experience Story is the unit of analysis; fact comparison is one layer inside it | owner, after the external review |
| 2026-10-26 | Severity, confidence and verification status are separate fields, never combined | owner |
| 2026-10-26 | Principles are operational, with conditions and scoped exceptions; an "accept" decision creates a scoped, expiring exception, never a blanket suppression | external review, adopted |
| 2026-10-26 | Deterministic checks only for expressible rules; otherwise approved semantic expectations | external review, adopted |
| 2026-10-26 | Capture first; deterministic pass before any model work | external review, adopted |
| 2026-10-26 | Release naming: Northbound **2.3** (base) · **2.4** (narrative/demo) · **2.4.1** (memory) · **bench-NN** (sealed benchmark) | doc consistency review |
| 2026-10-26 | Narrative fixture ≠ benchmark fixture; headline numbers come only from the sealed set | external review, adopted |
| 2026-10-26 | Fair baselines: same model, same context, same budget; three evaluations (coverage, judgment, reproducibility); negative controls first-class | external review, adopted |
| 2026-10-26 | **Finablo:** R1 (the 401(k) cross-surface number) is the real-product validation; R2 (an experience-level collision) is shown only if it survives contextual adjudication. The auditor gets only inputs that existed before the release | doc consistency review |
| 2026-10-26 | Three Meta models: Muse Spark, Muse Spark Open, Muse Voice Transcribe. SAM 3.1 and others are out of the MCV | external review, adopted |
| 2026-10-26 | Finablo runs use synthetic profiles and Standard-mode endpoints only; Contributor mode only for fictional data | external review, adopted |
| 2026-10-26 | The demo script does not predetermine issue counts, severities or benchmark numbers | external review, adopted |
| 2026-10-27 | Hero conflict uses only **true** messages; the false seat count and fee mismatch are shown separately as the factual layer | second review, adopted |
| 2026-10-27 | Three rule kinds evaluated independently: universal (no exceptions), conditional (scoped exceptions), coherence (P2). An exception to one rule never excuses another. "Time-sensitive" = departs within 72 h; fixed dates alone never qualify | second review, adopted |
| 2026-10-27 | Directive validity: text deadline, action precondition, feature default lifetime or supersession; an unknown end is explicit, never "forever" | second review, adopted |
| 2026-10-27 | Semantic core proven first (W1b) on hand-authored stories, with real model interpretation | second review, adopted |
| 2026-10-27 | Claims are `supported` / `contradicted` / `unverifiable`; only contradicted claims raise false-claim issues | second review, adopted |
| 2026-10-27 | Benchmark additions: B-explore+scenarios (scenarios counted as setup), a budget-matched multi-pass B-judge-N, fresh runs vs cached replay, a corrected no-generators ablation | second review, adopted |
| 2026-10-27 | Finablo historical runs: no voice note; persona discovery reported as blind discovery vs given a target persona | second review, adopted |

## Open: owner to decide (defaults in bold)

| # | Decision | Default and why |
|---|---|---|
| D11 | Northbound rule wording (U1, U2, P1–P4, P1-E1) and the boundary-case table | **as in examples/northbound/README.md** (written draft); the owner confirms before W1b runs. A voice note is recorded later, once the rules are final, to test onboarding |
| D12 | An independent human adjudicator for the subjective labels | **ask one person** for about 1 hour on Nov 1–2; otherwise report owner-only adjudication and say so |
| D13 | Which Finablo commits for R1 and R2 | the planning agent finds the introducing commits; the owner confirms |
| D14 | Open-weights hosting credits (Modal / Baseten) | **apply today**; if they are not granted, the fallback is in the plan |
