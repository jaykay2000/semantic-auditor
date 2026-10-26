# Semantic Release Auditor

> Working name. The public name is pending (likely **Semantic Auditor**); see [docs/decisions.md](docs/decisions.md).

**Every feature passed. The release still failed its users.**

The Semantic Release Auditor **reconstructs what a particular user experiences across a release, identifies conflicting product behavior and messages, and gives the owner reproducible evidence to make a shipping decision.**

Users don't experience features; they experience a release. Each feature in a release can pass its own tests and evals, and together they can still tell one traveller to *wait for a price drop* and *book now, only 2 seats left* on the same afternoon. They can second-guess a purchase the traveller can no longer change, or apply urgency to exactly the people the product promised not to pressure.

The auditor finds those **semantic release issues**. It tells them apart from legitimate tradeoffs and owner-approved exceptions. It gives the owner a release review: ranked issues, each with evidence that replays on demand, and a Ship / Hold recommendation.

## How it works

```
 owner voice note + docs ──► PRODUCT CONTRACT: operational principles with scoped exceptions,
                             features, decisions, personas + state, scenarios, facts + oracles
                                         │
 base release ─┐                         ▼
 head release ─┴─► scenario runner (simulated time) ──► captures + state per step
                                         │
                   deterministic checks ─┤ (no model)
                                         ▼
                   messages · directives · claims  (Muse Spark Open)
                                         ▼
                   USER EXPERIENCE STORY per persona: time-ordered events, base ↔ head aligned
                                         ▼
                   code proposes candidate conflicts ──► Muse Spark interprets them against
                   principles & exceptions: conflict / tradeoff / exception applies / compatible
                                         ▼
                   issues: severity · confidence · verification (separate) ──► verifier
                                         ▼
                   Release Story view · repro · Ship / Hold recommendation ──► owner decision ──► memory
```

## What it looks for

| Kind | Example |
|---|---|
| Competing directives | Price Watch: "wait for a drop" · Fare Lock: "only 2 seats, lock now" |
| Stale guidance | after booking: "we'll tell you when to book" |
| Principle breach | scarcity pressure on a flexible traveller, against the owner's rule |
| Unexplained tradeoff | "prices may drop" and "seats are limited", never reconciled for the user |
| Attention load | four non-booking messages in 24 hours |
| Fact divergence | lock fee €9 on the banner, €12 at checkout |
| Unsupported assertion | "only 2 seats left" when inventory shows 9 |

And what it deliberately **does not** raise: an approved exception whose conditions are all met (the same banner for a traveller departing tomorrow, with real seat counts and the tradeoff explained), an explained tradeoff, messages that are never live at the same time, persona-specific facts, transactional repetition, and actionable post-purchase offers.

## Documents

1. [Vision](docs/01-vision.md)
2. [Problem](docs/02-problem.md)
3. [Architecture](docs/03-architecture.md)
4. [Onboarding](docs/04-onboarding.md)
5. [Release review workflow](docs/05-audit-workflow.md)
6. [Demo](docs/06-demo-vision.md)
7. [Implementation plan](docs/07-implementation-plan.md)
8. [Evaluation](docs/08-evaluation.md)

Also: [Decisions](docs/decisions.md) · [Hackathon compliance and provenance](HACKATHON.md) · [Northbound demo app](examples/northbound/README.md) · [Benchmark](bench/README.md) · [Finablo integration](integrations/finablo/README.md)

## Built with Meta models

| Role | Model |
|---|---|
| Interpret candidate conflicts against owner principles; explore and repair journeys | **Muse Spark** (Meta Model API) |
| Extract messages, directives and claims at volume; independent defense and cross-check | **Muse Spark Open** (open weights, Modal / Baseten) |
| Turn the owner's spoken intent into draft principles | **Muse Voice Transcribe** |

## Layout

```
src/sra/      adapters · models · contract · onboard · explore · extract · graph (claims)
              · story · relate · check (deterministic) · verify · decide · report · bench
examples/     Northbound: a fictional multi-feature travel app (2.3 / 2.4 / 2.4.1)
bench/        frozen-fixture protocol, baselines, results
integrations/ how a consumer app adopts the auditor (first: Finablo)
docs/         design documents
```

## Status

Built during the Meta Global AI Developer Hackathon (Oct 26 – Nov 4, 2026). License to be chosen before the repo goes public (Apache-2.0 proposed).
