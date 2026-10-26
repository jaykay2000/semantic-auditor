# W1b: semantic core proof (2026-10-26)

**Result: ACCEPTED on the third full attempt.** All 15 hand-authored stories matched their expected status vectors exactly, on **5 of 5 fresh runs** (75/75). All three falsifiability stubs **failed**, as required.

Reproduce: `python3 scripts/w1b_run.py --runs 5`. Reports go to `runs/w1b/<timestamp>/report.json`, which is not committed. The offline code-layer test is `python3 -m pytest tests/test_w1b_offline.py`. W1 and W1b together cost **$2.87 over 381 model calls**.

## What was tested

- **Input.** 15 stories in `tests/fixtures/stories/` (authored in `build.py`, from `examples/northbound/README.md`): Maya, Maya-R, Lena, Raj, Raj-X, Raj@72h, Raj@72h+30s, Raj@72h+1m, Kai, Hana, Omar, Sam & Alex, Theo, Rina (2.4.1) and Maya on 2.3. Each story is raw copy, features, channels, exact timestamps, user actions and oracle values. No directive fields are authored.
- **Pipeline.**
  - Muse Spark 1.3 (`low` effort) extracts every message of a story in one call: message kind, decision, action, strength, urgency cue, own-tradeoff, and claims.
  - Code computes validity windows and generates P2 candidates. It evaluates U1–U4, P1 with P1-E1 (conditions (a) and (b) in code on exact timestamps, (c) from the extraction, plus scope) and P3.
  - Muse Spark 1.3 (`medium` effort) labels each P2 candidate. Code then checks that any claimed reconciling message was shown while both directives were live and before the decision.
- **Comparison.** An exact set of (rule, subject, status, label, conditions), including the *passed* entries. Candidate order is shuffled per run.
- **Controls.** An always-conflict interpreter, an always-compatible interpreter, and an extractor that calls every directive `suggest`. Each must fail. They failed on 4, 5 and 9 stories respectively.
- **Offline layer.** With gold extractions and gold P2 labels, the code reproduces every vector (17 tests). Five deliberate code mutations each turned the suite red: the 72 h boundary `<=`→`<`, dropping the scope check, ignoring tradeoff pairs, skipping reconciler timing, and disabling the stale check.

## Sample model rationales (run 1)

- **Maya** → `unexplained_tradeoff`: "compatible (lock to hedge while waiting) but have material tradeoff of EUR 9…"
- **Kai** → `conflict`: "Per pair_type these are incompatible act-now vs wait."
- **Lena** → `explained_tradeoff`: "cg_answer at 10:04:10, while both fl_banner and pw messages were live and before leave…"

## What the attempts found (kept, because the misses were informative)

| Attempt | Result | Finding | Change |
|---|---|---|---|
| 1 run | 11/15 | The model read the Price Watch card ("likely to drop… we'll tell you when to book") as **information**, not a recommendation, so no competing directive existed. The model was right: a forecast plus a promise is not advice | **Copy** changed to "We suggest waiting; we'll tell you when to book" (fixture) |
| 1 run | — | The model labelled "Book now, or lock it… if your plans might change" as `conditional`, which would silently remove Kai's conflict | **Rubric:** a primary instruction plus a fallback takes the primary action; `conditional` only for alternatives presented as equals |
| 5 runs (#1) | aborted | Network connect timeout | Router retries timeouts, 429 and 5xx |
| 5 runs (#2) | 74/75 | Once, the €18 checkout **line item** was not extracted as a fee, so the U2 check on it went missing (the banner violation was still caught) | **Rubric:** amounts in line items and receipts are fee claims. For W6: deterministic locators on structured surfaces |
| 5 runs (#3) | 74/75 | Once, Theo's "You can still switch… for €30" offer was read as information, so the U3 actionability check on it went missing (the outcome was still correct: nothing raised) | **Rubric:** an offer of an action is a directive |
| 5 runs (#4) | **75/75** | — | — |

## Limits of this result (stated, not glossed)

- **This is the development set.** The same author wrote the stories, the expected vectors and the three rubric clarifications made in response to misses here. The clarifications are general (forecast vs recommendation, primary vs fallback, line items, offers), not story-specific, but only the **sealed benchmark** can show they generalize.
- Text only: no capture, no DOM or screenshots. W6/W8 must reproduce these vectors from real Northbound captures.
- Single model family: cross-model checks were not exercised. The defense pass and verification are not built yet (W9).
- The two misses in attempts 2 and 3 were each 1 in 75, so the rate of this class of extraction miss is low but **not zero**. W9's cross-model agreement and W6's deterministic locators are the mitigations; a single run should never be trusted for a release decision without verification.
- `state_at` still carries a generic booking vocabulary (`booking_status`, change window) in the core; W3b moves the state model into the contract.
