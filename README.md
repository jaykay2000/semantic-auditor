# Semantic Release Auditor

Semantic Release Auditor turns validated discoveries, from developers and AI agents, into reusable release checks.
Each one keeps the user's journey, the rule that was broken, and the evidence, so the next release doesn't start
from zero.

The Python package is `semaudit`; the short name is SRA. It was built during the Meta Global AI Developer Hackathon
(Oct 26 – Nov 4, 2026). The reusable checks are a **prototype**: tested on one open-source store, with the limits
listed [below](#limits).

## The loop

```
 discovery: a developer, a user or an AI agent reports a problem, in their own words
     │
     ▼
 Muse Spark Open drafts the user's JOURNEY (a persona and the steps the app's driver can perform)
 and the RULE it broke (one of the owner's rules, the page or email it applies to, a statement with no figures)
     │
     ▼
 a deterministic GATE checks every step against the report's own text and refuses what it cannot verify
     │
     ▼
 the owner APPROVES the check, pinned to its exact content
     │
     ▼
 REPLAY on a release: every page and email captured, beside the app's own records (for a store, the order record)
     │
     ▼
 three separate readings of the rule ──► fixed · still open · came back · did not reproduce · not confirmed
     │
     ▼
 SAVED: the next run loads the approved check from storage and runs it again
```

Two terms, used throughout:

- A **journey** is what one user does: who they are (a persona) and the steps, written in the app's own action words
  (its adapter's verbs, such as `add_to_cart` or `place_order`).
- A **rule** is one of the owner's written rules about what the user should experience, for example "the email's
  breakdown must add up to the order total, each part counted once, checked against the store's order record".

## Reusable checks (prototype)

Code: [`src/semaudit/imported/`](src/semaudit/imported/). Measured results:
[docs/evidence/imported-checks/README.md](docs/evidence/imported-checks/README.md).

### What a saved check holds

A check is one YAML file, `checks/<id>.yaml`, in the app's contract folder
([`record.py`](src/semaudit/imported/record.py)):

- **actions**: the persona and the journey's steps;
- **invariant**: the owner's rule, the surface it applies to (a page or an email), and a statement of what must hold;
- **source**: the original finding, word for word. Its quote is kept as evidence of what was reported. It is never
  shown to the model that judges the replay.

The owner approves the actions and the invariant. The source is kept but is not part of what is approved.

### How a finding becomes a check

[`convert.py`](src/semaudit/imported/convert.py): one model call drafts the journey and the rule from the finding's
own "how to reproduce" text. A deterministic gate then checks:

- **coverage**: the draft's pieces are verbatim parts of the reproduce text and cover all of it, so no instruction is
  dropped silently;
- **verbs**: every step uses a verb the app's driver has and the contract describes;
- **actions**: every action in the text is carried out by a step, or named as unmapped;
- **persona**: only fields the contract defines, with values that come from the text or a declared default;
- **invariant**: a real contract rule, on a surface a step reaches, with none of the report's figures in it.

A draft that fails is redrafted once with the gate's errors. The result is one of `converted`,
`partially_converted`, `adapter_gap` (needs a step the app's driver can't perform) or `not_converted`. Only a
`converted` check can be approved. Conversion has no CLI command yet; an app's harness calls
`semaudit.imported.convert.convert(...)`.

### Commands

| Command | What it does |
|---|---|
| `semaudit checks approve --contract DIR --check ID --by NAME` | Approves one converted check at its current content. It writes `check:<id>` with the content digest (a short hash of the actions and the invariant), who approved, and the date into the contract's `approvals.yaml`. |
| `semaudit checks run --contract DIR --base REL --head REL --run-id ID --max-usd N` | Loads the approved checks **from storage only** (`approvals.yaml`, `checks/<id>.yaml`, `dispositions.yaml`) and imports nothing. A check whose content changed since approval is refused and listed. Each approved check is replayed fresh on both releases, judged, and its outcome is added to the memory. Writes `runs/<id>/saved-checks.json` with the hash of every file it loaded. |
| `semaudit checks card --contract DIR --out FILE [--saved saved-checks.json] [--check ID]` | Renders the check cards page: the original finding, the journey and rule, the four statuses, and the older release beside the newer one. |

Saved checks run with `semaudit checks run`. They are not yet part of `semaudit review` or shown on the release
review page.

### Four separate statuses per release

[`recheck.py`](src/semaudit/imported/recheck.py) records four statuses and never merges them:

| Status | Values | What it says |
|---|---|---|
| Replay | succeeded · failed | Every step ran, nothing was left unmeasured, the app did not refuse a step the finding needs, and the rule's page or email was captured with at least one message. No model is involved. |
| Rule result | pass · fail · not_measurable | The majority of 3 independent readings. Each reading sees the rule, the captured messages on that surface and the app's own record, never the original quote. |
| Readings that agree | 3/3 · 2/3 · lower | How many of the 3 readings agree with the majority. The replay can be repeatable while the reading varies; this says how much. |
| Evidence | verified · partially_verified · unverified | Every quote in the majority readings is checked against the captured text, and every record value they cite against the record itself. |

**A PASS needs both a satisfied rule and verified evidence.** A majority pass whose evidence is less than
`verified` becomes `not_measurable`, and the card says why. A replay that failed is never judged.

### Memory: what happened between two releases

[`decide/memory.py`](src/semaudit/decide/memory.py) compares the older release (base) with the newer one (head):

| Status | Meaning |
|---|---|
| `fix_confirmed` | fails on the base, passes on the head with verified evidence |
| `still_open` | fails on both releases |
| `regressed` | passes on the base, fails on the head ("came back") |
| `not_reproduced` | passes on both: the reported condition did not reproduce on the base |
| `not_confirmed` | something was not measured: a replay failed, no majority, or a head pass without verified evidence |

Outcomes are appended to the contract's `dispositions.yaml`, beside the owner's decisions on release issues.

### Owner approval is pinned to content

Outside measurement runs, a check replays only if `approvals.yaml` holds the digest of its **current** actions and
invariant. Edit a step or the rule and the old approval no longer applies: `checks run` refuses the check until it is
approved again ([`contract/approve.py`](src/semaudit/contract/approve.py), [`saved.py`](src/semaudit/imported/saved.py)).

### What was measured

All from [docs/evidence/imported-checks/README.md](docs/evidence/imported-checks/README.md):

- **Held-out set:** 57 agent findings from Spree experiments, set aside before any converter code was written
  ([`holdout.json`](docs/evidence/imported-checks/holdout.json)). The converter was frozen, then run once.
- **Conversion:** 6 of 57 converted fully (11%); 15 partially; 5 needed a step the store's driver can't perform;
  31 not converted ([`heldout-conversions.txt`](docs/evidence/imported-checks/heldout-conversions.txt)). No
  converted check contains an invented action.
- **Replay:** 6 checks × 3 releases × 3 fresh replays. The rule result was the same in all 3 replays for 17 of 18
  check-and-release pairs ([`heldout-replays.json`](docs/evidence/imported-checks/heldout-replays.json)).
- **The demo check (C1-04, an agent's free-shipping email finding).** Picked before its result was seen
  ([`DEMO-PICKS.md`](docs/evidence/imported-checks/DEMO-PICKS.md)). It FAILs on Spree 6.0.0.beta2, where the email's
  lines add up to $179.38 but it shows $194.38. It PASSes on beta3, where shipping shows $15.00 and the lines add up.
- **The video run is Run 3c**, started from storage with nothing imported
  ([`run3c-transcript.txt`](docs/evidence/imported-checks/acceptance/run3c-transcript.txt),
  [`cards-run3c.html`](docs/evidence/imported-checks/acceptance/cards-run3c.html)). C1-04: beta2 FAIL 3/3 with
  verified evidence, beta3 PASS 3/3 with verified evidence, memory `fix_confirmed`. A variant with a different basket
  (three blenders) gives the same FAIL then PASS, also `fix_confirmed`.
- **A second app, refused.** Finablo's 401(k) limit bug was tried as a check. The developers' written record names
  what the user saw but no step they took, so the frozen converter graded it `partially_converted` and SRA refused
  to approve it. That is the gate working. The bug stays one of SRA's own release-review journeys
  ([docs/evidence/imported-checks/finablo/README.md](docs/evidence/imported-checks/finablo/README.md)).
- **Earlier runs, kept as they came out.** Run 2 did not pass: the newer release was `not_measurable` because 2 of 3
  readings ran to the reply-length cap. In Run 3, one reading wrongly passed the broken email and was outvoted 2 to 1;
  that is why agreement is its own status.
- **Cost** (Muse Spark Open on Baseten): about $0.05 per conversion; $0.035 to $0.087 per replay on the held-out set,
  before the two judging fixes. With them, Run 3c cost $0.54 all-in for 2 checks on 2 releases, about $0.14 per check
  per release, because garbled replies are asked again.
  Run 3c cost $0.54 for 12 readings, because garbled record values forced re-asks.

### Limits

- **Prototype.** Saved checks have run on one store (Spree) only, with one driver and one converter version.
- **Narrow import.** 6 of 57 held-out findings converted (11%). In the six finding groups reported only by the
  agents, 0 of 24 findings converted.
- **Two judging fixes were made after results were seen**, and both are disclosed in the evidence README:
  a reply cap with fresh retries for runaway replies (the judge role is capped at 6,000 tokens, up to 4 tries), and
  a re-ask, up to 3 times, when a reading writes a garbled record value. A clean number that is wrong is never
  re-asked. Neither touches the frozen converter, the gate or the rule. One rule was made stricter at the same time:
  a PASS now needs verified evidence.
- **Approval in the recorded runs.** The approvals of C1-04 and its blender variant, used in every acceptance run,
  were written by the build session under the owner's plan. The harness's `approvals.yaml` labels them "owner has
  not reviewed this digest".
- **The "next" release changes only the storefront.** No newer Spree backend was available, so the emails did not
  change between beta3 and the next release.
- The converter was run once; how much conversion varies between runs was not measured.

### Reproduce the Spree demo

The Spree harness lives in its own repository, [spree-semaudit](<SPREE_HARNESS_URL>): the store's contract, its
driver, the import vocabulary (`contract-imported/`) and `imported_checks.py`. That is where the demo's Spree beat is
reproduced. Run 3c was:

```bash
python3 imported_checks.py run-saved --base current --head candidate --run ic-accept-run3c --max-usd 0.6
```

`current` is Spree 6.0.0.beta2 and `candidate` is beta3. It needs a Baseten key for Muse Spark Open.

## Release review

The reusable checks sit on top of SRA's release review, which came first. A release review takes the owner's
written rules (the **product contract**), runs each persona's journeys on two releases, and reports what changed
for the user.

Users don't experience features; they experience a release. Each feature can pass its own tests and say only true
things, and together they can still hand one traveller two different plans in the same few minutes: *wait for a
price drop* (a correct forecast) and *lock this fare, 2 seats left* (a correct seat count). The owner's rule says
that when two features advise on the same decision, the product must explain the tradeoff. SRA flags the traveller
who gets no explanation, and clears the one whose app explains it.

```
 owner's rules + docs ──► PRODUCT CONTRACT: rules with scoped exceptions, features, decisions,
                          personas + state, scenarios, facts + oracles (the app's own records)
                                         │
 base release ─┐                         ▼
 head release ─┴─► scenario runner (simulated time) ──► captures + state per step
                                         │
                   deterministic checks ─┤ (no model)
                                         ▼
                   messages · directives · claims  (extractor role)
                                         ▼
                   USER EXPERIENCE STORY per persona: time-ordered events, base ↔ head aligned
                                         ▼
                   code proposes candidate conflicts ──► the interpreter role judges them against the
                   rules and exceptions: conflict / tradeoff / exception applies / compatible
                                         ▼
                   issues: severity · confidence · verification (separate) ──► verifier
                                         ▼
                   release review page · repro · Ship / Hold recommendation ──► owner decision ──► memory
```

Which model plays each role is under [Models](#models-measured).

### What it looks for

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

These examples come from Northbound, a fictional travel app written for this project
([examples/northbound](examples/northbound/README.md)). Its rules are written by the owner, not imported.

### Capture

`semaudit capture` runs each persona's scenarios against one release of the app and writes **episodes**: the ordered steps, everything the product showed or sent, and the oracle state after each step. It costs no model budget.

```bash
pip install -e '.[demo,dev]' && playwright install chromium
semaudit capture --contract examples/northbound/contract --release 2.4 [--persona maya --persona omar] [--run-id ID] [--runs-dir runs]
```

The runner starts the release from the contract's `app.launch` on a free port and stops it afterwards. For each step it sets the simulated clock (which runs due jobs, so emails and pushes sent between steps exist), lets the app's adapter (`app.adapter`, here `examples/northbound/adapter.py`) perform the verb in Chromium (1280x900), captures the page it landed on (DOM, screenshot, marked elements), captures every new email, push, chat transcript and PDF, and snapshots every oracle. Output: `runs/<run-id>/episodes/<release>/<persona>__<scenario>.json` plus artifacts under `runs/<run-id>/captures/`. Exit `0` when every step ran; exit `2` if a release would not boot or a step failed or a surface could not be measured (the episodes are still written). Format: `src/semaudit/story/episode.py`. Adding an app means writing its adapter; the runner is generic.

### Review a release

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
release review page says why. In `review --reader` mode (used for the Spree and Finablo reviews in the demo) the
model reads every rule and every captured story and names the issues, and SRA checks each citation against the
captures ([docs/03-architecture.md](docs/03-architecture.md)).

**Adding an app** needs no core change: a contract (rules, decisions, features, surfaces, facts and oracles,
`subject.yaml` for who the user is and what describes their situation, personas, scenarios, release policy) and an
adapter for its scenario verbs. `tests/test_core_is_generic.py` keeps app vocabulary out of `src/semaudit/` and
runs a non-travel contract through the rules.

## Models (measured)

Every model call goes through `semaudit.models.complete(role=…)`; the role names a job, and the model for each role
is set in the app's `semaudit.toml` (defaults in [`router.py`](src/semaudit/models/router.py)). This table is what
the runs actually used.

| Role | Job | Northbound (fictional travel app) | Finablo (real finance app) | Spree (real open-source store) |
|---|---|---|---|---|
| `extractor` | reads messages, directives and claims out of each capture | Muse Spark 1.3 (Meta API) | not called (reader-mode review) | Muse Spark Open (Baseten) |
| `interpreter` | judges candidate conflicts against the rules; in reader mode, reads every rule and story | Muse Spark 1.3 | Muse Spark 1.3 (Meta API) | Muse Spark Open |
| `cross_checker_extract`, `cross_checker_interpret` | second pass over extraction and interpretation | Muse Spark 1.2 | not called | Muse Spark Open (extract only; interpret had 0 calls) |
| `defender` | argues against every issue occurrence | Muse Spark 1.2 | not called | Muse Spark Open |
| `importer` | drafts a check's journey and rule from a finding | — | Muse Spark Open (1 call; the draft was refused) | Muse Spark Open |
| `check_judge` | the 3 readings of a saved check's rule | — | — | Muse Spark Open |

Model IDs: `muse-spark-1.3` and `muse-spark-1.2` on the Meta Model API; `meta-models/muse-spark-open-1026` on Baseten.

**How this was measured** (2026-10-31): the `models` and `model_settings` fields in each review's manifest
(Northbound `runs/e2e-2/review-2.3-2.4.json`; Finablo `review-10ff1e3-a183626.reader.json`; Spree
`spree-scale-2t/review-v6.0.0.beta2-v6.0.0.beta3.reader.json`), the role and model on every row of each run ledger
(this repo's `runs/ledger.jsonl`, the Spree harness's `review-root` and `import-root` ledgers, and the Finablo
harness's `import-root` ledger), and the
`models` recorded on every saved-check result (for example
[`run3c-saved-checks.json`](docs/evidence/imported-checks/acceptance/run3c-saved-checks.json)). Run folders and
ledgers are not committed.

**Not independent.** Each app uses one model family for every role (on Spree, one model), so a second pass is not
independent agreement.
The verifier records "reduced independence" and caps confidence at medium.

**Not built:** Muse Voice Transcribe (turning the owner's spoken intent into draft rules), and onboarding, which would draft a
contract from the owner's docs (`src/semaudit/onboard/` and `explore/` are empty). The router can also call a non-Meta provider, added for a
control experiment; no result in this README or the demo comes from it.

## Documents

- [Vision](docs/01-vision.md)
- [Problem](docs/02-problem.md)
- [Architecture](docs/03-architecture.md)
- [Onboarding](docs/04-onboarding.md) (design; not built)
- [Release review workflow](docs/05-audit-workflow.md)
- [Implementation plan](docs/07-implementation-plan.md)
- [Evaluation](docs/08-evaluation.md)
- [Reusable checks: what was built and measured](docs/evidence/imported-checks/README.md)
- [Decisions](docs/decisions.md)
- [Archive](docs/archive/README.md): superseded demo drafts

Also: [Hackathon compliance and provenance](HACKATHON.md) · [Northbound demo app](examples/northbound/README.md) · [Benchmark](bench/README.md) · [Finablo integration](integrations/finablo/README.md) · [Spree tax line, reported upstream](demo/evidence/taxline-upstream-2026-10-30/README.md)

## Layout

```
src/semaudit/  adapters · capture · contract · story · extract · relate (rules and conflict candidates)
               · verify · decide (issues, memory, reader) · report (review page, tickets) · imported (reusable checks)
               · models (role router) · bench
               (check · explore · graph · onboard are empty placeholders)
examples/      Northbound: a fictional multi-feature travel app (2.3 / 2.4 / 2.4.1)
bench/         frozen-fixture protocol, baselines, results
integrations/  how a consumer app adopts the auditor (first: Finablo)
demo/          video assets and upstream evidence
docs/          design documents and measured evidence
```

## Status

Built during the Meta Global AI Developer Hackathon (Oct 26 – Nov 4, 2026). Licensed under Apache-2.0 ([LICENSE](LICENSE)).
