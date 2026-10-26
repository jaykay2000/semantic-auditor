# 8. Evaluation and benchmark

## What we are trying to show, stated honestly

A capable frontier model with a browser, the docs, test accounts, the owner's principles and enough time **can** find Maya's conflicting recommendations. Some agentic QA platforms already combine autonomous exploration with a product knowledge base. So the claim is **not** "a model cannot find this".

The claim is narrower and testable:

> Given the same model, the same context and the same budget, the auditor **covers more of the experiences that matter**, produces **evidence that holds up and can be reproduced**, raises **fewer false alarms on legitimate behaviour**, and gives **the same answer release after release**, respecting the owner's past decisions.

If the baseline matches or beats the auditor on a measure, we publish that too.

## Three evaluations, scored separately

| Evaluation | Baseline (same model, same context, same budget) | What the auditor must show |
|---|---|---|
| **E1 Experience coverage** | **B-explore**: Muse Spark as a browser agent, given the contract docs, the owner rules, the persona and clock hooks, and the same tool-call, time and $ budget. **B-explore+scenarios**: the same agent, also given the auditor's scenario definitions | It reaches more of the issue-bearing (persona × scenario × surface × time) combinations, including time-triggered and post-action ones |
| **E2 Judgment quality** | **B-judge-1**: Muse Spark, one long-context call, given **the auditor's own captured stories** (every capture in time order, with persona, state and feature labels), the rules with their exceptions, and the release notes, under a strong published prompt. **B-judge-N**: a **budget-matched multi-pass** baseline on the same input: per-persona passes, a self-critique pass and a consolidation pass, at the same $ as the auditor's interpretation plus verification | Higher precision and recall; a lower false-positive rate on negative controls; explanations whose every cited event really exists in the evidence |
| **E3 Release reproducibility** | **B-repeat**: a one-off agentic review, i.e. B-explore followed by a multi-pass judge (same structure as B-judge-N) over **B-explore's own captures**, run *k* = 3 times per release | Stable issue sets across **fresh** runs; findings that replay on demand; correct attribution (new vs pre-existing, which feature) |

E2 deliberately gives the baseline the auditor's coverage, so it measures *judgment* alone. E1 measures *coverage* alone. This separation is what keeps the comparison meaningful even if the baseline judges well.

**Scenarios are setup work, and are counted as such.** The auditor's coverage partly comes from owner-approved scenarios. E1 reports both B-explore variants, so the value of the scenarios is visible separately from the value of the runner. The owner's minutes spent writing or approving scenarios are reported as setup cost. If B-explore+scenarios matches the auditor, the honest conclusion is that the scenarios, not the runner, supply the coverage.

**Inference effort is reported.** The auditor makes several model calls per candidate (interpretation, cross-check, defense). Every condition reports its $ and calls, and B-judge-N exists so that "more passes" is not mistaken for "a better system".

### Fairness rules

1. **Same model family and version** for the baseline as the auditor's interpreter.
2. **Same information:** principles with their exceptions, release notes, contract docs and hooks. Nothing the auditor uses is withheld.
3. **Equal prompt effort:** the baseline prompt is iterated on the *narrative* fixture (2.4) for the same number of rounds as the auditor's prompts, then frozen before any benchmark run. Both prompts are published in `bench/conditions/`.
4. **Same budget** for E1 (tool calls, wall time, $), and for B-judge-N in E2 ($ matched to the auditor's measured spend).
5. **Same scoring:** identical matching rules, the same adjudicators, and adjudicators blind to which system produced a finding.

## Fixtures

| Fixture | Purpose | Used for headline numbers? |
|---|---|---|
| **Narrative**: Northbound 2.3 → 2.4 → 2.4.1 | the demo story; prompt development for both systems | **no** (labelled "dev" wherever shown) |
| **Benchmark**: Northbound `bench-01 … bench-03` | the frozen, unseen test set | **yes** |
| **Real product**: Finablo historical releases | external validity | reported separately, with denominators |

### Freezing the benchmark

- A separate session builds `bench-NN` from 2.3. Each release has 2–4 new features, a mix of issue-bearing and negative-control interactions, and a ground-truth file `bench/ground_truth/bench-NN.yaml`.
- Until scoring, the bench releases and ground truth live **outside the repo**. The **sha256 of each ground-truth file is committed** to `bench/FROZEN.md` before any system is run against it, so anyone can verify afterwards that nothing changed.
- The session building the auditor never reads them, and issue descriptions are never in either system's context.
- **Who writes the bench contracts.** The seeding session also writes each bench release's contract additions (features, decision vocabulary with incompatible and tradeoff pairs, scenarios), acting as the product owner. It writes them **as product policy first, committed and hashed before seeding any issue**, so that the vocabulary is generic ("lock and wait are a material tradeoff"), not a list of answers. Both the auditor and the baselines receive the same contract at run time; no developer of the auditor reads it.
- **Stated limitation:** this is process-level independence, not full independence. One owner designed both. We say so in the README and the video.

### Target composition (to be confirmed by the seeding session)

| | Count (target) |
|---|---|
| bench releases | 3 |
| issue-bearing interactions | 15 (≥2 of each kind: conflicting directives, unexplained tradeoff, stale guidance, conditional-rule breach, attention load, fact divergence, false claim) |
| **rule-boundary cases** | ≥ 6: an exception satisfied while a coherence rule is still violated (Kai pattern); an exception failing on a false claim (Omar pattern); a qualifying-looking attribute that is not the condition (Hana pattern); an exact threshold and threshold + 1 (Raj@72h pattern); an exception used outside its scope |
| **negative controls** | **≥ 15**, at least 2 per pattern: exception applies; reconciled or explained tradeoff (with both features' recommendations present); duplicate_ok; persona-legitimate difference; actionable post-purchase offer; compatible-in-time; unverifiable-but-not-false claim; user-initiated conversation excluded from load |
| personas | up to 8 per release |

Negative controls are a first-class part of the test set, not a footnote. A system that raises everything scores perfect recall and fails here.

## Matching rule (how a finding is scored)

A finding **matches** a ground-truth item when all of these agree:
- the persona (or one of the grouped personas);
- the rule id;
- the **label**, where it is part of the truth (`conflict` vs `unexplained_tradeoff` are scored as different answers);
- the event set: for relations, the pair of features plus the decision; for single events, the feature, surface and message key.

Each ground-truth item can be matched at most once. A finding that matches nothing is a false positive *unless* adjudication accepts it as a real, unseeded issue (see below). The matcher is a script in `bench/` that reads both systems' outputs in the same normalized format, so no finding is matched by hand. A baseline's free-text finding is normalized into that format by a fixed, published prompt, and its normalizations are kept for inspection.

## Ground truth and adjudication

- **Objective kinds** (fact divergence, false claim, stale guidance with a data precondition): ground truth comes from the oracle and the seeded diff. No human judgement is needed.
- **Subjective kinds** (competing directives, principle breach, tradeoff explained or not, attention load): the seeded label is a **hypothesis**. Every finding from either system, and every seeded item, is adjudicated by:
  - the **owner**, applying their own principles, and
  - **one independent human adjudicator**, if we can recruit one (open decision D12). They are given the principles and the evidence, and are blind to which system produced the finding.
- **Blinding:** adjudication sheets are generated by script, with system names removed, findings re-worded into one neutral template and shuffled. The owner built the auditor and may still recognise its style, so we say so. Adjudication is spread over Nov 1–2.
- We report agreement between the adjudicators (Cohen's κ), and score against the **owner's** labels, with the independent adjudicator's labels as a second line.
- A finding the adjudicators deem real but unseeded counts as a **true positive** for whichever system found it, and is added to the denominator for both systems.

## Metrics

**E1 Coverage**
- Share of ground-truth issue-bearing combinations reached (an issue's events all captured). **Measurable for the baseline** because B-explore's browser tool is wrapped by the same capture adapter, so every page, email, push and chat it sees is logged as a capture in the same format.
- Share of time-triggered and post-action events captured.
- Cost and wall time.

**E2 Judgment** (on identical stories)
- Precision and recall overall and by kind, with denominators.
- **Label accuracy** on coherence findings: `conflict` vs `unexplained_tradeoff` vs `explained_tradeoff`.
- **False-positive rate on negative controls**, reported by pattern.
- **Evidence support**: the share of findings in which every cited event, quote and value resolves to a real capture. A finding citing something that is not in the evidence counts as unsupported.
- Severity agreement with the adjudicators (a separate axis, not part of precision).
- Calibration: of findings marked high confidence, the share the adjudicators confirmed.

**E3 Reproducibility**
- Run-to-run stability: the mean Jaccard of issue sets across *k* = 3 **fresh** runs (cache disabled, extraction and interpretation re-run). Cached replays are reported separately as *replay determinism*, which demonstrates reproducibility of evidence, not stability of inference.
- Replay success: the share of findings whose repro command reproduces them.
- Attribution accuracy: new vs pre-existing, and the responsible features.
- **Memory** (narrative fixture only, labelled *dev*): on 2.4.1, the share of *fixed* issues correctly marked resolved, accepted exceptions correctly honoured, and out-of-scope variants correctly raised. The benchmark has no "next release", so memory gets no headline number.

**Ablations** (the auditor minus one part; 2 bench releases, 1 fresh run each. no-generators, no-exceptions and no-verifier are planned; no-delta and no-time run only if the budget allows)

| Ablation | Removes |
|---|---|
| no-generators | the code generators; **keeps** the model-only `model_open` pass over each story. Tests whether code-generated candidates matter |
| no-exceptions | principles without their conditions and exceptions; expected to fail the negative controls |
| no-verifier | candidates are reported directly |
| no-delta | head only; tests attribution and new/pre-existing |
| no-time | stories without ordering or state; tests stale guidance and windows |

## Real product: Finablo

- **Inputs given to the auditor:** Finablo's `VISION.md` and product principles **as they existed in git before the historical release**, synthetic personas, and the two builds (the commit before and the release commit). **Not given:**
  - `CLAUDE.md`, `BUG-HISTORY.md`, `PLAN.md` and the handoff cards, all of which describe the historical bugs;
  - **any voice note recorded now**, because it is not contemporaneous knowledge.

  The exact input list and commit SHAs are recorded in the run.
- **Persona discovery is reported as its own claim.** If the auditor's normal persona generation (contract axes, thresholds in the dated inputs) produces the affected cohort, R1 is reported as **blind discovery**. If the cohort has to be supplied, it is reported as **detection given a target persona**. Both are useful; they prove different things.
- **Events:**
  - **R1, objective:** the pending-page 401(k) limit for a 61-year-old (the page showed $24,500; the server and the export said $35,750).
  - **R2, experience-level candidate:** the dashboard hero's on-pace framing vs a new pillar card's urgent directive. This counts as a finding **only if it survives a contextual adjudication**, because "ahead overall, with one urgent task" can be a legitimate combination.
- **Reporting rule:** R1 is the real-product validation. R2 appears in the video only if adjudicated as a real conflict. Otherwise we say plainly that the experience-level capability is demonstrated on Northbound.
- **Data:** synthetic profiles only; Standard-mode endpoints only.

## Reporting

`bench/results/<date>/` holds the scores for every condition, all findings from both systems (including false positives), the adjudication sheet, κ, costs and the frozen hashes. The video shows the headline numbers *as measured*, including any measure where the baseline wins.
