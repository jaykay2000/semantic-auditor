# W13b round 0: the judge baselines on the dev fixture (Oct 27)

**Dev only** (Northbound 2.4, the fixture both systems are tuned on); never a headline number. Truth: the W1b
hand-written status vectors (`bench/dev/northbound-2.4.truth.json`, 16 issue units, 6 negative controls,
13 personas). Baseline prompts are round 0 (`bench/conditions/prompts`), not yet tuned. Spend $0.83.

| System | TP | FP | FN | Precision | Recall | $ | calls |
|---|---|---|---|---|---|---|---|
| auditor (semaudit-full, cached review) | 16 | 0 | 0 | 1.00 | 1.00 | 0.41 | many |
| B-judge-1, run 1 | 15 | 0 | 1 | 1.00 | 0.94 | 0.10 | 1 |
| B-judge-1, run 2 (fresh) | 14 | 0 | 2 | 1.00 | 0.88 | 0.10 | 1 |
| B-judge-1, run 3 (fresh) | 15 | 0 | 1 | 1.00 | 0.94 | 0.10 | 1 |
| B-judge-N | 16 | 2 | 0 | 0.89 | 1.00 | 0.52 | 17 |

- B-judge-1 missed U2 (fee displayed vs fee charged, Sam & Alex) in 2 of 3 runs, and U4 (second-guessing after
  booking, Maya and Maya-R) in 1 of 3. Run-to-run Jaccard over the 3 fresh runs: **0.87**. The auditor's fresh
  runs on the same captures were exact 5 of 5 (W8).
- B-judge-N found all 16 but raised the two **explained-tradeoff negative controls** (Lena, Maya-R) as
  unexplained tradeoffs: it grouped them with Maya into one finding and did not credit the reconciler.
- Every baseline finding cited real events with verbatim quotes (evidence support 1.00).

**What this means.** On judgment over identical captured stories, on the fixture the auditor was built on, one
Muse Spark call comes close at a quarter of the cost. The protocol anticipated this (docs/08: "if the baseline
matches or beats the auditor on a measure, we publish that too"). The auditor's measurable advantages here are
stability (exact vs 0.87) and the negative controls the multi-pass baseline fails; the sealed bench, with more
boundary cases and negative controls, is where the comparison counts.
