# Input ablation of B-judge-1: plan, written before the run (2026-10-28)

**Status: committed BEFORE any variant runs on sealed data.** The prompt and code hashes are recorded in the
commit that adds this file. The variants are run ONCE, and every result is reported, whatever it is.

## Why this exists

The frozen E2 comparison (FROZEN-CONDITIONS.md) gave the one-call baseline the auditor's own work as input:
- the auditor's captures (its scenario runner drove the app as each persona);
- each message tagged with feature, surface, channel, component, message key and whether the user started it;
- the oracle readings (the true state at every step);
- the owner's contract as structured data;
- the auditor's judging method, written out in `prompts/_common.md`.

The sealed run measured B-judge-1 at 15 of 15 found with 0 false alarms. That result shows the auditor's multi-step
judging adds nothing **on top of those inputs**. It does not show what those inputs are worth. This ablation
measures that, by removing them one at a time from the SAME call.

**This was added after the first sealed result was seen.** It changes nothing in the auditor and adds no new
auditor condition. It only removes inputs from a baseline that is already frozen. It is reported as a follow-up
analysis, separate from the frozen E2 result, and never in place of it.

## Variants (cumulative: each removes one more thing)

| id | removes | what the call still gets |
|---|---|---|
| V0 | nothing (= frozen B-judge-1, already measured, NOT re-run) | everything above |
| V1 `no-method` | the judging method (the "How to judge" section of `_common.md`) | the task and output format, structured contract, oracle readings, tagged captures |
| V2 `no-oracle` | also: oracle readings and the story's static truth | the task and format, structured contract, tagged captures, persona context |
| V3 `plain-rules` | also: the structured contract | each rule's id, title, severity and owner-written text, plus a plain sentence for each exception, generated mechanically from its conditions, scope and expiry (`plain_exception` in `semaudit/bench/inputs.py`); the vocabulary (feature ids, decision ids with their actions, surface ids) |

What NO variant removes:
- **The captures themselves, and their feature/surface tags.** Without the auditor's scenario runner there is no
  transcript to judge. That is E1 (coverage, B-explore), a separate condition.
- **The output format.** It is needed so every variant is scored by the same matcher.

Same model, role and settings as B-judge-1: the `interpreter` role, no effort override, one call per release,
`fresh=True`. Prompt: `prompts/inputs/judge_bare.md`, identical for V1–V3. It is the B-judge-1 task statement and
the "What to report" section of `_common.md`, copied verbatim. Only the payload differs between variants.

## Inputs, scoring, reporting

- Captures: the sealed run's own `semaudit-full r1` captures (`<results>/runs/<rel>-r1/episodes/<rel>`), the same
  ones V0 judged. Releases: bench-01, bench-02, bench-03.
- Scored with the frozen matcher (`semaudit.bench.match.score`) against the same sealed normalized truth,
  pre-adjudication, exactly like V0. Evidence support uses r1's evidence index.
- Reported for each variant and release, and totalled: tp, fp, fn, Wilson 95% intervals, negative-control hits,
  label accuracy, evidence support, cost. Counts only reach the building session.

## Hypothesis, stated so it can fail

H1: recall or precision falls as inputs are removed, most at V2 (no oracle readings) for objective rules, and at
V1/V3 for conditional and coherence rules.

If V3 still scores like V0, then the auditor's structured evidence and method are NOT what makes one call
accurate. The demo claim *"the auditor's evidence is what makes the judgment accurate"* is then dropped, and we
report that.

## What must be unchanged since the frozen run (5e32f9a)

The date/time fix (06f72a1) changed auditor files after the sealed run. None of them is used here. Before running,
the custodian confirms this prints nothing:

    git diff --stat 5e32f9a HEAD -- src/semaudit/bench/judge.py src/semaudit/bench/match.py \
        src/semaudit/bench/findings.py src/semaudit/story src/semaudit/contract src/semaudit/models \
        bench/conditions/prompts/_common.md bench/conditions/prompts/judge_one.md \
        bench/conditions/findings.schema.json bench/conditions/truth.schema.json

It also records the sha256 of `prompts/inputs/judge_bare.md` and `src/semaudit/bench/inputs.py` in its report.

## Budget

Cap `--max-usd 1.00` for all 9 calls. The estimate is ~$0.55, from B-judge-1's measured $0.056–0.072 per release.
One run, no retries. A variant that runs out of budget is recorded as not measured.
