# 8. Evaluation and benchmark

## What we are trying to show, stated honestly

A capable frontier model with a browser, the docs, test accounts, the owner's principles and enough time **can** find Maya's conflicting recommendations. Some agentic QA platforms already combine autonomous exploration with a product knowledge base. So the claim is **not** "a model cannot find this".

The claim is narrower and testable:

> Given the same model, the same context and the same budget, the auditor **covers more of the experiences that matter**, produces **evidence that holds up and can be reproduced**, raises **fewer false alarms on legitimate behaviour**, and gives **the same answer release after release**, respecting the owner's past decisions.

If the baseline matches or beats the auditor on a measure, we publish that too.

## Three evaluations, scored separately

| Evaluation | Baseline (same model, same context, same budget) | What the auditor must show |
|---|---|---|
| **E1 Experience coverage** | **B-explore**: Muse Spark as a browser agent, given the contract docs, the owner principles, the persona and clock hooks, and the same tool-call, time and $ budget. Free to explore however it likes | It reaches more of the issue-bearing (persona × scenario × surface × time) combinations, including time-triggered and post-action ones |
| **E2 Judgment quality** | **B-judge**: Muse Spark, one long-context call, given **the auditor's own captured stories**: every capture in time order with persona, state, feature labels, plus the principles with exceptions and the release notes. A strong prompt, published | Higher precision and recall; a lower false-positive rate on negative controls; explanations whose every cited event really exists in the evidence |
| **E3 Release reproducibility** | **B-repeat**: B-explore + B-judge as a one-off review, run *k* = 3 times per release | Stable issue sets across runs; findings that replay on demand; correct attribution (new vs pre-existing, which feature); owner decisions respected on the next release |

E2 deliberately gives the baseline the auditor's coverage, so it measures *judgment* alone. E1 measures *coverage* alone. This separation is what keeps the comparison meaningful even if the baseline judges well.

### Fairness rules

1. **Same model family and version** for the baseline as the auditor's interpreter.
2. **Same information:** principles with their exceptions, release notes, contract docs and hooks. Nothing the auditor uses is withheld.
3. **Equal prompt effort:** the baseline prompt is iterated on the *narrative* fixture (2.4) for the same number of rounds as the auditor's prompts, then frozen before any benchmark run. Both prompts are published in `bench/conditions/`.
4. **Same budget** for E1: tool calls, wall time and $.
5. **Same scoring:** identical matching rules, the same adjudicators, and adjudicators blind to which system produced a finding.

## Fixtures

| Fixture | Purpose | Used for headline numbers? |
|---|---|---|
| **Narrative**: Northbound 2.3 → 2.4 → 2.4.1 | the demo story; prompt development for both systems | **no** (labelled "dev" wherever shown) |
| **Benchmark**: Northbound `bench-01 … bench-NN` | the frozen, unseen test set | **yes** |
| **Real product**: Finablo historical releases | external validity | reported separately, with denominators |

### Freezing the benchmark

- A separate session builds `bench-NN` from 2.3. Each release has 2–4 new features, a mix of issue-bearing and negative-control interactions, and a ground-truth file `bench/ground_truth/bench-NN.yaml`.
- Until scoring, the bench releases and ground truth live **outside the repo**. The **sha256 of each ground-truth file is committed** to `bench/FROZEN.md` before any system is run against it, so anyone can verify afterwards that nothing changed.
- The session building the auditor never reads them, and issue descriptions are never in either system's context.
- **Stated limitation:** this is process-level independence, not full independence. One owner designed both. We say so in the README and the video.

### Target composition (to be confirmed by the seeding session)

| | Count (target) |
|---|---|
| bench releases | 6 |
| issue-bearing interactions | 24 (≥3 of each kind: competing directives, stale guidance, principle breach, unexplained tradeoff, attention load, fact divergence, unsupported assertion) |
| **negative controls** | **≥ 18**, at least 3 per pattern: exception applies, explained tradeoff, duplicate_ok, persona-legitimate difference, actionable post-purchase offer, compatible-in-time (messages that would conflict but are never live together) |
| personas | 8 per release |

Negative controls are a first-class part of the test set, not a footnote. A system that raises everything scores perfect recall and fails here.

## Ground truth and adjudication

- **Objective kinds** (fact divergence, unsupported assertion, stale guidance with a data precondition): ground truth comes from the oracle and the seeded diff. No human judgement is needed.
- **Subjective kinds** (competing directives, principle breach, tradeoff explained or not, attention load): the seeded label is a **hypothesis**. Every finding from either system, and every seeded item, is adjudicated by:
  - the **owner**, applying their own principles, and
  - **one independent human adjudicator**, if we can recruit one (open decision D12). They are given the principles and the evidence, and are blind to which system produced the finding.
- We report agreement between the adjudicators (Cohen's κ), and score against the **owner's** labels, with the independent adjudicator's labels as a second line.
- A finding the adjudicators deem real but unseeded counts as a **true positive** for whichever system found it, and is added to the denominator for both systems.

## Metrics

**E1 Coverage**
- Share of ground-truth issue-bearing combinations reached (an issue's events all captured).
- Share of time-triggered and post-action events captured.
- Cost and wall time.

**E2 Judgment** (on identical stories)
- Precision and recall overall and by kind, with denominators.
- **False-positive rate on negative controls**, reported by pattern.
- **Evidence support**: the share of findings in which every cited event, quote and value resolves to a real capture. A finding citing something that is not in the evidence counts as unsupported.
- Severity agreement with the adjudicators (a separate axis, not part of precision).
- Calibration: of findings marked high confidence, the share the adjudicators confirmed.

**E3 Reproducibility**
- Run-to-run stability: the mean Jaccard of issue sets across *k* = 3 runs.
- Replay success: the share of findings whose repro command reproduces them.
- Attribution accuracy: new vs pre-existing, and the responsible features.
- **Memory:** on 2.4.1 and on a bench "next release", the share of *fixed* issues correctly marked resolved, accepted exceptions correctly honoured, and out-of-scope variants correctly raised.

**Ablations** (the auditor minus one part, all on the benchmark)

| Ablation | Removes |
|---|---|
| no-generators | the model-only `model_open` pass over the story; tests whether code-generated candidates matter |
| no-exceptions | principles without their conditions and exceptions; expected to fail the negative controls |
| no-verifier | candidates are reported directly |
| no-delta | head only; tests attribution and new/pre-existing |
| no-time | stories without ordering or state; tests stale guidance and windows |

## Real product: Finablo

- **Inputs given to the auditor:** Finablo's `VISION.md` and product principles **as they existed in git before the historical release**, an owner voice note, synthetic personas, and the two builds (the commit before and the release commit). **Not given:** `CLAUDE.md`, `BUG-HISTORY.md`, `PLAN.md` and the handoff cards, all of which describe the historical bugs. The exact input list and commit SHAs are recorded in the run.
- **Events:**
  - **R1, objective:** the pending-page 401(k) limit for a 61-year-old (the page showed $24,500; the server and the export said $35,750).
  - **R2, experience-level candidate:** the dashboard hero's on-pace framing vs a new pillar card's urgent directive. This counts as a finding **only if it survives a contextual adjudication**, because "ahead overall, with one urgent task" can be a legitimate combination.
- **Reporting rule:** R1 is the real-product validation. R2 appears in the video only if adjudicated as a real conflict. Otherwise we say plainly that the experience-level capability is demonstrated on Northbound.
- **Data:** synthetic profiles only; Standard-mode endpoints only.

## Reporting

`bench/results/<date>/` holds the scores for every condition, all findings from both systems (including false positives), the adjudication sheet, κ, costs and the frozen hashes. The video shows the headline numbers *as measured*, including any measure where the baseline wins.
