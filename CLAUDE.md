# Semantic Release Auditor: working rules for agents

Read [README.md](README.md), [HACKATHON.md](HACKATHON.md) and [docs/07-implementation-plan.md](docs/07-implementation-plan.md) first.

## Hard rules

- **New work only.** Never copy code from Finablo (`~/Documents/src/finlearn`) or any other private repo into this one. Ideas are fine; record them in the HACKATHON.md provenance ledger.
- **No consumer specifics in `src/sra/`.** Anything Finablo- or Northbound-specific goes in that app's `.sra/` contract, or in `examples/` / `integrations/`. If the core needs an `if app == …`, the contract schema is missing a concept.
- **Roles, not models.** Call `sra.models.complete(role=…)`. Never name a model ID outside `sra.toml` / `sra/models/`.
- **Deterministic where possible.** Joins, normalization, arithmetic, diffs and ratchet checks are code. Models extract and judge.
- **Nothing unverified is reported as CONFIRMED.** A check that cannot measure exits 2, never 0.
- **Blind benchmark.** The session building checkers must not read `bench/ground_truth/` or the Northbound v2 seeding notes.
- **Budget.** Every run takes `--max-usd`. Never run against a production system. Never call Finablo's Sage chat without the owner's approval.
- **Push and publish only when the owner says so.**

## Stack

Python 3.12, Playwright, Pydantic v2, Typer, httpx, Jinja2, pytest. Demo app: FastAPI + Jinja + fpdf2.

## Layout

See README.md. Run artifacts go to `runs/` (gitignored, except runs promoted to `bench/results/` or `docs/demo-runs/`).
