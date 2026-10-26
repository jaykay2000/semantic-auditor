# Northbound: demo app under audit

A small, fictional travel-booking app built to be audited. It is deliberately multi-surface, so one traveller's facts (price, dates, cancellation policy, baggage) appear in many places, as they do in real products.

**Fictional.** Northbound is not a real company. Its name, data and branding are invented for this demo.

## Surfaces

| Surface | Kind | Notes |
|---|---|---|
| Search results | web page | fare cards with price and fare class |
| Fare detail | web page | baggage, change and cancellation rules |
| Checkout | web page | itemized total, fees, currency |
| Confirmation page | web page | booking reference, total, cancellation deadline |
| Confirmation email | email | written to `outbox/` (file sink), HTML |
| Itinerary PDF | PDF | downloadable, generated with fpdf2 |
| Concierge | chat | answers trip questions. Deterministic templates by default; an optional LLM-backed path for realism |
| Booking API | JSON | `GET /api/bookings/{id}`: the source of truth (oracle) |

Test-data hook: `POST /api/test/personas` creates a traveller with given axes (fare, party, currency, loyalty) and returns a booking id.

## Builds

| Build | Purpose |
|---|---|
| `v1` | Baseline. Correct, apart from any deliberately pre-existing issues listed in ground truth |
| `v2` | The release under audit: seeded issues, intended changes (documented in `RELEASE_NOTES.md`) and decoys |
| `v3` | Fixes for v2's issues; used to show the ratchet |

Build selection: `NORTHBOUND_BUILD=v1|v2|v3`, read in one place (`config.py`).

## ⚠️ Blind seeding

The v2 issue list and its ground truth are written by a **separate session** and stored in `bench/ground_truth/northbound-v2.yaml`. Agents building the auditor's checkers must not read that file or the v2 diff before Phase 4 scoring. This README only names the *categories* the benchmark must cover:

- each of the six finding families (contradiction, oracle mismatch, unsupported, persona misfit, unexplained semantic change, unknown claim);
- at least one **partial rollout** of an intended change;
- **decoys**: differences that are correct (formatting within policy, legitimately persona-specific values), which a good auditor must *not* flag;
- issues that appear only for some personas.
