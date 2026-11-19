# Verdict stability, first measurement: old vs current defender instructions, 3 runs each (2026-11-18)

**Question.** In the Spree 6.0.3 → 6.0.4 escape catch test ([write-up](../escape-catch-spree-6.0.3-6.0.4.md)), one
false alarm on 6.0.4 (the admin page's payment, $955.79, read as the tax) has four occurrences. After the defender was
allowed to dispute which fact a figure states, a single run dropped three of them and kept the fourth. Was that the
new instructions, or one run's luck? One run cannot say.

**How.** `semaudit compare-prompts runs/esc-2/review-before-after.json --old 96eb296 --repeats 3` in the Spree
harness's `review-root-escape-xfam` (readings and defence on Muse Spark, the second-model check on Claude Sonnet
5.5). It re-derives the review's issues from the pinned episodes (recorded readings, no new reading), then runs the
second-model check and the defence 3 times on each issue under the defender instructions of commit `96eb296` (before
the figure dispute) and 3 times under the current ones. The adjudication code is the current code for both, so only
the instructions differ. Run 0 of each is the ordinary request; runs 1 and 2 send seeds 1 and 2.

## Result ([raw](compare-spree-6.0.4-k3.json))

"Defence held" counts the runs in which the issue survived the defence (n of 3).

| occurrence of the false alarm | second model reproduces it | old instructions: defence held | current: defence held | current status |
|---|---|---|---|---|
| U1, admin page | 0 of 3 | 3 of 3 | **0 of 3** | failed: disputed |
| U2, admin vs storefront order page (1) | 0 of 3 | 3 of 3 | **1 of 3** | partly verified (mixed) |
| U2, admin vs storefront order page (2) | 0 of 3 | 3 of 3 | **0 of 3** | failed: disputed |
| U2, admin vs order email | 0 of 3 | 3 of 3 | **0 of 3** | failed: disputed |

- **The change is the instructions, not luck.** With the old ones the defence never stood (0 of 12 runs dropped an
  occurrence). With the current ones it stood in 11 of 12.
- **The fourth occurrence is run-to-run variation.** The defence stood in 2 of its 3 runs. With `--repeats 3` it is
  `mixed`: not verified, not dropped, confidence low, and the page says "held in 1 of 3 runs".
- **The second model never reproduced it** (0 of 12 runs): Claude Sonnet 5.5 does not read the payment as the tax.

## Cost

$1.97 in all, of which $0.075 was the second model's 8 new Claude calls; the rest is the defender (Muse Spark 1.2,
about $0.065 a call): 30 distinct requests for 4 issues with 6 occurrences, 2 instruction versions and 3 runs, less
the 6 already recorded. Every old-instruction run was new, because the defender's input now also shows the figures
read, so no earlier reply matched. The run stopped at its spend cap three times and was resumed from the recorded
replies; no request was paid twice (checked: 30 distinct request digests, each in the cache once).

## Limits

- One false alarm on one page, one store: it shows the instrument works and what the instructions changed here, not
  a rate.
- 3 runs: "mixed" means the verdict is unstable, not how unstable.
- Only the defender's instructions are compared; a changed extraction or judging prompt is reported, not swapped.
