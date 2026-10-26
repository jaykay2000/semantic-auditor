# 4. Onboarding flow: learning the product

**Goal:** turn "here is my app" into an owner-approved **Product Contract** in under an hour of owner time. For the demo, the target is under 10 minutes.

## Inputs

| Input | Required | Used for |
|---|---|---|
| App URL (base build) + optional login/test-data hook | yes | exploration, journeys, oracle discovery |
| Docs: README, help pages, pricing/policy pages, PRDs, API spec (OpenAPI) | recommended | facts, policies, oracle paths |
| Owner interview: a 2–5 minute voice note, or typed answers to generated questions | recommended | expectations, personas, what "wrong" means |
| Known past bugs (issue links, retros) | optional | seeds invariants; becomes benchmark events |

## Steps

```
1 INGEST ─► 2 EXPLORE ─► 3 DRAFT ─► 4 INTERVIEW ─► 5 REVIEW ─► 6 BASELINE
   docs       map app      contract   fill gaps     owner        record journeys,
   voice      surfaces     v0         ask owner     approves     first clean run
```

### 1. Ingest
- Docs and the API spec are chunked and read in one long-context pass by the `mapper` (Muse Spark, 1M context; PDF and image inputs accepted).
- The voice note is transcribed by Muse Voice Transcribe. The mapper extracts **expectation statements** ("a traveller must never see two prices") and **persona hints** ("our tricky users are families and anyone paying in euros").

### 2. Explore
- The `explorer` agent (Muse Spark with browser tools: navigate, click, fill, read, screenshot) walks the app from the entry URL, with a step budget.
- It records each **surface** it reaches (page, modal, generated email in the sink, downloadable PDF, chat), the **journey** that reached it as replayable steps, and the **network calls** made along the way. The network calls are the candidate **oracles** (JSON fields whose values match what the screen shows).
- **Oracle discovery is mostly code:** for each number or date on a screen, search the captured API responses for a matching value (with format normalization). A match proposes an oracle path. The owner confirms it.

### 3. Draft contract v0
The mapper proposes:
- `surfaces.yaml`: every surface reached, with kind and journey.
- `facts.yaml`: recurring quantities and conclusions seen on ≥2 surfaces, or named in docs, each with an oracle when one was found.
- `personas.yaml`: **axes** (the dimensions that change what the product should say), found from form fields, pricing tiers, policy branches and the interview; plus 3–6 archetypes.
- `invariants.yaml`: one `same_value_across_surfaces` per multi-surface fact, `grounded` rules for AI-generated surfaces, and conditional rules from the owner's expectations.

Each proposed item carries **provenance** (the doc span, screenshot or transcript line it came from) and a **confidence**.

### 4. Interview (gap-filling)
The auditor asks the owner only what it cannot infer, as a short list of concrete questions:
- "Checkout shows `$1,284` and the email `$1,284.00`. Should the email ever show a compact form such as `$1.3K`?"
- "Is `cancel_deadline` in the traveller's timezone or the airline's?"
- "The concierge mentioned 'price guarantee'. Is that a real policy? Where is its source of truth?"

Answers can be spoken (Muse Voice Transcribe) or typed. Each answer edits the contract with provenance.

### 5. Owner review
- `sra contract review` renders an HTML page: each surface with its screenshot and extracted claims highlighted, each fact with its oracle and the surfaces that render it, each invariant in plain English ("Every surface shows the same trip total for the same traveller"), and an approve / edit / reject control per item.
- The approved contract is written to `.sra/` and committed in the customer's repo. **Nothing becomes a rule without approval.**

### 6. Baseline
- Replay all journeys for the generated personas on the base build. Run every checker. Anything found here is either a **pre-existing bug** (reported) or a contract error (fixed in review).
- The result is the first **clean claim graph**. Later audits diff against it.

## Incremental learning (after day one)

Onboarding never fully ends. Every audit feeds back:
- **UNKNOWN_CLAIM** findings become interview questions ("A new claim, 'price guarantee', appeared on checkout. Add it as a fact? Where is its truth?").
- **New surfaces** found by journey repair are proposed as additions.
- **REJECTED** candidates with an owner-supplied reason become allowlist entries or refined invariants.
- **CONFIRMED** findings become ratchet checks (see the audit workflow).

The contract improves over time, and this is the property a one-shot prompt cannot have.

## Onboarding output, as files

```
.sra/
  product.yaml        name, summary, owner expectations (with transcript provenance)
  surfaces.yaml
  facts.yaml          facts + oracles + tolerance/formatting policy
  personas.yaml       axes, archetypes, generation strategy, test-data hook
  invariants.yaml
  journeys/*.json     recorded, replayable steps
  allowlist.yaml      accepted divergences, each with reason + owner + expiry
  checks/             (empty until the first confirmed finding)
  CONTRACT.md         generated human-readable summary
```

## Acceptance criteria for the hackathon

- On Northbound: from URL + docs + a 60-second voice note to an approved contract with ≥90% of the hand-written reference contract's facts and surfaces. Measured, not eyeballed: `bench/` holds the reference contract.
- On Finablo: a draft contract that finds at least the report, dashboard, PDF, email and export surfaces, and at least 6 of its 10 known cross-surface facts, without any Finablo-specific code.
