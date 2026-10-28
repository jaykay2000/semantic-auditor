# W13b sealed run: follow-ups (2026-10-27/28)

All sealed figures below are COUNTS from the benchmark session. The building session never read a sealed file.
The frozen result (5e32f9a) is unchanged. Everything here is reported beside it, never in place of it.

## Frozen result, pre-adjudication (3 sealed releases, r1)
| system | found (of 15) | false alarms | negative controls hit | cost |
|---|---|---|---|---|
| auditor (full) | 8 | 36 | 2 of 40 | $1.64 |
| B-judge-1 (one call) | 15 | 0 | 0 of 40 | $0.19 |
| B-judge-N (multi-pass) | 14 | 0 | 0 of 40 | $1.56 |

## Why the auditor lost: two step-level defects, both before any judging
1. **False alarms: 34 of 34 unmatched units were one defect.** They were all on one objective date/time rule, all on
   messages that stated the CORRECT time. `claim["value"] == truth` can never pass for a timestamp. Fixed in
   06f72a1 (relate/claims.py: one comparison, at the claim's own precision; an unreadable claim is never raised).
2. **Misses: 6 of 7 were a decision-filing gap.** An action listed under two decisions; the model filed the message
   under the other one (normalize overruled nothing: 0 of 293 messages), so the rule never ran. The 7th was a
   date/time claim that was never extracted. Fixed on branch `fix/shared-action-decisions` (4cfc0a2, not merged):
   a shared action bears on every decision that lists it.
- The verifier removed nothing. It can only drop a finding whose verification `failed`, and the misses never
  reached it.
- The ground truth's scope, per the benchmark author: objective kinds = every real head issue; judged kinds =
  seeded only. All truth deltas are "new".

## B-judge-1's inputs came from the auditor
B-judge-1 judged the auditor's own captures, structured stories, oracle readings and structured contract, with
the auditor's method written into its prompt. So E2 shows the auditor's multi-step JUDGING adds nothing on top of
those inputs. It does not show what the inputs are worth. That is the input ablation
(bench/conditions/INPUT-ABLATION.md, committed 16bd979 before running).

## Dev scale pilot (fb222a9). DEV ONLY, one run per cell
Hand-written 2.4 stories padded with rule-neutral in-app messages (padding proven answer-neutral by
tests/test_scale_pilot.py).

| scale | events | auditor core: found / false / cost | B-judge-1: found / false / cost |
|---|---|---|---|
| 1x | 70 | 16 / 0 / $0.048 | 14 / 0 / $0.061 |
| 4x | 280 | 16 / 0 / $0.068 | 14 / 0 / $0.093 |
| 16x | 1,120 | 16 / 0 / $0.108 | 16 / 0 / $0.175 |
| 32x | 2,240 | 16 / 0 / $0.162 | 16 / 0 / $0.303 |

Reading: bland padding up to ~140k tokens did NOT degrade the one-call baseline. Its 2 misses at 1x/4x are within
single-run noise. Cost grows ~5x for the baseline and ~3.4x for the auditor, so the auditor is ~1.9x cheaper at
32x. This pilot is no evidence of an accuracy advantage at scale. Padding is the easy, literal kind of length; the
literature's hard cases are non-literal multi-hop reasoning and temporal arithmetic. Pilot spend $0.94.

## Input ablation of B-judge-1 (plan committed first: 16bd979), sealed r1 captures, one run per variant
Benchmark-session counts, 2026-10-28. Spend $0.5476 (ledger matches). The frozen-file check printed nothing.

| variant (cumulative) | found (of 15) | false alarms | NC hits | cost |
|---|---|---|---|---|
| V0 frozen B-judge-1 | 15 | 0 | 0 of 40 | $0.19 |
| V1 no written judging method | 15 | 0 | 0 of 40 | $0.20 |
| V2 also no oracle readings | 12 | 1 | 1 of 40 | $0.18 |
| V3 also plain-English rules instead of the structured contract | 10 | 6 | 1 of 40 | $0.16 |

Reading:
- The written method added nothing.
- Without the oracle readings, the one call found 3 fewer issues.
- Also without the structured contract, it found 5 fewer and raised 6 false alarms.

So the auditor's EVIDENCE layer (true state over time + the owner's structured contract) is what makes one call
accurate. Its prompt wording is not. The captures themselves were never removed (that is E1). Caveat: n is small
(15 issue units), one run per variant, and the variants are cumulative, so V3's effect includes V2's.
