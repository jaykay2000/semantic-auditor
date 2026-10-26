# Benchmark

The proof that the system beats a prompt.

## Conditions

| Condition | What runs |
|---|---|
| **baseline-prompt** | Muse Spark, one long-context call: product docs + release notes + *every* capture of both builds for the tester's default persona. Asked to list semantic issues with evidence. |
| **baseline-prompt-all-personas** | Same, but given the auditor's full persona captures. This isolates the value of reasoning and verification from the value of coverage. |
| **sra-full** | The whole pipeline. |
| **ablation-no-contract** | sra without the contract: no oracles, invariants or allowlist. |
| **ablation-no-verifier** | sra with candidates reported directly. |
| **ablation-no-diff** | sra auditing head alone, with no base build or release intent. |

## Metrics

Per condition, against `ground_truth/northbound-v2.yaml`:
- **recall** per finding family and overall;
- **precision**: confirmed findings that match a ground-truth issue, over all confirmed findings. Decoys flagged count as false positives;
- **partial-rollout catch** (yes/no);
- **$ and wall time**;
- held-out split: issues used for tuning are reported separately from issues never looked at.

Matching rule: a finding matches an issue when the family, the fact (or topic) and at least one surface agree. Each issue can be matched at most once.

## Layout

```
bench/
  ground_truth/   sealed until Phase 4 (blind seeding)
  conditions/     condition configs
  results/        committed scored runs: the numbers the video shows
```

## Real-world events

`ground_truth/finablo-*.yaml` (outside the sealed set): real historical Finablo bugs, recreated on local branches, audited blind. They are reported separately from the synthetic score.
