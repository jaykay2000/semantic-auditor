# Northbound: the demo app under audit

A small, fictional travel-booking app built to be audited. **Northbound is not a real company**; its name, data and branding are invented.

It exists to make one capability visible: **several features, each telling the user something true, that together leave one traveller with guidance the owner would not sign.**

This file is the **single source** for Northbound's rules, copy, personas and expected results. Other documents refer to it, and do not restate it.

## Releases (one naming scheme, used everywhere)

| Release | Role | Contents |
|---|---|---|
| **2.3** | base | Core booking; Price Watch (opt-in alerts, before booking only); Concierge 1.0 (answers questions); confirmation page, email, PDF |
| **2.4** | **narrative fixture**: the demo release | Three changes, each green on its own tests: **Fare Lock** (inventory notice + lock offer; an urgent variant for imminent trips); **Price Watch auto-enroll** (every searcher gets a drop forecast; its email and push alerts keep running after booking); **Concierge 2.0** (proactive tips) |
| **2.4.1** | memory fixture | Fixes for the issues the owner marked *fix*; also **extends Fare Lock to hotels**, outside the scope of the approved exception |
| **bench-01 … bench-03** | **benchmark fixture** | Sealed releases built from 2.3 by a separate session ([docs/08-evaluation.md](../../docs/08-evaluation.md)). Never used for the narrative, and never read by the session building the auditor |

Selection: `NORTHBOUND_RELEASE=2.3|2.4|2.4.1|bench-NN`, read in one place (`config.py`).

## Surfaces, oracles and hooks

| Surface | Kind |
|---|---|
| Search results (Price Watch card), fare detail (Fare Lock banner), checkout, confirmation | web pages |
| Confirmation email, Price Watch email | email (file sink `outbox/`) |
| Price Watch push | file sink `outbox/push/` |
| Itinerary | PDF |
| Concierge | chat (deterministic templates; the optional LLM path is off for benchmarks) |

**Oracles (JSON):**
- `booking`: status, fare type, `departure_at`, the fees charged, and the change window;
- `inventory`: seats left at the fare;
- `forecast`: the drop forecast and its window.

Every rendered message carries `data-feature=<id>` and `data-message-key=<stable key>`; email and push templates carry the same two headers.

**Hooks:**
- `POST /api/test/personas` creates a traveller with axes and a trip.
- `POST /api/test/clock {advance: "2h"}` advances simulated time and runs due jobs.

**State is derived, not stored on the persona.** A persona has a trip with `departure_at`. Time conditions compare **exact timestamps** (`trip.departure_at` − `message.shown_at`, at full clock precision). Nothing is rounded or truncated, so a departure 72 h 00 min 30 s away does **not** qualify as within 72 h.

## Running Northbound

```bash
cd examples/northbound
pip install -e '../..[demo]'          # fastapi, uvicorn, fpdf2 (plus the repo's own dependencies)
./run.sh                              # = python3 -m uvicorn northbound.app:app --port 8080 (PORT=... to change)
python3 -m pytest examples/northbound/tests    # from the repo root
```

| Env var | Default | Meaning |
|---|---|---|
| `NORTHBOUND_RELEASE` | `2.3` | release to run (read only in `northbound/config.py`) |
| `NORTHBOUND_OUTBOX` | `examples/northbound/outbox/` (gitignored) | email and push file sinks |
| `NORTHBOUND_TEST_HOOKS` | `1` | `1` mounts `/api/test/*` |

**Pages** (plain HTML, no JS needed): `/search?origin=&destination=&date=` · `/fare/<fare_id>` · `/checkout/<fare_id>` (POST books) · `/booking/<id>` · `/booking/<id>/itinerary.pdf` · `/concierge` (chat; `POST /api/concierge {"text"}` for JSON). Fare ids are `LIS-BER-NR` (non-refundable, EUR 129 per traveller) and `LIS-BER-RF` (refundable, EUR 189), plus EUR 24 taxes and fees per traveller; switching to refundable within 24 h of booking costs EUR 30 (`POST /booking/<id>/upgrade`). The departure time is always the traveller's `trip.departure_at`; the search `date` is only echoed.

**Identity:** cookie `nb_traveller=<id>`, or header `X-Traveller: <id>`, or query `?traveller=<id>` (header wins).

**Hooks** (`/api/test/*`, simulated time only; nothing reads the wall clock):
- `POST /api/test/personas {id, name, travellers: 1|2|4, flexible, trip: {origin, destination, departure_at}}` (ISO time with a zone)
- `POST /api/test/clock {"advance": "30s"|"2h"|"1d2h"}` or `{"set": "<iso>"}`: runs every due job in due-time order; returns `{now, jobs_run}`. `GET` returns the time and pending jobs. The clock starts at D0 = `2026-11-02T10:00:00+00:00`.
- `POST /api/test/world {"seats": {"LIS-BER-NR": 2}, "forecast": {"LIS-BER": {"drop": true, "window_days": 14}}}`
- `POST /api/test/reset`: wipes travellers, bookings, jobs, message log, the outbox files and the clock.
- `GET /api/test/messages?traveller=`: the server-side log of every message shown or sent (debug only, not an oracle).

**Oracles** (read-only JSON, always mounted): `GET /api/oracle/booking?traveller=` (`status` `not_booked|booked`, `fare_type`, `departure_at`, `charges[]` in EUR cents with `what`, `transaction`, `quote_id`, `within_change_window`, `change_window_ends`) · `GET /api/oracle/inventory?fare=` (`seats_left`) · `GET /api/oracle/forecast?route=LIS-BER` (`drop`, `window_days`). The change window is 24 h from booking, inclusive, computed from the simulated clock.

**Markers.** Every message on a page is rendered by ONE Jinja macro (`templates/macros.html`) and carries `data-feature`, `data-message-key` and `data-shown-at` (simulated ISO time). Emails and push notifications are JSON files, one per message, in `outbox/email/<message_id>.json` and `outbox/push/<message_id>.json`: `{message_id, to, subject, sent_at, headers: {"X-Feature", "X-Message-Key"}, text, html}`. The itinerary PDF lists its message keys in the PDF keywords and keeps its text extractable. Message ids (`m000001`, ...) are shared by the log and the sinks.

**2.3 copy keys** (`northbound/copy.py` is the table; the canonical `pw.*` and `cg.*` texts above are used verbatim):

| Feature | Keys |
|---|---|
| core | `core.results`, `core.results.fare`, `core.fare.summary`, `core.fare.policy.{non_refundable,refundable}`, `core.checkout.{fare,taxes,total,already,soldout}`, `core.confirmed`, `core.confirmed.{charge,total,fare_window,fare_closed,fare_refundable}`, `core.email.confirmation`, `core.pdf.{itinerary,charge,total}` |
| price_watch | `pw.card.optin` (the 2.3 opt-in offer, a card on search results), `pw.card.watching`, `pw.email.forecast` (text = the `pw.card` copy), `pw.email.forecast.nodrop` (text = the `pw.card.nodrop` copy), plus `pw.card` and `pw.card.nodrop` as the canonical wording |
| concierge | `cg.greeting`, `cg.answer.{status.none,status.booked,refund,deal.none,deal.booked,when,price_watch,fallback}` |

2.3 has no Fare Lock and no `fl.*` keys, and Concierge 1.0 never produces `cg.regret`, `cg.reconcile` or `cg.upgrade`.

### Adding a release

A release is a module in `northbound/releases/` (file name: `2.4` -> `r2_4.py`, `2.4.1` -> `r2_4_1.py`, `bench-01` -> `bench_01.py`) that defines `RELEASE = Release(...)`: the ordered list of enabled feature modules, per-feature settings and copy overrides (or new keys). `load_release("2.3").derive("2.4", add=[...], remove=[...], settings={...}, copy={...})` builds one from another. Core never checks the release name.

A feature is `northbound/features/<id>.py` (or any importable dotted path, listed in `features`) exposing `class Feature(BaseFeature)` with `id` (matches `contract/features.yaml`), `DEFAULTS`, `COPY` (extra keys) and these optional hooks, documented in `northbound/features/__init__.py`:

- `messages_for(surface, ctx) -> [Message]`: what to show on `search_results | fare_detail | checkout | confirmation | chat`
- `on_action(action, ctx, data) -> dict | None`: reacts to `search`, `open_fare`, `opt_in`, `book`, `upgrade`; may schedule or cancel jobs and send email/push; `{"error": ...}` refuses
- `on_job(job, ctx)`: runs a due job with the clock at its due time
- `concierge_reply(question, ctx) -> Message | None`

`ctx` offers `now`, `traveller`, `booking`, `message(...)`, `send_email(...)`, `send_push(...)`, `schedule(feature, kind, delay=)`, `cancel_jobs(feature)` and `state_for(feature_id)`. Price Watch 1.0 implements only `mode: opt_in`; 2.4 extends or replaces that module for auto-enrol.

## Owner rules: written draft (the voice note comes later)

| ID | Kind | Rule | Evaluated by |
|---|---|---|---|
| **U1** | universal | Every scarcity, availability and policy claim matches our own data. | code: claim vs `inventory` / policy oracle |
| **U2** | universal | For the same traveller, the same transaction and an unchanged price quote, every displayed fee matches the amount ultimately charged. | code: displayed fee vs `booking.charges` for that transaction |
| **U3** | universal | Every recommendation we show is one the traveller can still act on. | code: the action's precondition at the time it is shown |
| **U4** | universal | After purchase, we never second-guess a completed choice. Offering an action the traveller can still take is not second-guessing. | model classifies the message as *retrospective* or not; the verifier re-checks |
| **P1** | conditional | We may always share true inventory information. We do not **urge** immediate booking, except for genuinely time-sensitive trips. | applies to directives on `when_to_book` (flights *and* hotels) with strength `urge` or `require` |
| **P1-E1** | exception to P1 | Permitted when **all** hold: (a) `trip.departure_at − message.shown_at ≤ 72 h`, compared exactly (fixed dates alone never qualify); (b) the inventory claim (seats or rooms left) matches the inventory oracle; (c) the message **explains its own tradeoff** (book now vs keep flexibility). Scope: Fare Lock, *flight* fare detail and checkout. Expires 2027-01-31. | (a), (b) code; (c) model + verifier |
| **P2** | coherence | When more than one feature gives an active recommendation about the same decision, the product must **reconcile incompatible actions**, or **explain the material tradeoffs between otherwise compatible actions**, while both are live and before the traveller decides. | generator (pair type from the vocabulary) + model (`reconciles`) |
| **P3** | load | Beyond messages about the booking itself, we send a traveller at most **2 outbound contacts** (email or push) in any 24 hours. In-app cards and user-initiated conversations (the concierge answering a question) are not contacts. | code: count |

**Two different "explanations", kept separate:**
- `explains_own_tradeoff` is about the message itself (P1-E1 (c)).
- `reconciles: [directive ids]` means the message addresses another feature's advice (P2).

Explaining your own tradeoff never reconciles a conflict with someone else's advice.

### Decision vocabulary (contract)

| Decision | Actions | Incompatible pairs | Rationale |
|---|---|---|---|
| `when_to_book` | `book_now`, `lock_fare`, `wait_for_drop`, `set_alert`, `conditional` | **incompatible:** `book_now` ⟂ `wait_for_drop` (act now vs wait). **Material tradeoff (compatible):** `lock_fare` + `wait_for_drop`. A traveller *could* pay €9 to hold the fare while watching for a drop, but the lock costs money and expires after 48 h, while the forecast drop window is 14 days. Doing both is coherent only if someone explains that | — |
| `fare_type` | `choose_refundable`, `choose_non_refundable`, `upgrade_to_refundable` | — | — |

`conditional` means a message that lays out alternatives by the traveller's situation ("if you can move your dates…; if not…"). It never forms a competing pair. It is the typical *reconciling* message.

Preconditions:
- `book_now`, `lock_fare`, `wait_for_drop` and `set_alert` require `booking.status == not_booked`.
- `choose_*` requires `not_booked`.
- `upgrade_to_refundable` requires `booking.within_change_window` (24 h from booking; fee €30).

### Strength rubric: suggestion vs urging (operational, so P1 does not hinge on taste)

A directive is **`urge`** if **any** of these cues is present in the same message:

| Cue | Examples |
|---|---|
| U-a: an **immediacy** word attached to the action | "now", "today", "right away", "before it's gone", "don't miss" |
| U-b: a **countdown** or a stated deadline of **≤ 24 h** attached to the primary action | "offer ends in 3 h", a countdown timer |
| U-c: **scarcity coupled to an imperative** in the same sentence | "Only 2 seats left, book now" |

Otherwise, the directive is classified as follows:

| Strength | Test |
|---|---|
| `require` | the traveller cannot continue without acting |
| `suggest` | an optional or conditional offer of an action, with none of the cues above: "Lock it for 48 h for €9 total", "You can still switch…" |
| `inform` | states a fact and recommends no action: "2 seats left at this fare" on its own |

The model extracts strength **and the cue it relied on** (U-a, U-b or U-c, or none). A code lexicon checks for the same cues independently. If the two disagree, confidence drops and the disagreement is recorded. Every canonical copy key below carries its expected strength.

## Canonical copy (2.4); every document quotes from here

| Key | Feature | Copy |
|---|---|---|
| `pw.card` | Price Watch | "Prices on your dates are likely to drop over the next two weeks. We suggest waiting; we'll tell you when to book." |
| `pw.email.forecast` | Price Watch | the same message, by email |
| `pw.email.after` | Price Watch | "Keep waiting to book. We'll tell you when prices drop." → `wait_for_drop`, **suggest**. Sent after booking (the bug), so its precondition `not_booked` is false |
| `pw.push.moving` | Price Watch | "Prices on LIS→BER are moving." |
| `pw.card.nodrop` | Price Watch | "Our forecast: prices on this trip are unlikely to drop before departure." |
| `fl.banner` | Fare Lock | "2 seats left at this fare. Lock it for 48 h for €9 total, for your whole booking." → `lock_fare`, **suggest** (no cue). The fee claim is €9 per booking |
| `fl.banner.urgent` | Fare Lock | "Departing soon: only 2 seats left at this fare. Book now, or lock it for 12 h for €9 total if your plans might change." → primary `book_now`, **urge** (cue U-a/U-c); secondary `lock_fare`; explains its own tradeoff |
| `fl.banner.urgent_bare` | Fare Lock | "Only 2 seats left. Book now." → `book_now`, **urge** (U-c), no explanation |
| `fl.checkout.lock` | Fare Lock | lock checkout: "Fare Lock (48 h): €18" for a couple. The bug: it charges €9 **per traveller**, while the banner promised €9 **total, for the whole booking** |
| `fl.hotel.urgent` | Fare Lock (2.4.1) | hotel page: "Checking in soon: only 1 room left at this rate. Book now, or hold it for 12 h for €9 total if your plans might change." → `book_now`, **urge**, explains its own tradeoff |
| `cg.regret` | Concierge 2.0 | "You should have booked a refundable fare." → retrospective |
| `cg.reconcile` | Concierge 2.0 | "Prices on your dates are likely to drop, but this fare has 2 seats left. If you can move your dates, wait for the alert; if not, locking protects this price." → reconciles `pw.card` + `fl.banner` |
| `cg.upgrade` | Concierge 2.0 | "You can still switch to a refundable fare for €30 until tomorrow 10:05." → suggest `upgrade_to_refundable` |

## Personas and expected results

Each persona's **expected status vector** is committed as `tests/fixtures/stories/<persona>.expected.json`. It lists every rule × event (or event pair), with its status (`violated` / `passed` / `excepted` / `not_applicable`), and every exception condition (`met` / `not_met` / `unknown`). W1b and W8 compare exact sets. The table below summarizes them.

| Persona | Trip and scenario | Expected |
|---|---|---|
| **Maya** (hero) | solo, flexible, departs in 42 days. 10:00 search (`pw.card`), 10:01 `pw.email.forecast`, 10:03 fare (`fl.banner`), 10:06 books non-refundable **without** buying a lock, 12:00 `pw.email.after`, 18:00 `pw.push.moving`, D2 09:02 asks "Did I get a good deal?" → `cg.regret` | **P2 violated, labelled `unexplained_tradeoff`**: `wait_for_drop` (live since 10:00) and `lock_fare` (10:03) come from different features and are compatible actions with a material tradeoff, and nothing explains it. **U3 violated** at 12:00. **U4 violated** at D2. **P3 violated**: exactly 3 outbound contacts in 24 h (emails at 10:01 and 12:00, push at 18:00; the concierge conversation does not count). P1 not applicable (suggest, no cue). U1 passed. U2 not applicable (no lock purchased) |
| **Maya-R** (negative) | as Maya, but 2.4's fare page shows `cg.reconcile` inline below the banner | P2 **passed** (reconciled while both live). The others as for Maya |
| **Lena** (negative, NC2) | flexible, 42 days. Sees **both** features' recommendations, Price Watch (`pw.card`, `wait_for_drop`) and Fare Lock (`fl.banner`, `lock_fare`); then asks "Book now or wait?" and the concierge answers `cg.reconcile`, which `reconciles` both, while both are live and before she decides; she leaves without booking | P2 candidate generated, then **passed** (`explained_tradeoff`). Appears in the *not raised* list |
| **Raj** (negative, NC1) | solo, departs in 30 h. Search (`pw.card.nodrop`), fare (`fl.banner.urgent`) | P1 applies, **P1-E1 met** (a ✓ b ✓ c ✓) → **excepted**. P2 **not applicable** (no competing directive). Nothing raised |
| **Raj-X** (positive) | as Raj, with `fl.banner.urgent_bare` | **P1 violated**: P1-E1 (c) `not_met` |
| **Raj@72h** (boundary) | as Raj, but departure is **exactly 72 h 00 min 00 s** after the banner is shown | P1-E1 (a) **met** (≤ 72 h): excepted |
| **Raj@72h+30s** (boundary) | departure 72 h 00 min **30 s** after the banner | P1-E1 (a) **not_met**: **P1 violated**. Guards against rounding or truncation |
| **Raj@72h+1m** (boundary) | departure 72 h **01 min** after the banner | P1-E1 (a) **not_met**: **P1 violated** |
| **Kai** (boundary) | departs in 30 h. Search (`pw.card`, the forecast says drop), fare (`fl.banner.urgent`) | P1 **excepted** (P1-E1 met). **P2 violated, labelled `conflict`**: `book_now` ⟂ `wait_for_drop` are incompatible, and `explains_own_tradeoff` ≠ `reconciles` |
| **Hana** (boundary) | fixed dates, departs in 6 months. Search (`pw.card.nodrop`), fare (`fl.banner.urgent`) | **P1 violated**: P1-E1 (a) `not_met` (≈ 4,380 h) |
| **Omar** (boundary) | departs in 20 h; inventory shows 9. Search (`pw.card.nodrop`), fare (`fl.banner.urgent`, which says 2) | **U1 violated**; P1-E1 (b) `not_met` → **P1 violated** |
| **Sam & Alex** (factual) | a couple, flexible. Search (`pw.card`), fare (`fl.banner`: €9 *total, for your whole booking*), **buy the lock**: `fl.checkout.lock` charges €18; the quote is unchanged | **U2 violated**: same travellers, same transaction (the lock purchase), unchanged quote, €9 shown vs €18 charged. **P2 violated** (`unexplained_tradeoff`), as for Maya |
| **Theo** (negative, NC5) | opens the fare from a direct link (no search, so no Price Watch enrolment), sees `fl.banner`, books non-refundable at 10:06; at 13:00 the concierge proactively sends `cg.upgrade` in-app (chat, not an outbound contact) | U3 passed (within the change window); U4 not applicable (not retrospective) |
| NC3 | any booked persona | confirmation page, email and PDF repeat "booked": `duplicate_ok` |
| NC4 | family of four vs solo | different totals: persona-specific facts |
| **NC6** | Maya on **2.3**: opts in to Price Watch at search (2.3 opt-in step), gets the forecast alert, books | no competing directive (Fare Lock does not exist in 2.3); nothing raised |

## Memory fixture: what 2.4.1 tests

- Issues marked *fix* come back `resolved`.
- An exception the owner accepts during the 2.4 review is honoured, inside its scope only.
- **Rina** (2.4.1) books a **hotel** checking in **30 h** later. `fl.hotel.urgent` says 1 room left, and the inventory oracle says 1 (verified); the copy explains its own tradeoff. So P1-E1's conditions (a), (b) and (c) are all **met**, and the exception fails **only on scope**: it covers Fare Lock on *flight* fare detail and checkout. P1 is raised with *"nearest exception P1-E1 does not apply: scope (hotel)"*. The expected vector records a ✓ b ✓ c ✓ and scope ✗.
