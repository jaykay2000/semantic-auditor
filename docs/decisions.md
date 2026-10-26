# Decisions

## Settled

| Date | Decision | Source |
|---|---|---|
| 2026-10-26 | Standalone open-source repo; Finablo is a consumer, never a dependency | owner |
| 2026-10-26 | No code copied from Finablo's harness; ideas only, recorded in HACKATHON.md | hackathon "new work only" rule |
| 2026-10-26 | Solo entry (Indie Developer track) | owner |
| 2026-10-26 | Skip Finablo's Sage chat surface | owner |
| 2026-10-26 | Mobile is a generic adapter for later | owner |
| 2026-10-26 | GitHub: the owner's personal account is acceptable (the rules only require a public repo); `finablo` is the fallback | owner |
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

## Open: owner to decide (defaults in bold)

| # | Decision | Default and why |
|---|---|---|
| D1 | Public name | **"Semantic Auditor"**, with the `semaudit` CLI. "Release auditor" is taken on PyPI and npm; `semantic-release` is a well-known npm tool; `semantic-auditor` is free on PyPI. The docs keep "Semantic Release Auditor" until this is confirmed |
| D2 | License | **Apache-2.0** (permissive, with a patent grant) |
| D3 | GitHub username for the personal account | needed before publishing; `gh` on this machine is logged in as `finablo` |
| D11 | Northbound principle wording (P1–P4, P1-E1) | **as in examples/northbound/README.md**; the owner records the voice note that produces them |
| D12 | An independent human adjudicator for the subjective labels | **ask one person** for about 1 hour on Nov 1–2; otherwise report owner-only adjudication and say so |
| D13 | Which Finablo commits for R1 and R2 | the planning agent finds the introducing commits; the owner confirms |
| D14 | Open-weights hosting credits (Modal / Baseten) | **apply today**; if they are not granted, the fallback is in the plan |
