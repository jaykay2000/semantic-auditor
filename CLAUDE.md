# Semantic Auditor: working rules for agents

Read [README.md](README.md), [HACKATHON.md](HACKATHON.md), [docs/03-architecture.md](docs/03-architecture.md) and [docs/07-implementation-plan.md](docs/07-implementation-plan.md) first. The unit of analysis is the **User Experience Story**; fact comparison is one layer inside it.

## Hard rules

- **New work only.** Never copy code from Finablo (`~/Documents/src/finlearn`) or any other private repo into this one. Ideas are fine; record them in the HACKATHON.md provenance ledger.
- **No consumer specifics in `src/semaudit/`.** Anything Finablo- or Northbound-specific goes in that app's `.semaudit/` contract, or in `examples/` / `integrations/`. If the core needs an `if app == …`, the contract schema is missing a concept.
- **Roles, not models.** Call `semaudit.models.complete(role=…)`. Never name a model ID outside `semaudit.toml` / `semaudit/models/`.
- **Deterministic where possible.** Joins, normalization, arithmetic, diffs, conditions and deterministic checks are code. Models extract and judge.
- **Severity, confidence and verification are separate fields.** Never derive one from another or merge them in the UI. A check that cannot measure exits 2, never 0.
- **Nothing suppresses broadly.** Owner "accept" creates a scoped, expiring exception; a deterministic check only for an expressible rule.
- **Blind benchmark.** The session building the auditor must not read sealed ground truth or the `bench-NN` release diffs (they live outside the repo until scoring). The narrative fixture (Northbound 2.4) is public and is never used for headline numbers.
- **Data policy.** Finablo runs: synthetic profiles, Standard-mode endpoints only.
- **Budget.** Every run takes `--max-usd`. Never run against a production system. Never call Finablo's Sage chat without the owner's approval.
- **Push and publish only when the owner says so.**

## Stack

Python 3.12, Playwright, Pydantic v2, Typer, httpx, Jinja2, pytest. Demo app: FastAPI + Jinja + fpdf2.

## Layout

See README.md. Run artifacts go to `runs/` (gitignored, except runs promoted to `bench/results/` or `docs/demo-runs/`).
