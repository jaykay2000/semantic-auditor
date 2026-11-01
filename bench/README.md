# Benchmark

The protocol lives in [docs/08-evaluation.md](../docs/08-evaluation.md). This folder holds its artifacts.

```
bench/
  FROZEN.md        sha256 of each sealed ground-truth file, committed BEFORE any system runs on it
  ground_truth/    empty until scoring; sealed files are kept outside the repo until then
  conditions/      configs and frozen prompts for every condition:
                   semaudit-full · B-explore · B-judge · B-repeat · ablations
  adjudication/    blind adjudication sheets (owner, independent adjudicator), with κ
  results/<date>/  scores, every finding from every system (false positives included),
                   costs, input hashes
  reference/       hand-written Northbound reference contract (onboarding answer key)
```

## Rules

- The session building the auditor never reads sealed ground truth or the bench release diffs.
- The baseline prompts and auditor prompts are frozen before the first benchmark run, after equal tuning on the narrative fixture (Northbound 2.4).
- Headline numbers come only from `bench-NN`. Narrative-fixture results are labelled "dev".
- Every result file lists its denominators. Negative-control false positives are reported per pattern.

## Access log

- **2026-11-01, sealed contracts read by a build session (owner accepted).** While fixing new-user test finding 3
  (`decide/issues.py`, commit `4e7bd8d`), the build session rebuilt every stored review it could, offline (model
  cache only, no model calls), to confirm the fix changed no issue id, rule, signature, severity or persona (22 of 32
  rebuilt). To rebuild the bench reviews it loaded the sealed benchmark's **contracts** from the sealed folder. It
  read **no ground-truth files and no bench release diffs**, and it reported **issue counts only**. The owner accepted
  this on 2026-11-01. Nothing in the sealed folder was changed and nothing was re-sealed; the sealed hashes were not
  re-checked for this entry.
