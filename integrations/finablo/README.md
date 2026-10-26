# Integration: Finablo (first consumer)

Finablo is a personal-finance web app and the auditor's first real customer. It consumes sra like any other app would. **No Finablo code or contract lives in this repo.**

## What lives where

| Thing | Location |
|---|---|
| sra (the tool) | this repo, installed into Finablo's dev environment as a package |
| Finablo's Product Contract | `finlearn/.sra/` in Finablo's own (private) repo |
| Run artifacts | `finlearn-local-evidence/sra-runs/` (outside both repos) |
| This note | only the generic adoption steps, so other apps can copy them |

## Adoption steps (generic)

1. Boot two builds locally: base (`main`) and head (the release branch), on two ports.
2. Provide a test-data hook. For Finablo: the guest assessment API plus the dev-only login code endpoint, which already exist for QA. Both run against local only.
3. `sra onboard --url http://localhost:8080 --docs <docs> --voice owner-note.m4a`, then review and commit `.sra/` in the app's repo.
4. `sra audit --base http://localhost:8080 --head http://localhost:8081 --notes <release notes>`.

## Finablo-specific constraints (carried from Finablo's rules)

- Local only. Never run against `app.finablo.com`.
- Do not push Finablo branches for this work (limited CI minutes).
- Skip the Sage chat surface unless the owner approves its Claude spend.
- The auditor's own model calls (Meta credits) are separate from Finablo's Anthropic budget.

## Target for the hackathon

Recreate one real historical cross-surface bug on a local branch and catch it blind. Candidate: the pending-page 401(k) limit for a 61-year-old ($24,500 shown, $35,750 correct). The contract must be produced by `sra onboard`, not hand-coded with knowledge of the bug.
