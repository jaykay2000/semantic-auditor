# Northbound: the demo app under audit

A small, fictional travel-booking app built to be audited. **Northbound is not a real company**; its name, data and branding are invented.

It exists to make one capability visible: **several features, each telling the user something true, that together leave one traveller with guidance the owner would not sign.**

## Releases (one naming scheme, used everywhere)

| Release | Role | Contents |
|---|---|---|
| **2.3** | base | Core booking; Price Watch (opt-in alerts, before booking only); Concierge 1.0 (answers questions); confirmation page, email and PDF |
| **2.4** | **narrative fixture**: the demo release | Three changes, each green on its own tests: **Fare Lock** (inventory notice + €9 lock offer; an urgent variant for imminent trips); **Price Watch auto-enroll** (every searcher gets a drop forecast; alerts keep running after booking); **Concierge 2.0** (proactive tips) |
| **2.4.1** | memory fixture | Fixes for the issues the owner marked *fix*; also **extends Fare Lock to the hotel flow**, which is outside the scope of the approved exception |
| **bench-01 … bench-NN** | **benchmark fixture** | Sealed releases built from 2.3 by a separate session ([docs/08-evaluation.md](../../docs/08-evaluation.md)). Never used for the narrative, and never read by the session building the auditor |

Selection: `NORTHBOUND_RELEASE=2.3|2.4|2.4.1|bench-NN`, read in one place (`config.py`).

## Surfaces and hooks

| Surface | Kind |
|---|---|
| Search results (with the Price Watch card), fare detail (with the Fare Lock banner), checkout, confirmation | web pages |
| Confirmation email, Price Watch email, Fare Lock reminder | email (file sink `outbox/`) |
| Push notifications | file sink `outbox/push/` |
| Itinerary | PDF |
| Concierge | chat (deterministic templates; the optional LLM path is off for benchmarks) |
| Booking, inventory, price-forecast APIs | JSON: the **oracles** |

Every rendered message carries `data-feature=<id>` and `data-message-key=<stable key>`; email and push templates carry the same two headers. This is the attribution and event-identity path that a consumer's design system would provide.

**Hooks:**
- `POST /api/test/personas` creates a traveller with axes and state.
- `POST /api/test/clock {advance: "2h"}` advances simulated time and runs due jobs.

## Owner rules: draft, written (the voice note comes later)

The rules come in three kinds, because they fail in different ways:

| ID | Kind | Rule | Exceptions |
|---|---|---|---|
| **U1** | universal prohibition | Every scarcity, price and policy claim matches our own data. | none, ever |
| **U2** | universal prohibition | The price you see is the price you pay: every fee is shown before the traveller commits, identically on every surface. | none, ever |
| **P1** | conditional (urgency) | We may always share verified inventory information. We do not *urge* immediate action, except for genuinely time-sensitive trips. | **P1-E1**: all of (a) departure within 72 h (fixed dates alone do **not** qualify); (b) the scarcity claim matches inventory; (c) the message explains the tradeoff. Scope: Fare Lock, on fare detail and checkout. |
| **P2** | cross-feature coherence | When more than one feature gives an active recommendation about the same user decision, the product either presents a consistent recommendation or explains the competing tradeoffs. | none. P1-E1 permits urgency; it does **not** excuse incoherence |
| **P3** | conditional (post-purchase) | After purchase we help travellers get the most from their booking. We do not second-guess a completed choice unless they can still act on it. | — |
| **P4** | load | Beyond messages about the booking itself, we contact a traveller at most twice in 24 hours. | — |

**P2 is the release-level rule.** No single feature can break it on its own.

## Narrative fixture: what 2.4 is designed to contain

This list is public because the demo is built on it. 2.4 results are therefore never presented as benchmark numbers.

### Hero: every individual message is true

**Maya**: solo, flexible dates, tight budget, departs in 42 days. Scenario `S-book-flexible`:

| Time | Event | Feature | True? |
|---|---|---|---|
| D0 10:00 | searches LIS→BER | — | |
| D0 10:00 | search-results card: *"Prices on your dates are likely to drop over the next two weeks. We'll tell you when to book."* (directive: `wait_for_drop`) | Price Watch | ✓ matches the forecast oracle |
| D0 10:01 | Price Watch email, same message | Price Watch | ✓ |
| D0 10:03 | fare-detail banner: *"Only 2 seats left at this fare. Lock it for 48 h for €9."* (directive: `lock_fare`, strength *suggest*) | Fare Lock | ✓ inventory = 2 |
| D0 10:06 | books a non-refundable fare | — | |
| D0 12:00 | Price Watch email: *"We'll tell you when to book."* | Price Watch | stale (she has booked) |
| D2 09:02 | asks the concierge *"Did I get a good deal?"* → *"You should have booked a refundable fare."* | Concierge 2.0 | second-guesses a choice she can no longer change |

**Expected issues:**
- **P2 coherence conflict (the hero).** `wait_for_drop` (live from 10:00 until she books) and `lock_fare` (10:03) address the same decision, `when_to_book`. Both are correct, and the product never reconciles them. It is *new in 2.4*: the features involved are Price Watch auto-enroll and Fare Lock.
- **Stale guidance** at D0 12:00.
- **P3 breach** at D2 09:02.
- **P4 load**, if her messages exceed the limit.

Fare Lock's message to Maya is information plus a suggestion, not urgency, so **P1 is not breached for Maya.** Her problem is the relationship between the two features, not either message alone.

### Secondary: the factual layer (conventional defects, shown as such)

| Case | Expected |
|---|---|
| Every persona: the lock fee is €9 on the banner and €12 at checkout | **U2** fact divergence |
| **Omar**: departs in 20 h; the urgent banner says *"2 seats left"*; inventory = 9 | **U1** false claim, *and* P1-E1 condition (b) fails, so P1 is breached. The exception never excuses a false claim |

### Rule-boundary cases (each must come out exactly as stated)

| Case | Expected result | Why |
|---|---|---|
| **Maya**: flexible, conflicting advice, no explanation | raise **P2** | above |
| **Raj**: departs in 30 h; urgent banner with verified scarcity and an explained tradeoff; Price Watch forecasts *no drop before departure* | **allowed**: P1 applies and **P1-E1** is satisfied (a ✓ b ✓ c ✓); **P2 not applicable**, because no competing recommendation is live | the urgency rule applies and is explicitly excepted; the story shows both evaluations |
| **Kai**: departs in 30 h; same urgent banner, verified and explained; Price Watch *does* say "likely to drop, wait" | **allowed under P1-E1, but P2 raised** | an exception for urgency does not excuse the incoherence |
| **Hana**: fixed dates, departs in 6 months; urgent banner | **P1 breach** | fixed dates are not time-sensitivity, so P1-E1 condition (a) fails |
| **Omar** | **U1** (and P1 not excused) | above |

### Negative controls (must **not** be raised)

| ID | Case | Valid because |
|---|---|---|
| NC1 | **Raj** | the boundary table above |
| NC2 | **Lena** (flexible) asks the concierge *"book now or wait?"* and gets both the drop forecast and the seat count | `explained_tradeoff`: it helps her weigh them against her flexibility, which satisfies P2 |
| NC3 | Confirmation page, email and PDF all repeat "booked" | `duplicate_ok` (transactional) |
| NC4 | A family of four's total differs from a solo traveller's | different trips: persona-specific facts |
| NC5 | **Theo**, 3 h after booking: the concierge offers a switch to refundable *"for €30 until tomorrow 10:05"* | still actionable, with a deadline: P3 is satisfied |
| NC6 | Maya on **2.3**: a Price Watch alert before booking | compatible: no competing directive is live |

## Memory fixture: what 2.4.1 tests

- Issues marked *fix* come back `resolved`.
- An exception the owner accepts during the 2.4 review is honoured inside its scope only.
- Fare Lock's urgent variant on the **hotel** flow is outside P1-E1's scope (Fare Lock on fare detail and checkout only). It is raised with *"nearest exception does not apply: scope"*.
