# Hackathon compliance and provenance

Event: **Meta Global AI Developer Hackathon** (Cerebral Valley). Source: the participant guide PDF, read 2026-10-26.

## Rules that shape this project

| Rule (from the guide) | What we do about it |
|---|---|
| **Open source.** The repository must be public. | Standalone public repo with a license chosen before submission. No consumer app code (for example Finablo) lives here. |
| **New work only.** Startups may build on existing codebases but must clearly identify what was newly built. | Everything in this repo is written during the event. Prior work is listed below as *inspiration only*, and no code is copied from it. |
| **Demo must only highlight what was built during the hackathon.** Failing to identify original contributions means disqualification at the judges' discretion. | The video says on screen that Finablo is the *app under audit*, not the submission. Every feature shown is from this repo. |
| **Must use Meta models**: Muse Spark series, Muse Wonder, Muse Image, Muse Voice Transcribe, SAM 3.1 via the Meta Model API; open weights Muse Glimmer and Muse Spark Open; Muse Code. | Muse Spark, Muse Spark Open, Muse Voice Transcribe; SAM 3.1 as a stretch. Each has a distinct role (README). |
| **Open-weights model ID**: use `meta-models/muse-spark-open-1026` (not the one in the docs). | Pinned in model config. |
| **Banned / anti-projects**: medical advice, basic RAG, simple image analyzers, etc. | sra is developer tooling. The demo target is a travel app; Finablo is personal finance. |
| **Team size** up to 4; solo allowed. | — |
| **Submission**: Wed **Nov 4, 9:00 PM ET**, via the CV platform. Public repo, accessible video link, all contributors listed. | Internal deadline: submit by **Nov 4, 12:00 PM ET**. |
| **3-minute demo video**: a primary judging artifact, together with code and the live product. | Demo designed first ([docs/06-demo-vision.md](docs/06-demo-vision.md)). A sample run report is hosted publicly as the "live product". |
| **Credits**: $150 Meta Model API (claim by Nov 4, 9 PM ET; card required; set a spend limit). Baseten $100 + 2M TPM, Modal $100, Fireworks $25 (each by application). | Apply for Baseten and Modal on day 1 (open-weights serving). Set the Meta spend limit at $150. |

## Judging (stage 2, 0–10 per category)

| Category | Weight | How this project earns it |
|---|---|---|
| Impact | 30% | Every team shipping AI-written or multi-surface output has this problem. Proven on a real product (Finablo) as well as a demo app. |
| Use of Meta AI tooling | 25% | Five model roles. Open-weights extraction and verification. Cross-model agreement as a verification signal. Voice onboarding. |
| Technical depth | 20% | A product contract, a claim graph, differential audit with intent matching, a verifier, a ratchet, and a benchmark with a baseline and ablations. |
| Demo | 25% | Real run output, a before/after scoreboard, one live "it caught it" moment. |

Bonus prizes in reach: **Best Build on Meta Open Weight Models** ($10K), **Best Agentic Use-Case** ($5K), **Community Vote**, **Most Viral** (X post).

## Schedule

| Date (ET) | Event |
|---|---|
| Mon Oct 26, 12 PM | Kickoff |
| Tue Oct 27, 12 PM | Agents 101: Build a Multimodal AI Agent |
| Wed Oct 28, 12 PM | Agents 102: Best Practices for Verifiable Agents (directly relevant) |
| Fri Oct 30, 12 PM | Fireworks: inference to training with Muse Open models |
| Weekdays 10–11 AM | Discord #office-hours (Meta team) |
| Oct 27 – Nov 4 | Building period |
| Tue Nov 3 | Last day for submission questions |
| **Wed Nov 4, 9 PM** | **Submission deadline** |
| Nov 5–8 | Judging |
| Mon Nov 9, 12 PM | Top 10 announced, live final round |

## Provenance ledger

**Prior work that inspired this project. None of its code is in this repo.**

- Finablo's internal "same-story" harness: a deterministic cross-surface fact comparison for one app (10 hand-coded facts, 22 surfaces, hand-written cohorts). It also has a release diff, a value-to-code trace, and a 5-event replay benchmark. It is private, Finablo-specific, and uses no LLMs. Its lesson shapes this project: hand-coded extractors catch only what someone anticipated, and its blind recall on 5 real past releases was 2/5.

**New during the hackathon (everything in this repo):** the product contract and onboarding, the explorer and journey replay, model-based claim extraction, the claim graph and checkers, the verifier, the semantic diff with intent matching, evidence packets, the ratchet, the Northbound demo app, the benchmark, and the Finablo integration *contract* (the YAML that describes Finablo to sra, which lives in Finablo's repo).

Keep this ledger current: add a line whenever something from outside the event is used (a library, a dataset, an asset).
