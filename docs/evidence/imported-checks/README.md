# Imported checks: an agent's finding becomes a replayable release check (vertical slice, 2026-10-31)

**Status:** built end to end and measured on the held-out agent findings. The import works safely but converts only
6 of 57 held-out findings fully (11%); the converted checks replay and re-judge consistently.
**One handpicked success (the free-shipping email) is an engineering demonstration, not proof of broad conversion
reliability.**

## What was built

| Piece | Where | What it does |
|---|---|---|
| Check record | `src/semaudit/imported/record.py` | actions (persona + adapter-verb steps), invariant (owner rule + surface + statement), source (the agent's finding verbatim; its quote is evidence of the original finding only and is never shown to the judge) |
| Converter | `src/semaudit/imported/convert.py`, `prompts/convert.md` | one model call drafts clauses / steps / persona / invariant from the finding's own reproduce text; a deterministic gate refuses what it cannot verify; one redraft with the gate's errors; fail-closed classification |
| Re-check | `src/semaudit/imported/recheck.py`, `prompts/judge.md` | replay through SRA's capture runner (`Runner`), then 3 independent small judgments of the invariant over the cited surface's captured messages and the store's own order record; four separate statuses |
| Owner approval | `contract/approve.py::approve_check` | outside measurement runs, a check replays only when approved at its current content digest (same `approvals.yaml`) |
| Memory | `decide/memory.py` (`decide_check`, `check_status`, `record_check_outcome`) | fix_confirmed / still_open / regressed / not_reproduced / not_confirmed, stored in `dispositions.yaml` beside issue decisions |
| Spree harness | `spree-semaudit/contract-imported/` (`imports.yaml`, `catalog.json`), `imported_checks.py`, `imported_checks_aggregate.py` | the store's import vocabulary (15 verbs, words that must describe each verb, prerequisites, the 38-product catalog, defaults, R1-R11 -> U1..L1) and the driver |

**Tests:** `tests/test_imported_checks.py` (34). `scripts/mutate_imported_checks.py` removes each of 26 safeguards in
turn: 26 tests go red, 0 survive (checked at `b6d672b` and again at `f8ee336`). Full suite: 404 passed.

## Method and the no-tuning rule

1. `holdout.json` (`2379f13`) fixed the split before any converter code: 61 agent findings (trials C1, C2, X1, X2,
   M2, M3); dev = C1#00, C1#15, C1#16; C1#17 excluded (same reproduce text as a dev item); **57 held out**.
2. Developed only on the dev findings (that is where the "signed in" fabrication below was found and blocked).
   Frozen at `b6d672b` (harness `b6a3ad3`), run once on the 57. No converter change after seeing them.
3. One post-freeze change, a crash fix (`f8ee336`): a judgment whose reply is not JSON after retries (the model ran
   to its token cap) is recorded as a `not_measurable` vote instead of aborting the run. It cannot create a pass or
   a fail.
4. Demo picks were written down (`DEMO-PICKS.md`, `bd06123`) before their conversion results were seen.
5. Replays ran with `--measure` (unapproved checks allowed, every result stamped `approved: false`); the owner has
   approved nothing.

## Measures (held-out set only)

### 1. Conversion outcome (57 findings) — from `heldout-conversions.txt`

| Outcome | Count | What it means |
|---|---|---|
| converted -> replayed | **6** | every action mapped; replayed end to end on all three releases |
| partially_converted | 15 | named clauses it could not map, a missing prerequisite step, or an "observation" that reads like an action |
| adapter_gap | 5 | names a verb the adapter lacks: `wait`, `select_store_pickup` (real gaps); `proceed_to_checkout` x2, `complete_order` (over-cautious: existing verbs do these) |
| not_converted | 31 | the draft still failed the gate after one redraft (mostly: address or product data given no source clause, or a required field missing) |

- 52 of 57 drafts were refused at least once and redrafted. **No converted check contains an invented action or a
  silently dropped instruction** (checked by the gate on every check, and by hand for the 6 converted).
- The gate errs toward refusal: 31 not_converted is mostly data-provenance strictness, not unsupported actions.
- The preregistered "unsupported" demo, C2#11, came out **not_converted, not adapter_gap**. My expectation was wrong:
  its reproduce text is only "order one physical product plus The Spree Commerce Handbook, pay by Check." (the
  "fulfilled" email comes from the store, not from a tester action), and the gate refused it because no address was
  given. No replay was fabricated. The sign-in case does come out `adapter_gap`, but only on a dev finding
  (`demo/C1-16-dev-signin.yaml`: needs `sign_in` and a surface the harness does not reach).
- F01 (the free-shipping email): 7 held-out agent findings. C1#04 converted; C2#00, X2#04, M2#01, M2#02, M3#01 came out
  partially_converted (mostly the action-word check firing on "placed both orders" / "add Subtotal+..." in
  observations); X1#03 not_converted (the draft claimed `enter_address` and `apply_promo_code` were missing).

### 2. Manual corrections needed (the 6 converted)

**1 of 6.** M3-02 (Store Pickup shown briefly before Standard is charged): the importer inserted a declared
prerequisite "choose delivery" before Place Order, but the finding is exactly that the shopper does not choose. The
check therefore passes everywhere and memory says `not_reproduced` (correct signal that the check is not faithful).
The other 5 match the agent's text. No correction was applied before measuring.

### 3. Replay consistency (6 checks x 3 releases x 3 fresh replays = 54) — from `heldout-replays.json`

| | Count |
|---|---|
| replays that ran end to end on the first try | 45 / 54 |
| after one fresh retry (one store at a time) | 54 / 54 |
| check x release where all 3 runs gave the same assertion outcome | **17 / 18** |

The 9 first-try failures were page loads timing out while two or three stores captured at once; in one of them
the store also refused the FREESHIP code, which the replay status caught (`step_note_fails`). Without that
safeguard that run would have been judged on an order with no code. The one inconsistent triple is F01 on `next`,
run 3: 2 of its 3 judgments were runaway replies, so the outcome was `not_measurable`.

### 4. Assertion outcomes (majority of 3 judgments; same in all 3 runs unless noted)

| Check | Agent's finding (graded family) | current (beta2) | candidate (beta3) | next (beta3 + storefront 8ba5eee) | Matches the grading? |
|---|---|---|---|---|---|
| C1-04 | free-shipping email does not add up (F01, fixed) | **fail** | **pass** | pass, pass, not_measurable | yes |
| C1-01 | cart "Total" without tax/delivery note (F17, both) | fail | fail | fail | yes |
| C2-02 | same, other agent (F17, both) | fail | fail | fail | yes |
| X2-00 | tax-inclusive item line (F02, both) | fail | fail | fail | yes |
| M3-00 | same, other agent (F02, both) | fail | fail | fail | yes |
| M3-02 | Store Pickup shown, Standard charged (P05, both) | pass | pass | pass | no: the check is not faithful (see 2) |

The F02 result on `next` agrees with the upstream issue already filed (spree/storefront#283).

### 5. Semantic confidence and evidence (the separate statuses)

- **Semantic confidence** (54 judged replays): 3/3 judgments agreed in 47, 2/3 in 7.
- **Evidence, quotes:** in all 155 readable judgments, every quoted text was found verbatim in the captured message on
  the check's surface (bare labels such as "Subtotal" are counted as uninformative, not false).
- **Evidence, record values:** 102 of 155 judgments wrote every record value correctly; 53 wrote a malformed value
  (stray JSON fragments, a `\x7f` character) in the model's structured output. No genuine misreading of a figure
  was found. 7 of 162 judgments were runaway replies (no output).
- **Memory, current -> candidate:** C1-01, C2-02, X2-00, M3-00 `still_open` x3; M3-02 `not_reproduced` x3; **C1-04
  `fix_confirmed` in 1 run, `not_confirmed` in 2**, because the rule requires every majority judgment's evidence to
  be fully verified and 2 runs had a malformed record value. **candidate -> next:** the four still_open; C1-04
  `not_reproduced` (already fixed) x2, `not_confirmed` x1. 36 outcomes recorded in
  `spree-semaudit/contract-imported/dispositions.yaml`; no owner decision exists on any check.

### 6. Model cost (Baseten, Muse Spark Open; from `import-root/runs/ledger.jsonl`)

| | Spend |
|---|---|
| held-out conversion (57 findings, 113 calls) | $3.03, i.e. **$0.053 per conversion** |
| re-check, clean calls | **$0.035 per replay** (3 judgments, ~5K tokens each) |
| re-check, all-in (runaways, re-judging after the crash fix) | $4.72 / 54 = $0.087 per replay |
| dev (conversion + re-check) | $0.86 |
| **total** | **$8.61** |

A release re-check of these 6 checks costs about $0.21 at the clean rate ($0.52 all-in), plus about 1.5 min of capture per
check (6 checks took about 8-9 min per release run). No Meta API spend.

## What it means

- The **re-check side works**: deterministic replays (once captures do not compete for the machine), stable
  judgments, quotes always traceable, and the known fix shows as fail -> pass while four standing defects stay open on
  a new storefront release.
- The **import side is safe but narrow**: it never fabricated a replay on the held-out set, but it fully converts
  about 1 in 10 agent findings, and its two heuristics (action words in observations; prerequisite insertion) both
  mislead in measured cases.
- The **evidence rule is stricter than the model's output hygiene**: malformed record values block 2 of 3 fix
  confirmations even though every quote and every arithmetic step was right.

## Not done / limits

- "Next release" is the **storefront only**: beta3 backend with the upstream storefront at `8ba5eee` (installed
  2026-10-30; upstream main is now `7531a4f`). No newer Spree backend was available in the harness, so backend-rendered
  surfaces (the emails) did not change between candidate and next.
- No owner approval was given or simulated; all replays are measurement runs.
- The converter was run once; conversion variance across reruns was not measured.
- `adapter_gap` names were checked by reading only for the 5 held-out cases above.
