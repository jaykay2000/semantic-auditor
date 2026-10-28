# W13c post-fix evaluation: plan, written before the new releases exist (2026-10-28)

**Status: committed before the benchmark session builds the new releases, and frozen
(`FROZEN-POSTFIX.md`) before any model runs on them.** W13b (`FROZEN-CONDITIONS.md`, 5e32f9a) stays the original
result and is never rewritten. This is a separate, post-fix evaluation, reported beside it. **No tuning or patching
after these results are seen.** Any later change is evaluated on releases that do not exist yet.

## What changed since W13b, and why a fresh set is needed
Fixes made after reading W13b's counts-only breakdowns:
- 06f72a1 + e9bbd1e: one claim comparison, with date/time at the claim's precision, detected from the measured
  values.
- 4cfc0a2: a shared action bears on every decision that lists it.

Re-running on bench-01..03 after seeing their answers would only be a post-hoc check. A claim needs releases
nobody has tuned against.

## The new releases (built by the benchmark session, sealed before any run)
- Three new sealed Northbound releases, `bench-04`, `bench-05`, `bench-06`, sized like bench-01..03.
- At least one is genuinely issue-free.
- Varied seeded issues and negative controls, at least as broad in docs/08 patterns as bench-01..03. Not
  reproductions of the two W13b defects: at most about a third of the seeded items may involve a date/time claim
  or a shared action.
- Truth is written, normalized, hashed and sealed BEFORE any model call. The seal check must pass at run time.
- The benchmark session attests composition as counts only (as `bench/COMPOSITION.md` did).

## Systems, all fresh (no cache), same models and settings as W13b
| system | runs |
|---|---|
| auditor (`semaudit-full`), merged main at the freeze | run 1 on every release; runs 2 and 3 on the stability release |
| B-judge-1, the strongest W13b baseline, frozen prompt | on each release's run-1 captures; on the stability release's run-2 and run-3 captures too (comparable repeats) |
| B-judge-N | on run-1 captures, LOWEST priority, only if budget remains (W13b: weaker than B-judge-1 at 8x its cost) |

Stability release: the first issue-bearing release (`--stability`). Scored by the frozen matcher, pre-adjudication,
with the same blind adjudication sheets as W13b.

## Predeclared success thresholds (each reported as met / not met / not measured)
| claim | met when | numbers |
|---|---|---|
| False-alarm control | auditor false alarms <= **2** over all releases, AND **0** on every issue-free release, AND auditor negative-control hits <= B-judge-1's **+ 1** | `fp_total_max = 2`, `fp_issue_free_max = 0`, `nc_margin = 1` |
| Recall | auditor recall >= **0.80**, AND >= B-judge-1's recall **- 0.10** (non-inferiority) | `recall_min = 0.80`, `recall_margin = 0.10` |
| Stability | auditor Jaccard over its 3 fresh runs >= **0.90**, AND >= B-judge-1's Jaccard over its 3 comparable runs | `stability_min = 0.90` |
| Cost | auditor fresh cost <= **$1.00** per release. Reported beside both baselines; this does NOT claim the auditor is cheaper | `cost_per_release_max = 1.00` |

`scripts/w13c_postfix.py` evaluates exactly these numbers (`THRESHOLDS`). `tests/test_postfix_runner.py` pins the
script and this table against each other. With ~15 issue units, the intervals are wide: every verdict is reported
with its Wilson interval, and a "met" is a result on these releases, not a general claim.

## Budget
Cap `--max-usd 4.30`, the W13b budget left. Steps run in priority order, and a step whose cap does not fit is
skipped and recorded. Expected ~$4.0 without B-judge-N.
