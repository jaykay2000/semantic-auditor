# Northbound: the demo app under audit

A small, fictional travel-booking app built to be audited. **Northbound is not a real company**; its name, data and branding are invented.

It exists to make one capability visible: several features that each pass their own QA, and together give one traveller a story the owner would not sign.

## Releases (one naming scheme, used everywhere)

| Release | Role | Contents |
|---|---|---|
| **2.3** | base | Core booking; Price Watch (opt-in alerts, before booking only); Concierge 1.0 (answers questions); confirmation page, email, PDF |
| **2.4** | **narrative fixture**: the demo release | three changes, each green on its own tests: **Fare Lock** (scarcity banner + €9 lock fee); **Price Watch auto-enroll** (every searcher, keeps running after booking); **Concierge 2.0** (proactive money-saving tips) |
| **2.4.1** | memory fixture | fixes for the issues the owner marked *fix*; also **extends Fare Lock to the hotel flow**, which is outside the scope of the approved exception |
| **bench-01 … bench-NN** | **benchmark fixture** | sealed releases built from 2.3 by a separate session (see [docs/08-evaluation.md](../../docs/08-evaluation.md)). Not used for the narrative and never read by the session building the auditor |

Selection: `NORTHBOUND_RELEASE=2.3|2.4|2.4.1|bench-NN`, read in one place (`config.py`).

## Surfaces

| Surface | Kind |
|---|---|
| Search results, fare detail, checkout, confirmation | web pages |
| Confirmation email, Price Watch email, Fare Lock reminder | email (file sink `outbox/`) |
| Push notifications | file sink `outbox/push/` |
| Itinerary | PDF |
| Concierge | chat (deterministic templates; an optional LLM path is off for benchmarks) |
| Booking API, inventory API, price API | JSON: the **oracles** |

Every rendered message carries `data-feature=<id>` (and email/push templates carry a feature header). This is the attribution path; it is what a consumer's design system would provide, and the contract maps it.

**Hooks:**
- `POST /api/test/personas` creates a traveller with axes and state.
- `POST /api/test/clock {advance: "2h"}` advances simulated time and runs due jobs (emails, pushes).

## Owner principles (the contract the demo uses)

| ID | Principle (operational) | Exceptions |
|---|---|---|
| **P1** | We do not manufacture scarcity or use urgency to pressure flexible travellers. For genuinely time-sensitive trips, we may communicate verified inventory constraints and explain the tradeoff. | **P1-E1**: trip is time-sensitive (departs within 72 h, or dates fixed) **and** the seats-left claim matches inventory **and** the tradeoff is explained. Scope: Fare Lock on fare detail and checkout. |
| **P2** | The price you see is the price you pay: every fee is shown before the traveller commits, and it is the same everywhere. | — |
| **P3** | After purchase, we help travellers make the most of their booking. We do not second-guess a completed choice unless they can still act on it. | — |
| **P4** | Beyond messages about the booking itself, we contact a traveller at most twice in 24 hours. | — |

## Narrative fixture: what 2.4 is designed to contain

This list is public because the demo is built around it. The demo therefore never presents 2.4 results as benchmark numbers.

**Seeded issues:**
- **Maya** (flexible dates, tight budget, departs in 42 days):
  - Price Watch says *wait for a drop*, while Fare Lock says *only 2 seats left, lock now*. This is the competing-directives issue, and it breaks P1.
  - The "2 seats" claim does not match inventory, which shows 9. This is an unsupported assertion.
  - After she books, a Price Watch email arrives: *"we'll tell you when to book"*. This guidance is stale.
  - On day 2, the concierge says *"you should have booked refundable"* when she can no longer switch. This guidance is stale and breaks P3.
- **Maya** gets four non-booking messages in 24 hours, which breaks P4.
- **Every persona:** the Fare Lock fee is €9 on the banner and €12 at checkout. This is a fact divergence and breaks P2.

**Negative controls**, which must *not* be raised:

| ID | Persona | Looks suspicious because | Valid because |
|---|---|---|---|
| NC1 | **Raj** (fixed dates, departs in 30 h) | the same Fare Lock urgency banner | P1-E1 applies: time-sensitive ✓, 2 seats matches inventory ✓, tradeoff explained ✓ |
| NC2 | Lena asks the concierge "book now or wait?" | it mentions both a likely drop and limited seats | `explained_tradeoff`: it helps her weigh them against her flexibility |
| NC3 | any | confirmation page, email and PDF all repeat "booked" | `duplicate_ok`: transactional confirmations |
| NC4 | family of four vs solo | different totals | different trips: a different fact per persona, not a divergence |
| NC5 | Theo, 3 h after booking | the concierge raises switching to refundable | actionable: within the free-change window, with a deadline and a price |
| NC6 | Maya on **2.3** | a Price Watch alert before booking | compatible: no competing directive is live |

## Memory fixture: what 2.4.1 tests

- Issues marked *fix* must come back `resolved`.
- A scoped exception the owner accepts during the 2.4 review must be honoured, inside its scope only.
- Fare Lock on the **hotel** flow for a flexible traveller sits outside P1-E1's scope. It must be raised, with the note "nearest exception does not apply".
