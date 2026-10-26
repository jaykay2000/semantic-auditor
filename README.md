# Semantic Auditor

**Every feature passed. The release still failed its users.**

The Semantic Auditor **reconstructs what a particular user experiences across a release, identifies conflicting product behavior and messages, and gives the owner reproducible evidence to make a shipping decision.**

Users don't experience features; they experience a release. Each feature can pass its own tests and say only true things, and together they can still hand one traveller two different plans in the same few minutes: *wait for a price drop* (a correct forecast) and *lock this fare, 2 seats left* (a correct seat count). Nothing helps her weigh them. They can also second-guess a purchase she can no longer change.

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

**Release-level issues** (no single feature is wrong; the experience is):

| Kind | Example |
|---|---|
| Unexplained tradeoff (coherence) | Price Watch: "likely to drop, we suggest waiting" · Fare Lock: "2 seats left at this fare. Lock it for 48 h for €9". Both true and compatible, but nobody explains that the lock expires long before the drop window |
| Conflicting directives (coherence) | Price Watch: "wait" · Fare Lock's urgent variant: "Book now". Incompatible and unreconciled |
| Stale guidance | after booking: "Keep waiting to book. We'll tell you when prices drop." |
| Rule breach for this persona | urging immediate booking on a trip six months away, which the owner's rule forbids for non-imminent trips |
| Attention load | four non-booking messages in 24 hours |

**Factual issues** (the conventional layer, still checked):

| Kind | Example |
|---|---|
| Fact divergence | the lock is shown at €9, and a couple buying it is charged €18 |
| False claim | "only 2 seats left" when inventory shows 9 |

What it deliberately **does not** raise:
- urgency that an approved exception permits, with every condition met (departs within 72 h, seat count true, tradeoff explained);
- an explained tradeoff;
- messages that are never live at the same time;
- persona-specific facts;
- transactional repetition;
- actionable post-purchase offers.

An exception to one rule never excuses another: permitted urgency can still be raised for incoherence.

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
src/semaudit/      adapters · models · contract · onboard · explore · extract · graph (claims)
              · story · relate · check (deterministic) · verify · decide · report · bench
examples/     Northbound: a fictional multi-feature travel app (2.3 / 2.4 / 2.4.1)
bench/        frozen-fixture protocol, baselines, results
integrations/ how a consumer app adopts the auditor (first: Finablo)
docs/         design documents
```

## Status

Built during the Meta Global AI Developer Hackathon (Oct 26 – Nov 4, 2026). License to be chosen before the repo goes public (Apache-2.0 proposed).
