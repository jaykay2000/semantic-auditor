# 4. Onboarding: learning the product and the owner's intent

**Goal:** an owner-approved **Product Contract** that is complete enough to reconstruct a user's experience and judge it against the owner's own rules. Target: under an hour of owner time; under 10 minutes for the demo app.

## Inputs

| Input | Required | Feeds |
|---|---|---|
| App URL (base release) + persona hook + clock hook | yes | surfaces, scenarios, state, oracles |
| Docs: product vision, help and policy pages, pricing, API spec | recommended | principles (draft), facts, oracles, decisions |
| Owner voice note (2–5 min) or typed answers | recommended | principles, conditions, exceptions, persona hints |
| Feature list: release notes, a flag registry or design-system attribution | recommended | feature attribution |

**Leakage control for evaluations:** when onboarding is used to *test* the auditor on a historical release, it may only see inputs that existed **before** that release. Any doc that describes the bug being tested is excluded, and so is a voice note recorded today, which is not contemporaneous knowledge. The input list with its commit SHAs is recorded in the run (see [08-evaluation.md](08-evaluation.md)).

**Voice is optional.** The auditor's core runs on a written principles draft. The voice step is an onboarding convenience and a demo enhancement.

## Steps

```
1 INGEST ─► 2 MAP ─► 3 DRAFT ─► 4 SHARPEN PRINCIPLES ─► 5 REVIEW ─► 6 BASELINE
```

### 1. Ingest
- The voice note is transcribed with Muse Voice Transcribe. Docs and API specs are read by Muse Spark in one long-context pass.
- Out come **intent statements** with their sources (a transcript timestamp or doc span), persona hints, and named features.

### 2. Map
- The explorer (Muse Spark with browser tools) walks the app within a step budget, recording surfaces, the steps that reached them (replayable), network calls, and the feature attribution available on each surface.
- Oracle discovery is code: each value on a screen is matched against the captured API responses, and a match proposes an oracle path.
- **Hackathon scope:** for Northbound, a recorded walk plus automated oracle discovery is enough. Autonomous mapping of an unknown app is phase P2 (see the plan).

### 3. Draft the contract
The model proposes, each item with its provenance and a confidence:
- `features.yaml`: features and how to attribute a message to them.
- `decisions.yaml`: the user decisions the product guides; their **actions**; which actions are **incompatible**; each action's **preconditions**.
- `personas.yaml`: axes, archetypes and the **state** that matters (booked? departure time?).
- `scenarios.yaml`: time-ordered scripts covering the important journeys, including the time after the user acts.
- `surfaces.yaml`, `facts.yaml` (with oracles), `rules.yaml` (expressible checks).
- `principles.yaml`: drafts from the intent statements.

### 4. Sharpen principles (the step that matters most)
Owners speak in absolutes ("we never pressure travellers"). An absolute rule cannot tell an acceptable message from an unacceptable one, so the auditor splits each intent statement into operational rules of **three kinds**:

| Kind | Meaning | Exceptions? |
|---|---|---|
| **Universal prohibition** | never true to break, for anyone (e.g. "never state a scarcity claim our data doesn't support") | none |
| **Conditional rule** | forbidden by default; permitted only through a scoped exception whose conditions are data (checked by code) or judged (checked by model and verifier) | scoped, with expiry and approver |
| **Coherence rule** | about the *relationship* between features (e.g. "features that advise on the same decision must agree or explain the tradeoff") | none; an exception to another rule never excuses it |

It asks the owner targeted questions to get there, including **boundary** questions:
> "You said you never pressure travellers. Fare Lock shows '2 seats left'. Is sharing a true seat count always fine? When, if ever, may it urge booking now: a trip within days? What about fixed dates six months away? Must the banner explain the tradeoff?"

**Example result (Northbound's written draft):**
> **U1.** Every scarcity, price and policy claim matches our own data.
> **P1.** We may always share verified inventory information. We do not urge immediate action, except for genuinely time-sensitive trips.
> **P1-E1.** All of: departure within 72 h of the message, compared on exact timestamps (fixed dates alone do not qualify); the inventory claim matches inventory; the message explains the tradeoff. Scope: Fare Lock on fare detail and checkout. Expires 2027-01-31.
> **P2.** When more than one feature gives an active recommendation about the same decision, the product must reconcile incompatible actions, or explain the material tradeoffs between otherwise compatible actions.

The owner also labels each pair of actions on a decision as **incompatible** (book now vs wait) or a **material tradeoff** (lock vs wait). That label decides whether an unexplained pair is a `conflict` or an `unexplained_tradeoff`, so the model is never forced to call compatible advice a contradiction.

Each rule also gets a short list of **boundary cases** the owner confirms (the Maya / Raj / Kai / Hana / Omar table in [examples/northbound](../examples/northbound/README.md)). These become test fixtures.

### 5. Owner review
`semaudit contract review` renders one HTML page:
- each principle in plain English, with its conditions as a checklist and its source (the audio timestamp plays the clip);
- each exception with its scope;
- each decision's actions and incompatibilities;
- each feature with an example of an attributed message;
- each fact with its oracle.

Each item can be approved, edited or rejected. **Nothing becomes a rule without approval.** The approved contract is committed to the consumer's repo.

### 6. Baseline
- Run the scenarios on the base release and build its stories.
- Issues found here are **pre-existing**. They are reported as such, or they reveal a contract error that is fixed in review.
- The base stories become the reference for the first release review's delta.

## Incremental learning

After every review:
- unknown directive vocabulary, new surfaces, unmapped claims and exception conditions that evaluated as *unknown* become **owner questions**;
- owner dispositions update the memory (see [05-audit-workflow.md](05-audit-workflow.md), step 10): scoped exceptions, approved expectations, and deterministic checks only for expressible rules.

## Output

```
.semaudit/
  product.yaml            name, summary, sources
  principles.yaml         operational principles + scoped exceptions (with audio/doc provenance)
  features.yaml
  decisions.yaml          decisions, actions, incompatibilities, preconditions
  personas.yaml           axes, archetypes, state
  scenarios.yaml          time-ordered scripts
  surfaces.yaml
  facts.yaml              facts + oracles + formatting policy
  rules.yaml              expressible rules (deterministic)
  release_policy.yaml     severity x confidence x verification -> recommendation
  checks/                 deterministic checks from owner "rule" decisions
  expectations/           approved semantic expectations
  dispositions.yaml       owner decisions on issues and releases (semaudit decide; W11)
  CONTRACT.md             generated readable summary
```

## Acceptance for the hackathon

- **Northbound:** from the voice note and docs to an approved contract in under 10 minutes of owner time, matching the hand-written reference contract on principles, exceptions, decisions and features. The reference sits in `bench/` and is compared item by item.
- **Finablo:** a contract built only from the dated inputs. It must include at least the report, dashboard, PDF and export surfaces, the first-move and freedom-age decisions and facts, and principles drafted from `VISION.md`. The owner reviews it.
