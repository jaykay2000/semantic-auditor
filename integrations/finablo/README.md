# Integration: Finablo (first real consumer)

Finablo is a personal-finance web app. Its report, dashboard, PDF, export and AI assistant all speak to the same user about the same money, so it is a natural first consumer. It adopts the auditor like any other app would. **No Finablo code or contract lives in this repo.**

## What lives where

| Thing | Location |
|---|---|
| The auditor | this repo, installed into Finablo's dev environment as a package |
| Finablo's contract | `.semaudit/` in Finablo's own private repo |
| Run artifacts | outside both repos (a local evidence folder) |
| This note | generic adoption steps only |

## Adoption steps (generic)

1. Boot two releases locally (base and head) on two ports.
2. Provide a persona hook (Finablo: the guest assessment API plus the dev-only login-code endpoint, local only) and, where available, a clock hook.
3. Onboard: `semaudit onboard --url … --docs … --voice …`. The owner reviews, and the contract is committed in the app's repo.
4. Review a release: `semaudit review --base … --head … --notes …`.

## Hackathon evaluation (see [docs/08-evaluation.md](../../docs/08-evaluation.md))

| Event | Kind | Role |
|---|---|---|
| **R1** | objective: on the pending report page, a 61-year-old saw $24,500 as their 401(k) maximum while the server and export said $35,750 | **the real-product validation** |
| **R2** | experience-level: the dashboard hero's on-pace framing beside a new card's urgent directive | shown **only if it survives contextual adjudication**, because "ahead overall, with one urgent task" can be legitimate |

**Blindness:**
- The auditor gets only `VISION.md` and the principles as they existed **before** the release, synthetic personas, and the two builds. **No voice note:** one recorded now is not contemporaneous knowledge.
- Personas come from the auditor's normal generation over the contract's axes and thresholds. If the 61-year-old is not generated that way and has to be supplied, the result is reported as *detection given a target persona*, not *blind discovery*. The two claims are reported separately.
- It never gets `CLAUDE.md`, `BUG-HISTORY.md`, `PLAN.md` or the handoff cards, all of which describe these bugs.
- The input list and commit SHAs are recorded in the run.

## Constraints (carried from Finablo's own rules)

- Local only; never `app.finablo.com`.
- No Finablo pushes for this work (limited CI minutes).
- Skip the Sage chat surface.
- Synthetic profiles only; Standard-mode endpoints only.
- The auditor's model spend (Meta credits) is separate from Finablo's Anthropic budget.
