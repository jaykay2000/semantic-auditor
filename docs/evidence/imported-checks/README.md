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
| **total (held-out work)** | **$8.61** |

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

## Acceptance runs for the demo (owner-approved plan, `docs/09-demo-script-v7.md`), 2026-10-31

Every model call in this slice, conversion and judging, used a Meta model: `meta-models/muse-spark-open-1026` (Muse
Spark Open on Baseten): 57/57 check records, every judgment, and all ledger rows. Every re-check result now records
`models: {conversion, judging}`. The approval of C1-04 and C1-04-v1 is recorded as
`acceptance-run (main session, owner plan 2026-10-31; owner has not reviewed this digest)`: the owner has not looked at
these digests.

| Run | Pass condition | Outcome as it came out | Evidence |
|---|---|---|---|
| 1. Convert the raw F01 finding (C1#04, frozen converter `b6d672b`, held-out run) | journey reaches the confirmation email; invariant is the "adds up and matches the order record" rule, not the figures | **pass**: last step `read_order_email`; invariant U3 on `order_email_text`: "the itemised summary shown in the order confirmation email is arithmetically consistent with its total, with each component counted exactly once, and each amount matches the order record". Converted by `meta-models/muse-spark-open-1026` (2 gate rounds) | `demo/C1-04.yaml` |
| 2. Approve, then fresh replay on beta2 and beta3 | beta2 FAIL and beta3 PASS | **did not pass**: beta2 FAIL (3/3, evidence partially verified); beta3 **not_measurable** (2 of 3 judgments ran to the 16K-token cap, 1 said pass). Memory: `not_confirmed` | `acceptance/run2-*.json` |
| 3. A NEW run from storage only (`run-saved`; nothing imported) | runs at the same approved digest, same results | **ran from storage at digest `f0cb1dc9ee14fc8f`**: beta2 FAIL (2 fail / 1 pass), beta3 PASS (2 pass / 1 runaway), evidence verified on beta3; memory `fix_confirmed`. Same digest: yes. Same results as Run 2: base yes (FAIL), head no (Run 2 was not_measurable) | `acceptance/run3-transcript.txt` (command, file listing with hashes, output), `run3-saved-checks.json`, `cards-run3.html` |
| 4. Optional: different basket, same saved invariant (hand variant C1-04-v1: Personal Blender x3, nothing else changed) | same FAIL/PASS, different figures | **pass**: beta2 FAIL 3/3, beta3 PASS 3/3, evidence verified on beta3; memory `fix_confirmed` | `acceptance/run4-*.json`, `cards-run4-variant.html`, `C1-04-v1.yaml` |
| 5. Optional: converted findings in groups SRA's 11 shoppers did not report (F11, P01, P03, P04, P06, P07) | report N of M | **0 of 24**. (Correction: only F11 is in `grading/key-v4.json`; the P groups are in `scores/scores.json` `new_families`.) 4 of the 24 are partially converted, 2 adapter_gap, 18 not converted | below |

**Email figures from these captures (for the video):**
- Run 2/3, beta2: `Subtotal: $179.98 / Promotion: Promotion (Free Shipping) -$15.00 / Shipping: Express $0.00 /
  Tax: $14.40 / Order Total: $194.38` (179.98 - 15.00 + 0.00 + 14.40 = 179.38, not 194.38).
- Run 3, beta3: same, with `Shipping: Express $15.00` (adds up).
- Run 4, beta2: `(3) @ $49.99 = $149.97 / Subtotal: $149.97 / Promotion -$15.00 / Shipping: Express $0.00 /
  Tax: $12.00 / Order Total: $161.97`; beta3: `Shipping: Express $15.00`.

**What the runs show beyond pass/fail:** the semantic-confidence status earned its place. In Run 3 one beta2 judgment
said PASS on the broken email, reasoning that the promotion was "already reflected in net shipping"; it was outvoted
2-1 and the page shows "medium, 2/3". Runaway replies hit the beta3 / next email for this check unusually often (2/3
in Run 2, 1/3 in Run 3, 2/3 in next run 3 of the held-out set); that is the main threat to the demo beat.

Run 5 detail (held-out findings whose graded family is one of the six): C1#02, C1#03, C1#05, C1#10, C1#14, C2#03,
C2#05, C2#06, C2#07, C2#08, X1#00, X1#02, X1#05, X1#06, X2#01, X2#03, X2#05, M2#04, M2#05, M2#06, M3#03, M3#04, M3#05,
M3#06. None converted, so no second demo example qualifies under the rule "first such finding in held-out order that
converts".

Spend for the acceptance runs: $0.70 (of which $0.34 in Run 2, mostly four replies at the token cap). Total for the
slice: **$9.31**, all Baseten.
