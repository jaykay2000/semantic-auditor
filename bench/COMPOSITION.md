# Benchmark composition attestation

Public by design: aggregate counts only, with no ids, personas, features, copy keys, rules or text. Written
2026-10-27 by the W13a sealing session (the benchmark's custodian). The counts come from the sealed ground truth
pinned in `bench/FROZEN.md` (third freeze, `MANIFEST.sha256` `f1701ccff7b9310b6ab15580f0dc0eeee9026f227c374218d906f9be0cd99e0b`).
After unsealing, anyone can recount them from `ground_truth/bench-NN.yaml`. Categories follow docs/08-evaluation.md,
"Target composition". The issue kinds of subjective items are the seeding session's hypotheses until adjudicated.

## Issues by kind

| Kind | bench-01 | bench-02 | bench-03 | Total |
|---|---|---|---|---|
| conflicting directives | 1 | 0 | 1 | 2 |
| unexplained tradeoff | 1 | 0 | 1 | 2 |
| stale guidance | 1 | 0 | 1 | 2 |
| conditional-rule breach | 3 | 0 | 0 | 3 |
| attention load | 1 | 0 | 1 | 2 |
| fact divergence | 1 | 0 | 1 | 2 |
| false claim | 1 | 0 | 1 | 2 |
| **Total** | **9** | **0** | **6** | **15** |
| objective | 4 | 0 | 4 | 8 |
| subjective | 5 | 0 | 2 | 7 |

## Negative controls by pattern

| Pattern | bench-01 | bench-02 | bench-03 | Total |
|---|---|---|---|---|
| exception applies | 2 | 4 | 0 | 6 |
| reconciled or explained tradeoff | 1 | 1 | 1 | 3 |
| duplicate_ok | 2 | 2 | 1 | 5 |
| persona-legitimate difference | 1 | 2 | 1 | 4 |
| actionable post-purchase offer | 2 | 2 | 2 | 6 |
| compatible-in-time | 0 | 1 | 1 | 2 |
| unverifiable-but-not-false claim | 0 | 2 | 2 | 4 |
| user-initiated conversation excluded from load | 1 | 1 | 1 | 3 |
| *four further sub-patterns outside the eight (combined)* | 2 | 2 | 3 | 7 |
| **Total** | **11** | **17** | **12** | **40** |

## Rule-boundary cases by pattern

Boundary cases are tags over the issues and negative controls above, not separate items.

| Pattern | bench-01 | bench-02 | bench-03 | Total |
|---|---|---|---|---|
| exception satisfied while a coherence rule is still violated | 1 | 0 | 0 | 1 |
| exception failing on a false claim | 1 | 0 | 0 | 1 |
| qualifying-looking attribute that is not the condition | 1 | 0 | 0 | 1 |
| exact threshold | 1 | 1 | 1 | 3 |
| threshold + 1 | 1 | 0 | 0 | 1 |
| exception used outside its scope | 1 | 0 | 0 | 1 |
| *one further pattern outside docs/08's list* | 0 | 0 | 1 | 1 |
| **Total** | **6** | **1** | **2** | **9** |

## Personas

| | bench-01 | bench-02 | bench-03 | Total |
|---|---|---|---|---|
| personas | 8 | 7 | 8 | 23 |

## Minimums (docs/08 "Target composition")

- **Issues, ≥2 of each of the seven kinds:** met. Every kind has at least 2, and there are 15 issues in total,
  which equals the 15 target.
- **Rule-boundary cases, ≥6:** met, with 9. Each of the patterns docs/08 lists has at least 1.
- **Negative controls, ≥15 with ≥2 per pattern:** met. There are 40 in total, and 33 of them fall under the
  eight docs/08 patterns. Each of the eight has at least 2 even without the 7 under further sub-patterns.
- **Personas, up to 8 per release:** met, with at most 8.
