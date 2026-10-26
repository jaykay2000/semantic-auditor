# 3. Architecture

## Product thesis (the architecture serves this sentence)

> **The Semantic Auditor reconstructs what a particular user experiences across a release, identifies conflicting product behavior and messages, and gives the owner reproducible evidence to make a shipping decision.**

The **unit of analysis is the User Experience Story**: one persona's time-ordered experience of one release, across features and surfaces. Checking that facts agree across surfaces is still part of the system, but as one layer inside the story rather than as the product.

## Design stance

| Code does | Models do |
|---|---|
| drive scenarios, advance the clock, capture surfaces, snapshot state | read a capture and say what the product told the user |
| order events in time, track state, join events into candidate relations | decide whether a candidate relation is a conflict, a tradeoff or compatible |
| evaluate exception conditions that are data (persona attributes, state, oracle values) | judge soft conditions ("does this explain the tradeoff?") |
| normalize and compare facts; diff two releases' stories | propose relations the generators missed (lower confidence) |
| link every claim in an issue to a capture and a locator; replay episodes | play the defense: try to explain an issue away |
| combine severity, confidence and verification into a recommendation using the owner's policy | — |

Code narrows the search space and makes everything reproducible. Models interpret meaning. This is deliberately not "a model judge looks at everything".

## Layers

```
 L0 CONTRACT    principles (+conditions, +scoped exceptions) · features · decisions & actions · personas+state
                · scenarios · surfaces · facts+oracles · rules · release policy · owner dispositions
                                   │ drives every layer below
 L1 CAPTURE     scenario runner (persona hook, clock hook, user actions) ──► Episodes: ordered steps,
                captures (DOM, screenshots, email, PDF, chat, API) and a state snapshot per step
 L2 EVIDENCE    (a) claims: facts extracted, normalized, compared with oracles      [kept from first version]
                (b) messages: what each capture tells the user + feature attribution  [new]
                (c) directives: decision, action, urgency, validity, rationale given  [new]
 L3 STORY       User Experience Story = time-ordered events (messages, user actions, state changes)
                per (release, persona, scenario)                                       [new, central]
 L4 RELATIONS   code generators propose candidate relations between events ──► model interprets each
                against applicable principles & exceptions ──► labelled relations     [new]
 L5 ISSUES      issues = labelled conflicts + delta vs base release; severity, confidence and
                verification computed separately; verifier                             [reworked]
 L6 DECISION    release policy ──► Ship / Ship with notes / Needs review / Hold (a recommendation);
                owner disposition ──► memory (checks, approved expectations, scoped exceptions) [reworked]
 L7 PRESENT     Release Story view (hero) · issue evidence · story diff · repro command · PR summary
```

## What changed from the first architecture (and what was kept)

| Area | First version | Now | Why |
|---|---|---|---|
| Unit of analysis | claim per (persona, surface, fact) | **story** per (release, persona, scenario), with claims inside it | the thesis is about an experience, not a value |
| Time | none; captures were unordered | **episodes with a simulated clock**; events ordered; state per step | "wait" vs "book now" only conflict if both are live at the same time; guidance can go stale after the user acts |
| Feature | not modelled | **every message attributed to a feature** | the owner needs to know *which features* collide |
| Directives | not modelled | **decision / action / urgency / validity / rationale** | the central conflict is competing advice, which fact joins cannot see |
| Principles | prose "owner expectations" | **operational principles with conditions and scoped exceptions** | separates a real conflict from a legitimate, approved tradeoff (Maya vs Raj) |
| Checkers | six families over claims | **relation generators (code) + relation interpretation (model)**; the fact families survive as generators | first-class detection of directive and experience conflicts |
| Finding status | one verdict that mixed severity and certainty | **severity, confidence and verification status kept as three separate fields** | a harmful-if-true issue with weak evidence must not read as a confirmed critical |
| Learning | every finding becomes a deterministic check | **deterministic checks only for expressible rules**; otherwise approved semantic expectations; owner "intentional" becomes a **scoped, expiring exception** | the old version overpromised, and a blanket suppression would hide Maya's case under Raj's |
| Ordering | "ratchet checks before capture" | **capture first**, then cheap deterministic work, then model interpretation of candidates only | checks need fresh captures |
| Models | five roles across four model families (SAM, Glimmer) | **three models**: Muse Spark, Muse Spark Open, Muse Voice Transcribe | depth over breadth |
| Kept unchanged | adapters, capture format, facts, oracles, normalization, claim schema, model router, cache, cost ledger, run directory, exit codes | | they are the evidence foundation |

## L0: the Product Contract

The contract lives in the consumer's repo at `.semaudit/`. It is owner-approved, and every item records its source: a doc span, a transcript timestamp or a review click.

```yaml
# principles.yaml: three KINDS of rule, evaluated independently
# (1) universal prohibitions: no exceptions, ever
- id: U1
  kind: universal
  text: Every scarcity, price and policy claim matches our own data.
  check: {claims: [seats_left, price, fee, policy], must: match_oracle}   # code
  source: {kind: doc, file: northbound-principles-draft.md, at: "§1"}

# (2) conditional rules: forbidden by default, permitted only through a scoped exception
- id: P1
  kind: conditional
  text: >
    We may always share verified inventory information. We do not urge immediate
    action, except for genuinely time-sensitive trips.
  tier: core                                   # core | standard
  applies_to: {decision: when_to_book, directive.strength: [urge, require]}
  exceptions:
    - id: P1-E1
      conditions:                              # ALL must be met
        - {id: a, data: "state.departure_in_h <= 72"}          # code. Fixed dates alone never qualify
        - {id: b, data: "claim.seats_left == oracle.inventory"} # code
        - {id: c, judged: explains_tradeoff}                   # model judges; verifier re-judges
      scope: {features: [fare_lock], surfaces: [fare_detail, checkout]}
      approved: {by: owner, on: 2026-10-27, expires: 2027-01-31}

# (3) cross-feature coherence rules: about the RELATIONSHIP between messages
- id: P2
  kind: coherence
  text: >
    When more than one feature gives an active recommendation about the same user
    decision, the product either presents a consistent recommendation or explains
    the competing tradeoffs.
  tier: core
  applies_to: {relation: competing_directives}
  satisfied_by: [consistent_recommendation, explained_tradeoff]
  # no exceptions; an exception to a conditional rule never excuses a coherence rule

# features.yaml: who said it
- id: fare_lock
  release_introduced: "2.4"
  attribution: {dom_attr: "data-feature=fare_lock", templates: ["email/fare_lock_*"]}

# decisions.yaml: the user decisions the product guides, and which actions are incompatible
- id: when_to_book
  actions: [book_now, wait_for_drop, set_alert]
  incompatible: [[book_now, wait_for_drop]]
- id: fare_type
  actions: [choose_refundable, choose_non_refundable, upgrade_to_refundable]
  preconditions:
    choose_refundable: {booking.status: not_booked}
    upgrade_to_refundable: {booking.within_free_change_window: true}

# personas.yaml: archetypes, axes, and the STATE each persona carries into a scenario
- id: maya
  axes: {party: solo, budget: tight, date_flexibility: flexible, currency: EUR}
  state: {departure_in_days: 42}
- id: raj
  axes: {party: solo, budget: expense_account, date_flexibility: fixed}
  state: {departure_in_hours: 30}

# scenarios.yaml: time-ordered scripts, the backbone of a story
- id: S-book-flexible
  steps:
    - {at: "D0 10:00", do: search, route: LIS-BER}        # captures results incl. the Price Watch card
    - {at: "D0 10:01", do: check_inbox}                    # captures the Price Watch email
    - {at: "D0 10:03", do: open_fare, pick: cheapest}      # captures the Fare Lock banner
    - {at: "D0 10:05", do: checkout, fare: non_refundable}
    - {at: "D0 10:06", do: confirm}
    - {at: "D0 12:00", do: advance_clock_and_check_inbox}  # time-triggered email, push
    - {at: "D2 09:00", do: open_app}
    - {at: "D2 09:02", do: ask_concierge, q: "Did I get a good deal?"}
  # fixture requirement (tested): on 2.4, the Price Watch "wait" message is captured BEFORE the Fare Lock banner

# surfaces.yaml, facts.yaml (with oracles), rules.yaml (expressible checks): as before
# release_policy.yaml: how severity x confidence x verification becomes a recommendation (L6)
# dispositions/: owner decisions on past issues (L6 memory)
```

Two hooks the consumer provides: a **persona hook** that creates the persona's account and state, and a **clock hook** that advances simulated time and fires time-based jobs (emails, pushes). Without a clock hook, time-triggered surfaces are reported as *not measured*. They are never silently skipped.

## L1: Capture (episodes)

An **episode** is one run of one scenario, for one persona, on one release:
`Episode{release, persona, scenario, seed, steps[seq, sim_time, action, captures[], state_snapshot]}`.
- Captures use the format of the first version: DOM text and element boxes, screenshot, raw payload, URL, build id.
- **Locators are source-specific**, so evidence can be checked for every kind of surface, not just web pages:

  | Source | Locator |
  |---|---|
  | web page | CSS selector + bounding box + DOM text span |
  | email | message id + MIME part + character span |
  | push | notification id + field |
  | PDF | page + bounding box + text-layer span |
  | JSON / API | JSON path |
  | chat | turn index + character span |
- A **state snapshot** is read from the contract's oracles after each step: booking status, fare type, departure time, seats left, the price on record.
- Recorded journeys are replayed deterministically. An agent (Muse Spark with browser tools) **repairs** a step only when it breaks, and logs the repair.

## L2: Evidence

- **(a) Claims** — `{fact, value, unit, qualifiers, locator, extractor, confidence}`, normalized and compared with oracles **after extraction**. Each claim gets one of three statuses:
  - `supported`: the oracle agrees;
  - `contradicted`: the oracle disagrees. Only this status can raise a false-claim issue;
  - `unverifiable`: no oracle exists. Missing evidence is not evidence of falsehood, so this becomes an owner question (or a low-confidence note on an AI-generated surface), never a false claim.
- **(b) Messages** — `{message_id, capture_id, locator, exact_text, feature_id, attribution{method: dom_attr | contract_map | release_diff | model, confidence}, claims[]}`.
- **(c) Directives** — for any message that recommends something:

```json
{ "decision": "when_to_book", "action": "wait_for_drop",
  "strength": "suggest",                       // inform | suggest | urge | require
  "urgency": {"level": "low", "deadline": null, "reason_given": "prices on this route may drop"},
  "validity": {"from": "D0 10:00", "until": "unknown",
               "ends_on": [{"state": "booking.status == booked"}],
               "basis": ["action_rule"]},
  "objective": "lower price",
  "explains_tradeoff": false,
  "evidence_span": "Prices for LIS→BER may drop. We'll tell you when to book." }
```

Directives are extracted by Muse Spark Open, constrained to the contract's decision and action vocabulary. A directive outside that vocabulary is kept as `action: other` with free text, and becomes an onboarding question.

### Validity: when a directive is "live"

A directive is live from the moment it is shown until the **earliest** of these:

1. **Explicit text**: a deadline the message states ("lock it for 48 h", "until departure"). Basis: `text`.
2. **Action rules**: the contract's precondition for the action stops holding (`wait_for_drop` and `lock_fare` require `booking.status == not_booked`). Basis: `action_rule`.
3. **Feature default lifetime**: from `features.yaml` (e.g. a banner is live while it is on screen plus that session; an email for 7 days; a push for 24 h). Basis: `feature_default`.
4. **Superseded**: the same feature later issues a different directive on the same decision. Basis: `superseded`.

If none of these gives an end, `until` is **`unknown`**, never "forever". Two directives **overlap** when the later one is shown while the earlier one is live, and both preconditions hold at that moment. An overlap that depends on an `unknown` end is still proposed as a candidate, but it is marked `validity_unknown`, which lowers confidence and becomes an owner question ("how long should a Price Watch email's advice stand?").

This is a small, explicit rule set, not a general temporal reasoner. The fixtures test it: in Maya's story, the "wait" directive (10:00) is live at 10:03 because she has not booked and the email's default lifetime has not passed.

## L3: The User Experience Story

`Story{release, persona, scenario, events[], state_timeline[]}`, where each event is:

```json
{ "event_id": "e7", "event_key": "price_watch/price_watch_email/pw.wait_v2/when_to_book#1",
  "seq": 7, "sim_time": "D0 12:00",
  "kind": "message",                           // message | user_action | state_change
  "surface": "price_watch_email", "feature": "price_watch",
  "message_id": "m19", "directive": {...},
  "state_at_event": {"booking.status": "booked", "fare_type": "non_refundable", "departure_in_days": 42} }
```

The story is the single object that the relation layer, the issue evidence, the delta and the UI all read: one source of truth.

**Stable event identity.** `event_key` = feature / surface / message key / decision / occurrence index within the scenario. The message key comes from the app (`data-message-key`, email or push template id) where it exists. Otherwise it is a normalized text-template signature, and alignment is then marked *fuzzy*.

## L4: Relations

**Generators (code)** propose candidate relations within one story:

| Generator | Proposes a candidate when |
|---|---|
| `competing_directives` | two directives from **different features** share a decision, their actions are in the contract's `incompatible` set, and they overlap (validity rules above). Coherence rules (P2) apply to these |
| `stale_guidance` | a directive's precondition is false in `state_at_event` (e.g. "choose refundable" after booking a non-refundable fare, outside the free-change window) |
| `rule_applies` | an event matches a universal or conditional rule's `applies_to`. For conditional rules, its exceptions are evaluated (below) |
| `attention_load` | more than *N* directive or marketing messages within window *W* (contract-set) |
| `fact_divergence` | the claim layer finds the same fact with different values (first-version logic) |
| `false_claim` | a claim is `contradicted` by its oracle (e.g. "only 2 seats left" vs an inventory of 9). `unverifiable` claims go to owner questions instead |
| `model_open` | the model reads the whole story and proposes a relation none of the above produced. Kept, but starts at lower confidence, and its vocabulary gaps become onboarding questions |

**Interpretation (model).** Each candidate relation, with its events, evidence spans, applicable principles and exceptions, and the persona and state, goes to Muse Spark with a structured-output schema:

| Label | Meaning | Becomes an issue? |
|---|---|---|
| `conflict` | the user receives incompatible guidance, or a principle is broken, and no exception applies | yes |
| `unexplained_tradeoff` | both messages are individually legitimate, but the product never reconciles them for the user | yes, at lower severity, with a "explain the tradeoff" suggestion |
| `explained_tradeoff` | both signals are present *and* the product helps the user weigh them | no (negative control) |
| `exception_applies` | a scoped exception's conditions are all met | no; shown as "allowed by P1-E1" with each condition's result |
| `compatible` / `duplicate_ok` | no conflict (e.g. a confirmation page and a confirmation email) | no |

**Rule kinds are evaluated independently, in this order:**
1. **Universal rules** (U1, U2): code checks, with no exceptions. A failure stands no matter what else holds.
2. **Conditional rules** (P1, P3): the rule applies, then its exceptions are evaluated. Data conditions (`departure_in_h <= 72`, `seats_left == inventory`) are evaluated by **code** against state and oracles, giving *met*, *not_met* or *unknown*. Soft conditions (`explains_tradeoff`) are judged by the model and re-judged by the verifier. An exception applies only if **every** condition is *met*, and only inside its scope. An *unknown* condition lowers confidence; it never grants the exception.
3. **Coherence rules** (P2): evaluated on `competing_directives` relations. Satisfied only by a consistent recommendation or an explained tradeoff.

**An exception to one rule never excuses another rule.** Kai (imminent trip, verified, explained urgency) is allowed under P1-E1, *and* still raised under P2 if Price Watch tells him to wait. Omar (imminent trip, false seat count) fails U1 *and* fails P1-E1 condition (b). Every story shows each rule's evaluation, including the ones that passed, so "why is Raj fine?" is answered on screen: P1 applies and P1-E1 is met; P2 has no competing directive.

## L5: Issues

```json
{ "issue_id": "I-2.4-maya-01", "kind": "competing_directives",
  "release": "2.4", "base": "2.3", "delta": "new",          // new | changed | pre_existing | resolved
  "personas": ["maya"], "scenarios": ["S-book-flexible"],
  "events": ["e2", "e4"], "features": ["price_watch", "fare_lock"],
  "rules": [{"id": "P2", "kind": "coherence", "status": "violated",
             "why": "wait_for_drop (live since D0 10:00) and lock_fare (D0 10:03) on when_to_book; no reconciliation shown"},
            {"id": "P1", "kind": "conditional", "status": "not_applicable", "why": "lock_fare strength = suggest"},
            {"id": "U1", "kind": "universal", "status": "passed", "why": "seats_left 2 == inventory 2; forecast matches oracle"}],
  "severity":     {"level": "major", "factors": {"decision_impact": "money", "principle_tier": "core",
                   "reach": "2/8 personas, core booking journey", "timing": "pre-purchase", "recoverable": true}},
  "confidence":   {"level": "high", "basis": ["directives extracted by 2 models agree",
                   "label agreed by independent model", "defense failed", "no unknown conditions"]},
  "verification": {"status": "verified", "steps": {"reproduced": "pass", "evidence_linked": "pass",
                   "cross_model": "pass", "defended": "pass"}},
  "repro": "semaudit repro I-2.4-maya-03",
  "disposition": "open" }
```

**Three fields, never combined:**
- **Severity**: how bad it is *if real*. Factors: decision impact (money, time, irreversible), principle tier, reach (personas × journeys), timing (before or after the user commits), recoverability. Levels: critical, major, minor.
- **Confidence**: how likely it is to be real by the owner's standards. Basis: evidence type (a measured fact is stronger than an interpreted directive), agreement between the two extraction models, agreement on the label, the defense outcome, and any *unknown* exception conditions. Levels: high, medium, low.
- **Verification status**: which checks have actually been run, and their outcomes. Steps: `reproduced` (the episode is re-run and the same events appear), `evidence_linked` (every cited event resolves through its source-specific locator to the exact quoted text), `cross_model` (an independent model reaches the same label), `defended` (the defense pass could not explain it away), and `oracle_checked` (fact kinds only). Statuses: `unverified`, `partially_verified`, `verified`, `failed` (`not_reproducible` or `disputed`).

**What "verified" means, and does not mean.** Verified means the evidence was reproduced and resolves exactly, and the judgment was independently re-reached by a second model that also failed to explain it away. It does **not** mean a subjective product judgment is objectively true. That is the owner's call, and it is what the owner disposition records. Objective kinds (false claim, fact divergence) are additionally `oracle_checked`.

**Release notes** are used to attribute changes to features and to aim personas at what changed. A change being *intended* never by itself excuses a conflict; only an approved, scoped exception does.

**Delta.** The same scenario runs on the base release, and events are aligned by `event_key`. Events with no partner are explicitly **unmatched**: `added` in head or `removed` from base, never force-paired. Fuzzy alignments, which fall back to template signature and order, are marked as such and lower the delta's confidence. Each issue is classified *new*, *changed*, *pre_existing* or *resolved*, and the story diff shows events added, removed and changed.

## L6: Decision and memory

**Recommendation.** It is computed from `release_policy.yaml` and is never an LLM opinion. Default policy:

| Recommendation | Rule |
|---|---|
| **Hold** | an open issue is `severity = critical` **and** `confidence ≥ medium` **and** `verification = verified` |
| **Needs owner review** | an open critical issue is not verified, or has low confidence; or the open majors reach the policy threshold |
| **Ship with notes** | only verified majors or minors are open |
| **Ship** | nothing open |

The owner's actual decision is recorded beside the recommendation, never overwriting it.

**Owner dispositions become memory, and nothing is suppressed broadly:**

| Disposition | What is stored | Next release |
|---|---|---|
| **fix** | issue reference + expected resolution | the issue must come back `resolved`, or it is re-raised as `still_open` |
| **accept as scoped exception** | a new or narrowed exception: conditions, scope (features, surfaces, personas), expiry, approver | applies only when *all* its conditions are met. A similar event outside the scope or conditions is raised, with the reason (e.g. Fare Lock's urgent variant in the hotel flow: "nearest exception P1-E1 does not apply: scope"; Hana: "condition (a) not met: departs in 4,320 h") |
| **not an issue** | reason + the exact relation signature (events, features, principle) | that exact signature is not re-raised; a variant is |
| **expressible rule** | a deterministic check in `.semaudit/checks/` (fact equality, presence or absence under a condition, a precondition rule) | runs first after capture, with no model calls; it reports `could_not_measure` when a locator breaks |
| **approved semantic expectation** | a natural-language expectation, approved and scoped ("Price Watch never messages a traveller after they book") | evaluated by the relation layer every release; not claimed to be deterministic |

## Model roles and data policy

| Role | Model | Notes |
|---|---|---|
| `extractor` (messages, directives, claims) | **Muse Spark Open** (`meta-models/muse-spark-open-1026` on Modal/Baseten) | high volume, structured output |
| `interpreter` (label relations; `model_open` pass) | **Muse Spark** (Meta Model API; latest official ID, to be verified) | the core judgement |
| `cross_checker` (verification: re-extract and re-label) | the *other* model of the two | agreement across two different models is the point |
| `defender` (explain-it-away pass) | Muse Spark Open | independent of the interpreter |
| `explorer` (journey repair, onboarding mapping) | Muse Spark with browser tools | |
| `transcriber` (owner voice note) | **Muse Voice Transcribe** | |

**Data policy per target** (`semaudit.toml`): each target declares `data: synthetic | real`. Real or customer data may only be routed to Standard-mode endpoints. Contributor-mode endpoints, which may use prompts for training, are allowed only for fictional targets such as Northbound. Finablo runs use synthetic profiles only.

## Pipeline order (L1 → L7)

1. Materialize personas → run scenarios on base and head → captures + state (**capture first**).
2. Deterministic, model-free: run the existing locator-based checks in `.semaudit/checks/`; evaluate the data conditions that depend only on state.
3. Extraction (model): messages, directives, claims. Cached by content hash, so unchanged captures cost nothing. Then, in code, compare the newly extracted claims with oracles (`supported` / `contradicted` / `unverifiable`) and evaluate the data conditions that depend on claims.
4. Build stories; align base and head.
5. Generators → candidates (code). Interpretation of the candidates only (model), plus one `model_open` pass per story.
6. Issues → verifier → severity, confidence and verification computed independently.
7. Release policy → recommendation. Report, Release Story view, repro bundle.
8. Owner dispositions → memory.

## Kept from the first version

`semaudit.adapters`, `semaudit.models` (router, cache, ledger), `semaudit.contract` (extended), the facts/oracles/claims parts of `semaudit.extract` and `semaudit.graph`, `semaudit.report`, the run directory layout, and the exit codes (`0` ship, `1` issues need a decision, `2` could not measure).

New packages: `semaudit.story` (episodes, events, stories, alignment), `semaudit.relate` (generators, interpretation, exceptions), `semaudit.decide` (severity, confidence, verification, policy, dispositions). `semaudit.check` becomes the home of the deterministic checks only; `semaudit.ratchet` merges into `semaudit.decide`.

## Tech stack

Python 3.12 · Playwright · Pydantic v2 · Typer · httpx · Jinja2 · pdfplumber · pytest. Release Story UI: one static HTML page with vanilla JS, generated per run so it can be hosted anywhere. Northbound: FastAPI + Jinja + fpdf2.
