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

## Capture

`semaudit capture` runs each persona's scenarios against one release of the app and writes **episodes**: the ordered steps, everything the product showed or sent, and the oracle state after each step. It costs no model budget.

```bash
pip install -e '.[demo,dev]' && playwright install chromium
semaudit capture --contract examples/northbound/contract --release 2.4 [--persona maya --persona omar] [--run-id ID] [--runs-dir runs]
```

The runner starts the release from the contract's `app.launch` on a free port and stops it afterwards. For each step it sets the simulated clock (which runs due jobs, so emails and pushes sent between steps exist), lets the app's adapter (`app.adapter`, here `examples/northbound/adapter.py`) perform the verb in Chromium (1280x900), captures the page it landed on (DOM, screenshot, marked elements), captures every new email, push, chat transcript and PDF, and snapshots every oracle. Output: `runs/<run-id>/episodes/<release>/<persona>__<scenario>.json` plus artifacts under `runs/<run-id>/captures/`. Exit `0` when every step ran; exit `2` if a release would not boot or a step failed or a surface could not be measured (the episodes are still written). Format: `src/semaudit/story/episode.py`. Adding an app means writing its adapter; the runner is generic.

## Review a release

```bash
semaudit contract check examples/northbound/contract        # validate; lists items not yet owner-approved
semaudit review --contract examples/northbound/contract --base 2.3 --head 2.4 --max-usd 3
semaudit repro <issue-id> --review runs/<id>/review-2.3-2.4.json --max-usd 1   # re-capture + re-derive one finding
semaudit verify-report runs/<id>/review-2.3-2.4.json                           # offline: is the report what its inputs give?
semaudit decide <issue-id> fix --review runs/<id>/review-2.3-2.4.json --by <you>   # or not-an-issue --reason …, accept --expires …
semaudit decide-release hold --review runs/<id>/review-2.3-2.4.json --by <you>
semaudit serve --review runs/<id>/review-2.3-2.4.json --by <you>                 # the page with working decision buttons
```

`review` exits 0 only for a decided Ship: every persona measured and every contract item owner-approved at its
current content. Otherwise the recommendation is `provisional` (exit 1) or `not_measurable` (exit 2), and the
Release Story page says why.

**Adding an app** needs no core change: a contract (rules, decisions, features, surfaces, facts and oracles,
`subject.yaml` for who the user is and what describes their situation, personas, scenarios, release policy) and an
adapter for its scenario verbs. `tests/test_core_is_generic.py` keeps app vocabulary out of `src/semaudit/` and
runs a non-travel contract through the rules.

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

| Role | Model today | Planned |
|---|---|---|
| Extract messages, directives and claims; interpret candidate conflicts against owner principles | **Muse Spark 1.3** (Meta Model API) | extraction on **Muse Spark Open** (open weights) |
| Second-pass cross-check of, and argument against, every issue occurrence | **Muse Spark 1.2** | **Muse Spark Open** (still the same family) |
| Turn the owner's spoken intent into draft principles | not built | **Muse Voice Transcribe** |

Every role is called through `semaudit.models` by name, never by model ID. While all roles are one model family,
the verifier records "reduced independence" and caps confidence at medium: a second model's agreement is a second
pass, not independent agreement. Muse Spark Open is the same family too; only a model from another family lifts
the cap.

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

Built during the Meta Global AI Developer Hackathon (Oct 26 – Nov 4, 2026). Licensed under Apache-2.0 ([LICENSE](LICENSE)).
