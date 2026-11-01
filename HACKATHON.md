# Hackathon compliance and provenance

Event: **Meta Global AI Developer Hackathon** (Cerebral Valley). Source: the participant guide PDF, read 2026-10-26.

## Rules that shape this project

| Rule (from the guide) | What we do about it |
|---|---|
| **Open source.** The repository must be public. | Standalone public repo, Apache-2.0 ([LICENSE](LICENSE)). No consumer app code (for example Finablo) lives here. The Spree test harness is its own repo, [spree-semaudit](https://github.com/jaykay2000/spree-semaudit). |
| **New work only.** Startups may build on existing codebases but must clearly identify what was newly built. | All of this repo's source and features were written during the event, except the third-party assets and dependencies listed in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) (one font, used by the Northbound demo app, and the installed Python packages). Prior work is listed below as *inspiration only*, and no code is copied from it. |
| **Demo must only highlight what was built during the hackathon.** Failing to identify original contributions means disqualification at the judges' discretion. | The video says on screen that Finablo is the *app under audit*, not the submission. Every feature shown is from this repo. |
| **Must use Meta models**: Muse Spark series, Muse Wonder, Muse Image, Muse Voice Transcribe, SAM 3.1 via the Meta Model API; open weights Muse Glimmer and Muse Spark Open; Muse Code. | Two Meta model lines, measured from run manifests and ledgers ([README, Models](README.md#models-measured)): **Muse Spark 1.3 / 1.2** on the Meta Model API for the Northbound and Finablo reviews, and **Muse Spark Open** on Baseten for the Spree reviews and for every reusable-check conversion and judgment. Muse Voice Transcribe is **not built**. |
| **Open-weights model ID**: use `meta-models/muse-spark-open-1026` (not the one in the docs). | Used as is on Baseten, and recorded on every saved-check result (`models: {conversion, judging}`). |
| **Banned / anti-projects**: medical advice, basic RAG, simple image analyzers, etc. | semaudit is developer tooling. The apps it is shown on are Northbound (a fictional travel app), Spree (an open-source store) and Finablo (personal finance, the app under audit, not the submission). SRA gives no financial advice. |
| **Team size** up to 4; solo allowed. | Solo, Indie Developer track. |
| **Submission**: Wed **Nov 4, 9:00 PM ET**, via the CV platform. Public repo, accessible video link, all contributors listed. | Internal deadline: submit by **Nov 4, 12:00 PM ET**. |
| **3-minute demo video**: a primary judging artifact, together with code and the live product. | The video, the README and the submission lead with the same sentence (see the Demo row below). Hosting a sample run report publicly as the "live product" is planned. The first demo design is archived ([docs/archive/06-demo-vision.md](docs/archive/06-demo-vision.md)). |
| **Credits**: $150 Meta Model API (claim by Nov 4, 9 PM ET; card required; set a spend limit). Baseten $100 + 2M TPM, Modal $100, Fireworks $25 (each by application). | Meta Model API for Northbound and Finablo; Baseten for Muse Spark Open on Spree. Modal is not used. |

## Judging (stage 2, 0–10 per category)

| Category | Weight | How this project earns it |
|---|---|---|
| Impact | 30% | Teams already find problems: developers, users, and AI agents that test the product. SRA keeps a validated discovery as an approved check with its journey, rule and evidence, so later releases are checked for it again instead of rediscovering it. Shown on a fictional app (Northbound), a real open-source store (Spree) and a real product (Finablo). |
| Use of Meta AI tooling | 25% | As built and measured ([README, Models](README.md#models-measured)). **Muse Spark Open** (`meta-models/muse-spark-open-1026`, on Baseten) drafts every reusable check's journey and rule from a finding, gives the 3 seeded readings of the rule by the same model on each replay, and does every role in the Spree reviews. **Muse Spark 1.3** (Meta Model API) extracts and interprets in the Northbound reviews and reads the Finablo review; **Muse Spark 1.2** re-derives and argues against every Northbound issue. Each app uses one model family, so a second pass is recorded as reduced independence and confidence is capped at medium. Not built: Muse Voice Transcribe. |
| Technical depth | 20% | Reusable checks: a deterministic gate that refuses a draft it cannot verify against the finding's own text (no dropped instruction, no invented action); owner approval pinned to the check's content hash; replay with the app's own records; four statuses kept apart (replay · rule result · readings that agree · evidence verified), where a PASS needs verified evidence; memory across releases (fixed · still open · came back). Under it, the release review: time-ordered experience stories, code-generated conflict candidates plus model interpretation, owner rules with scoped exceptions, severity, confidence and verification as separate fields, and repro on demand. Measured on a held-out set fixed before the converter was written ([evidence](docs/evidence/imported-checks/README.md)). |
| Demo | 25% | Opening line: "Semantic Release Auditor turns validated discoveries, from developers and AI agents, into reusable release checks." Beats: (1) a real bug in the owner's finance app, Finablo, that passed its 354 automated deploy checks ([evidence](demo/evidence/finablo-gate-v706/README.md); from Finablo's private repository, not publicly verifiable): one 61-year-old test user was shown two different 401(k) limits; (2) the loop: discovery from developers, users and AI agents → Muse Spark Open drafts a journey and the rule it broke → a gate checks every step → the owner approves → replay on a release with the app's own records → new / fixed / still open / came back → saved for later reviews; (3) agents find different things on different runs (no scores, no ranking); (4) Spree: an agent's email finding becomes a check; it FAILs on the older release, PASSes on the next, and a new run loads the saved check and runs it again (Run 3c; label "prototype: 6 of 57 held-out agent findings converted"); (5) found, reported, fixed upstream: a Spree line SRA's own journeys found wrong in both releases, reported upstream, and fixed there by the maintainers (issue 283, PR #289 merged 2026-11-01); (6) Northbound: an owner-written rule about product intent; (7) back to Finablo: the 401(k) bug is one of SRA's own journeys, and on the next release it shows $35,750 everywhere; (8) the release review page. Sources are listed under "Demo sources" below. |

### Demo sources

Where each beat's facts come from, and what is not built yet (checked 2026-10-31).

| Beat | Source | Status |
|---|---|---|
| 1. Finablo bug | 61-year-old shown $32,500 and $24,500 where $35,750 applies (where the plan allows the age 60–63 catch-up): [demo/video-assets/scenes/README.md](demo/video-assets/scenes/README.md), from the Finablo review `review-10ff1e3-a183626.reader.json`. The 354 passing checks: Finablo's v706 deploy gate (354 OK, 0 FAIL: gate checks, not tests), quoted with its commit and tree in [demo/evidence/finablo-gate-v706](demo/evidence/finablo-gate-v706/README.md) | from Finablo's private repository; not publicly verifiable |
| 2. The loop | [README, The loop](README.md#the-loop) and [Reusable checks](README.md#reusable-checks-prototype) | built (prototype) |
| 3. Different runs find different things | the agent experiments' grading, in a separate private repo | description only, no counts in this repo |
| 4. Spree saved check | [imported-checks evidence](docs/evidence/imported-checks/README.md), Run 3c ([transcript](docs/evidence/imported-checks/acceptance/run3c-transcript.txt), [cards](docs/evidence/imported-checks/acceptance/cards-run3c.html)); reproduce in [spree-semaudit](https://github.com/jaykay2000/spree-semaudit) | built; the approval in Run 3c is labelled "owner has not reviewed this digest" |
| 5. Found, reported, fixed upstream | [demo/evidence/taxline-upstream-2026-10-30](demo/evidence/taxline-upstream-2026-10-30/README.md): spree/storefront issue 283 (reported 2026-10-30) was closed on 2026-11-01 by PR #289, "Show tax-exclusive line amounts in checkout and order summaries" ("Fixes #283"), written and merged by a member of the Spree organisation, merge commit `f9fa77a` (checked with `gh api`, 2026-11-01). Found by SRA's own Spree journeys, not by an imported check | reported upstream; fix merged 2026-11-01 (PR #289). SRA has not run the fixed storefront |
| 6. Northbound rule | rule P2 in [examples/northbound/contract/principles.yaml](examples/northbound/contract/principles.yaml); Maya and Lena in [docs/evidence/w9-review.md](docs/evidence/w9-review.md) | built; the rule is owner-written, not imported |
| 7. Finablo bug on the next release | [docs/evidence/imported-checks/finablo/README.md](docs/evidence/imported-checks/finablo/README.md): fresh captures of the `target_61` journey on v706 and v707 (v707 shows $35,750 on every limit line). A separate "unused headroom" line still uses the under-50 limit on both releases; Finablo closed it in v708 | the bug is one of SRA's own journeys, **not a saved check**. Turning it into one was tried: the developers' written record names what the user saw but no step they took, so the frozen converter graded it `partially_converted` and SRA refused to approve it. That is the gate working, not a defect |
| 8. Release review page | `semaudit serve`; stills in [demo/video-assets/page/README.md](demo/video-assets/page/README.md) | built |

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

- Finablo's internal "same-story" harness: a deterministic cross-surface fact comparison for one app (10 hand-coded facts, 22 surfaces, hand-written cohorts). It also has a release diff, a value-to-code trace, and a 5-event replay benchmark. It is private, Finablo-specific, and uses no LLMs. Its lesson shapes this project: hand-coded extractors catch only what someone anticipated, and its blind recall on 5 real past releases was 2/5, and it cannot represent directives, time or owner intent at all.

**New during the hackathon (everything in this repo):** reusable checks made from findings (`src/semaudit/imported/`: the converter and its gate, owner approval pinned to content, replay and re-check with four separate statuses, the check memory, `semaudit checks approve|run|card`), the product contract (operational principles, exceptions, decisions, scenarios), the scenario runner, extraction of messages, directives and claims, User Experience Stories, relation generators and interpretation, issues with severity, confidence and verification, the verifier, release policy, scoped memory, the Release Story UI, the Northbound demo app, the benchmark protocol and baselines. Also the Finablo *contract* (the YAML that describes Finablo to the auditor), which lives in Finablo's repo, not this one. Also the Spree harness (the store's contract, driver and import vocabulary), in its own repo, [spree-semaudit](https://github.com/jaykay2000/spree-semaudit).

**Outside software used as an app under audit (none of its code is in this repo):** Spree, an open-source store (6.0.0.beta2 and beta3, and the upstream storefront at `8ba5eee`), run locally by the Spree harness.

Keep this ledger current: add a line whenever something from outside the event is used (a library, a dataset, an asset).
