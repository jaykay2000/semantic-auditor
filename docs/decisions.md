# Decisions

## Open: owner to decide (defaults in **bold** are what the plan assumes)

| # | Decision | Options | Default and why |
|---|---|---|---|
| D1 | Public name | keep "Semantic Release Auditor" · rename (e.g. *Samesay*, *Concord*, *Truthline*) | **Rename before going public.** `semantic-release` is a widely used npm release tool, so the current name will be confused with it in search and on GitHub. Keep `sra` as the working CLI name until then. |
| D2 | License | **Apache-2.0** · MIT | Apache-2.0: permissive, with an explicit patent grant, which matters for tooling companies may adopt. |
| D3 | GitHub owner | personal account · `finablo` org · new org | **New org or personal account.** The auditor is meant to be independent of Finablo; hosting it under `finablo` makes it read as a Finablo internal tool. |
| D4 | Team | solo · up to 4 | **Solo** + Claude Code agents (disclosed in HACKATHON.md). |
| D5 | Demo target app | **Northbound (fictional travel app, built here)** · a Finablo-like finance clone | Travel shows the tool generalizes beyond Finablo's domain, and its claims (price, dates, refund policy, baggage) are instantly legible to any judge. Finablo supplies the real-world proof. |
| D6 | How much of Finablo appears | **Screens + one finding, synthetic personas, labelled "app under audit"** · also show the Finablo contract · no Finablo at all | Screens and one finding are enough for impact. The Finablo contract stays in Finablo's private repo. |
| D7 | Finablo bug to recreate | **Pending-page 401(k) limit ($24,500 vs $35,750, age 61)** · PDF-vs-JSON finalizer gap · the tax-loss-harvest dollar | The 401(k) case is a pure cross-surface number, easy to explain in 10 seconds, and the old deterministic harness missed it blind. |
| D8 | iOS stretch | **Design slide only** · single-screen spike on a generic sample app | Mobile is a post-hackathon adapter; any spike uses a generic sample app and synthetic data. |
| D9 | Sage chat in the Finablo run | **Skip** · include | Sage calls Claude and spends Finablo's AI budget; Finablo's rule is to ask before any LLM persona run. |
| D10 | Hosted "live product" | **Static report on GitHub Pages** · hosted Northbound + sra | Static is free and cannot break during judging. |

## Settled

| Date | Decision | Source |
|---|---|---|
| 2026-10-26 | Standalone open-source repo; Finablo is a consumer, never a dependency | owner |
| 2026-10-26 | Demo designed first; MCV defined in [07-implementation-plan.md](07-implementation-plan.md) | owner |
| 2026-10-26 | No code copied from Finablo's same-story harness; ideas only, listed in HACKATHON.md | hackathon "new work only" rule |
| 2026-10-26 | Roles, not models: every model is reached through `sra.models` routing | architecture |
| 2026-10-26 | Northbound v2 issues are seeded blind, by a separate session | benchmark integrity |
| 2026-10-26 | Nothing is pushed or made public until the owner says so | owner standing rule |
