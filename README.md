# Semantic Release Auditor

> Working name. `semantic-release` is already a well-known npm release tool, so the public name is an open decision. See [docs/decisions.md](docs/decisions.md).

**Your release passed every test, and it still tells the same user two different stories.**

The Semantic Release Auditor (`sra`) is an open-source, agentic auditor for product *meaning*. It first learns what your application is supposed to say: its surfaces, personas, facts and promises. Then, on every release, it checks whether the product still tells each user one true, consistent story across every surface. That covers web pages, emails, PDFs, AI assistants and API responses.

It catches the bugs functional QA cannot see:

| Finding | Example |
|---|---|
| **Contradiction** | Checkout says **$1,284**; the confirmation email says **$1,248**. |
| **Oracle mismatch** | The page says you can cancel until **Mar 3**; the booking record says **Mar 1**. |
| **Unsupported claim** | The AI concierge promises "free cancellation anytime" on a non-refundable fare. |
| **Persona misfit** | A solo traveller is upsold "kids eat free". A debt-free user is told to pay down debt. |
| **Unexplained semantic change** | Baggage allowance moved from 23 kg to 20 kg on the PDF only, and the release notes say nothing. |
| **Unknown claim** | A new "price guarantee" badge appears that the product owner never defined. |

## How it works

```
 ONBOARD (once, then incrementally)          AUDIT (every release)
 ─────────────────────────────────          ────────────────────────────────────────────
 docs + URL + owner voice note               base build ─┐
        │                                    head build ─┼─► personas × surfaces × builds
        ▼                                                │         (scripted replay, agent repair)
 explorer agent maps surfaces                            ▼
        │                                    claims extracted + normalized (open-weights model)
        ▼                                                ▼
 PRODUCT CONTRACT  ◄── owner reviews ──┐     claim graph ──► checkers ──► verifier ──► evidence packets
 (facts, oracles, personas,            │                                                    │
  invariants, journeys)  ◄─────────────┴──── confirmed findings become deterministic checks ┘
```

The **Product Contract** is a versioned set of YAML files that lives in your repo. It is what turns one-off model judgement into a system that remembers intent, knows what changed, verifies before it reports, and gets cheaper with every release.

## Status

Hackathon build: Meta Global AI Developer Hackathon, Oct 26 – Nov 4, 2026. Start with these:

- [Vision](docs/01-vision.md)
- [Problem](docs/02-problem.md)
- [Architecture](docs/03-architecture.md)
- [Onboarding flow](docs/04-onboarding.md)
- [Audit workflow](docs/05-audit-workflow.md)
- [Demo vision](docs/06-demo-vision.md)
- [Implementation plan](docs/07-implementation-plan.md)
- [Decisions](docs/decisions.md)
- [Hackathon compliance and provenance](HACKATHON.md)

## Built with Meta models

| Role | Model |
|---|---|
| Explorer, planner, persona-fit judge, intent reader | Muse Spark (Meta Model API) |
| High-volume claim extraction, independent verifier | Muse Spark Open (open weights; Baseten / Modal) |
| Owner onboarding interview | Muse Voice Transcribe |
| Grounding claims to pixels where there is no DOM (PDF, email images, iOS) | SAM 3.1 (stretch) |

## Layout

```
src/sra/        the auditor (adapters, models, contract, onboard, explore, extract,
                graph, check, verify, diff, report, ratchet, bench)
examples/       Northbound, a fictional multi-surface travel app with seeded releases
bench/          ground truth + baseline-vs-system scoring
integrations/   how a consumer app (first: Finablo) adopts sra
docs/           design documents
```

## License

To be decided before the repo goes public (Apache-2.0 recommended). See [docs/decisions.md](docs/decisions.md).
