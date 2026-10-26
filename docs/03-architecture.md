# 3. Architecture and approach

## Design stance

Models are good at **reading** (a screenshot, a PDF, a paragraph of AI prose) and at **judging** fuzzy questions (is this advice wrong for this person?). Code is good at **coverage**, **joins**, **arithmetic**, **diffs** and **memory**. The auditor uses each for what it is good at:

```
           model                          code                        model                 code
explore ──► read & extract claims ──► normalize, join, diff ──► judge fuzzy cases ──► verify, record, ratchet
```

No finding is ever "the model said so". Each one is a structured claim comparison with evidence, which a model helped produce and code checked.

## Components

```
                 ┌──────────────────────────── PRODUCT CONTRACT (.sra/ in the customer repo) ────────────────────────────┐
                 │ product · surfaces · facts+oracles · personas+axes · invariants · journeys · allowlist · checks/   │
                 └────────▲───────────────────────────────▲──────────────────────────────────▲──────────────────────────┘
                          │ drafts / owner approves       │ reads                            │ appends (ratchet)
   ┌──────────────┐  ┌────┴─────┐  ┌──────────┐  ┌─────────┴──┐  ┌──────────┐  ┌──────────┐  ┌───┴──────┐  ┌──────────┐
   │  adapters    │─►│ onboard  │  │ explore  │─►│  extract   │─►│  graph   │─►│  check   │─►│  verify  │─►│  report  │
   │ web/email/   │  │ ingest,  │  │ personas,│  │ claims →   │  │ claim    │  │ 6 finding│  │ repro,   │  │ evidence │
   │ pdf/api/chat │  │ map,     │  │ journeys │  │ normalized │  │ graph +  │  │ families │  │ x-model, │  │ packets, │
   │ (ios later)  │  │ interview│  │ replay + │  │ JSONL      │  │ diff     │  │          │  │ defense  │  │ HTML     │
   └──────────────┘  └──────────┘  │ repair   │  └────────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
                                   └──────────┘           models/ router: role → model, cache, cost ledger
```

| Package | Responsibility |
|---|---|
| `sra.adapters` | Capture a surface as a **Capture**: screenshot(s), DOM text + element boxes, raw payload (email HTML, PDF bytes, JSON, chat transcript), URL, timestamp, build id, persona id. Web: Playwright. Email: a file/SMTP sink the app writes to. PDF: bytes + text layer + rendered pages. API: JSON. Chat: scripted conversation. iOS (stretch): simulator screenshot + accessibility tree. |
| `sra.models` | One interface `complete(role, messages, schema=…)`. Maps **roles** to models via config, caches by content hash, retries, records tokens and $ per call in a ledger. No module names a model directly. |
| `sra.contract` | Pydantic schema for the Product Contract; load, validate, diff, version. |
| `sra.onboard` | Ingest docs / URL / voice note → explore → draft contract → owner review loop. See [04-onboarding.md](04-onboarding.md). |
| `sra.explore` | Persona generation from contract axes. Journey replay (recorded at onboarding), with agent **repair** when a script breaks or a new surface appears. |
| `sra.extract` | Capture → list of **Claims**, mapped to contract facts or marked *unmapped*. |
| `sra.graph` | Claim graph indexed by (build, persona, fact, surface). Semantic diff between builds. |
| `sra.check` | Finding families (below). Deterministic first, model judge only where needed. |
| `sra.verify` | Turns candidates into CONFIRMED / PLAUSIBLE / REJECTED with reasons. |
| `sra.diff` | Release-notes / PR intent → intended-change list; classifies each semantic change. |
| `sra.report` | Evidence packets (JSON + HTML), run report, PR-comment markdown. |
| `sra.ratchet` | Confirmed finding → deterministic check in `.sra/checks/`; runs checks first on every audit. |
| `sra.bench` | Seeded ground truth, the one-prompt baseline, ablations, scoring. |

## The Product Contract

The core asset. It holds what a prompt cannot: intent, truth and memory. It lives in the **customer's** repo at `.sra/` and is reviewed like code.

```yaml
# .sra/product.yaml
name: Northbound
summary: Book flights and hotels; AI concierge answers trip questions.
owner_expectations:          # distilled from the owner interview, each linked to invariants
  - id: E1
    text: "A traveller must see one total price everywhere, fees included."
    invariants: [INV-total-consistent]

# .sra/surfaces.yaml
- id: checkout
  kind: web_page
  journey: J-book            # how to reach it
- id: confirmation_email
  kind: email
  journey: J-book
  capture: {sink: outbox, match: {subject_contains: "Your trip"}}
- id: itinerary_pdf
  kind: pdf
- id: concierge
  kind: chat
  ai_generated: true         # claims here get the "unsupported" check by default

# .sra/facts.yaml — the things the product asserts
- id: trip_total
  type: money
  unit: booking_currency
  oracle: {kind: api, path: "GET /api/bookings/{id} :: $.total"}   # where truth lives
  tolerance: {abs: 0.5}      # or a formatting policy: compact "$1.2K" == 1,199..1,249
  surfaces: [checkout, confirmation_page, confirmation_email, itinerary_pdf, concierge]
- id: cancel_deadline
  type: datetime
  oracle: {kind: api, path: "$.cancellation.deadline"}
  normalize: {timezone: traveller_local}

# .sra/personas.yaml — archetypes + the axes that change what the product should say
axes:
  fare: [refundable, non_refundable]
  party: [solo, couple, family_with_kids]
  currency: [USD, EUR, JPY]
  loyalty: [none, gold]
archetypes:
  - {id: P-solo-eur, fare: non_refundable, party: solo, currency: EUR}
generation: {strategy: pairwise_plus_edges, max: 8}

# .sra/invariants.yaml — rules that must always hold
- id: INV-total-consistent
  kind: same_value_across_surfaces
  fact: trip_total
- id: INV-no-family-upsell-solo
  kind: conditional_absence
  when: {persona.party: solo}
  forbid: {claim_topic: family_perks}
- id: INV-refund-truth
  kind: grounded
  surfaces: [concierge]
  claim_topic: cancellation_policy
  must_match_fact: cancel_policy

# .sra/allowlist.yaml — accepted divergences, each with a reason and an expiry
# .sra/journeys/*.json — recorded, replayable steps per journey
# .sra/checks/*.yaml  — ratchet output (deterministic regression checks)
```

### Claim (output of extraction)

```json
{
  "claim_id": "c_8f2…", "run": "r_…", "build": "v2", "persona": "P-solo-eur",
  "surface": "confirmation_email", "fact": "trip_total",
  "value": 1248.00, "unit": "EUR", "raw_text": "Total paid: €1,248.00",
  "qualifiers": {"includes_fees": true},
  "topic": "price", "polarity": "assert",
  "locator": {"kind": "dom", "selector": "#total", "bbox": [412, 880, 590, 912]},
  "extractor": "muse-spark-open-1026", "confidence": 0.97
}
```

`fact: null` means **unmapped**: the product said something the contract does not know about. Unmapped claims are a signal in their own right (see onboarding, incremental learning).

## Finding families

| Family | Detected by | Deterministic? |
|---|---|---|
| **CONTRADICTION**: same persona, same fact, different values on two surfaces | graph join on (build, persona, fact) | yes, after normalization |
| **ORACLE_MISMATCH**: surface value ≠ oracle value | compare claim to oracle fetch | yes |
| **UNSUPPORTED**: claim not entailed by any fact, oracle or contract rule (default for `ai_generated` surfaces) | entailment judge with the contract + oracle snapshot as the only allowed evidence | model judge, then verified |
| **PERSONA_MISFIT**: violates a conditional invariant or an owner expectation for this persona | rule engine for explicit invariants; judge for expectations written in prose | mixed |
| **SEMANTIC_REGRESSION**: a (persona, surface, fact) cell changed between builds and no intended change explains it | graph diff + intent matching | diff yes, intent match by model |
| **UNKNOWN_CLAIM**: a new unmapped claim appeared in head | extraction + graph diff | yes; routed to the owner as a contract question, not a bug |

## Verification (precision)

Every candidate goes through the steps that apply to it before it can be reported:

1. **Re-capture.** Replay the journey fresh. A finding that does not reproduce is FLAKY and is not reported as a bug.
2. **Cross-model re-extraction.** A second, different model (Muse Spark if the first was Muse Spark Open, or the reverse) re-reads the evidence crop. The two must agree on the value.
3. **Deterministic recompute.** Re-normalize units, timezones and formatting policy. Re-fetch the oracle.
4. **Defense pass** (judged families only). A model is asked to *explain the finding away* using the contract, allowlist and release intent. If it produces a valid explanation (for example, "family perks shown because the persona's party includes kids"), the candidate is REJECTED with that reason attached.
5. **Verdict.** CONFIRMED (all applicable steps pass) · PLAUSIBLE (judge-only, shown separately) · REJECTED (kept in the report, with its reason, for transparency).

## Model routing (roles, not models)

| Role | Default model | Why |
|---|---|---|
| `explorer` (navigate unknown UI, repair journeys) | Muse Spark (vision + tool calling) | needs screen understanding and actions |
| `mapper` (onboarding: draft surfaces, facts, invariants) | Muse Spark (1M context, PDF/image input) | reads all docs + captures at once |
| `extractor` (capture → claims, high volume) | **Muse Spark Open 1026** (open weights, Baseten/Modal) | cheap, fast, self-hostable; structured output |
| `cross_extractor` (verification) | Muse Spark | a *different* model, so agreement means something |
| `judge` (unsupported, persona fit, intent match) | Muse Spark | reasoning over contract + evidence |
| `defender` (explain-it-away pass) | Muse Spark Open | independent of the judge |
| `transcriber` (owner voice interview) | Muse Voice Transcribe | spoken onboarding |
| `segmenter` (pixel-ground claims without DOM) | SAM 3.1 (stretch) | PDFs rendered as images, email images, iOS |

All model capabilities above are **to be verified on day 1** (see the implementation plan). The router makes any role swappable via `sra.toml` without code changes.

## Determinism, cost and reproducibility

- Every model call is cached by (role, model, prompt hash, image hashes). Re-running a report re-uses extractions, so a rerun costs $0 and gives identical output.
- Each run writes `runs/<id>/` holding captures, `claims.jsonl`, `graph.json`, `candidates.jsonl`, `findings/*.json`, `ledger.json` (tokens and $ per role) and `report.html`.
- **Ratchet first:** existing checks in `.sra/checks/` run before any model call. They are pure code over captures and oracle fetches.
- **Budget guard:** `--max-usd` per run. Extraction is batched per capture, and only cells that changed between builds go to the judge.

## Integration surface for consumers

A consumer app provides three things, and nothing more:

1. **A way to run two builds.** Two URLs (staging/base, preview/head), or a command that boots a build by git ref.
2. **Test-data hooks** (optional but recommended): an endpoint or script that creates a persona's account and data. Without it, the explorer fills forms itself.
3. **Its contract**: `.sra/` in its repo, created by `sra onboard`.

Outputs: an exit code (`0` clean · `1` confirmed findings · `2` could not measure), a report, and a PR-comment markdown. A GitHub Action wrapper is a stretch goal.

## Tech stack

Python 3.12 · Playwright (Chromium) · Pydantic v2 · Typer (CLI) · httpx (OpenAI-compatible chat endpoints for both the Meta Model API and Baseten/Modal; to verify) · Jinja2 (report) · pypdf / pdfplumber (PDF text) · pytest. Demo app: FastAPI + Jinja templates + fpdf2, no frontend build step.
