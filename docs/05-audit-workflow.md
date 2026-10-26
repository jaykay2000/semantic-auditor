# 5. Release review workflow

```
semaudit review --contract .semaudit --base <release|url> --head <release|url> --notes RELEASE_NOTES.md [--max-usd 5]
```

The output is a **release review**: the stories of each persona, the issues ranked for the owner, the evidence for each, and a recommendation (Ship / Ship with notes / Needs owner review / Hold) that the owner decides on. Layer names (L0–L7) refer to [03-architecture.md](03-architecture.md).

## Pipeline

```
1 PERSONAS ─► 2 CAPTURE ─► 3 DETERMINISTIC ─► 4 EXTRACT ─► 5 STORIES ─► 6 RELATE ─► 7 ISSUES ─► 8 VERIFY ─► 9 RECOMMEND ─► 10 OWNER
  + state      episodes,     checks, facts      messages,    ordered      generate    delta,       repro,       policy,        dispositions
               both          vs oracles,        directives,  events,      candidates, severity,    evidence,    report,        → memory
               releases      data conditions    claims       aligned      interpret   confidence   x-model,     Release Story
                             (no model)         (model)      base↔head    (model)                  defense
```

### 1. Personas
- Use every contract archetype, plus generated personas: pairwise coverage of the axes, edge values (thresholds named in principles and exceptions, such as departure at 71 h vs 73 h), and change-aimed personas whose axes exercise the features named in the release notes.
- Default cap: 8. Each persona carries **state** into its scenarios.

### 2. Capture (first, always)
- Run every applicable **scenario** for every persona on **both** releases. Steps advance the simulated clock through the clock hook, so time-triggered emails and pushes are captured where they happen in the story.
- Each step stores its captures and a **state snapshot** read from the oracles.
- If a step breaks, the explorer repairs it and logs a `step_repaired` event. A surface that cannot be reached is recorded as **not measured**, never treated as absent.

### 3. Deterministic pass (no model calls)
- Run the existing locator-based checks in `.semaudit/checks/` against the fresh captures. These checks already know where their values are, so they need no extraction.
- Evaluate the **state-only data conditions** of every rule and exception (departure within 72 h? booked? within the free-change window?).
- This step is cheap and catches known regressions before any model spend.

### 4. Extract (model, cached)
- From each capture, extract messages (with feature attribution), directives (decision, action, urgency, validity, rationale, explains-tradeoff) and claims. Muse Spark Open does this, constrained to the contract vocabulary.
- Unchanged captures hit the cache, so they cost nothing.
- Then, in code: compare the newly extracted claims with oracles. Each claim becomes `supported`, `contradicted` or `unverifiable`, and the claim-dependent data conditions are evaluated (does the seat count match inventory?). Only `contradicted` claims can become false-claim issues; `unverifiable` ones become owner questions.
- Compute each directive's validity window (text deadline, action preconditions, feature default lifetime, supersession); an end that cannot be determined is `unknown`, never "forever".

### 5. Stories
- Assemble the time-ordered events (messages, user actions, state changes) for each (release, persona, scenario).
- Align the base and head stories by stable `event_key`. Unmatched events are explicit (`added` / `removed`), and fuzzy alignments are marked.

### 6. Relate
- The generators (code) propose candidate relations: competing directives (across features), stale guidance, rule applicability, attention load, fact divergence, false claim.
- One `model_open` pass per story looks for anything the generators missed.
- Rules are evaluated **by kind and independently**: universal (no exceptions) → conditional (exceptions: data conditions in code, soft conditions judged; all must be met, inside scope) → coherence (an incompatible pair must be reconciled; a material-tradeoff pair must be explained) → load (code counts; user-initiated conversations excluded).
- Muse Spark labels each candidate: `conflict` · `unexplained_tradeoff` · `explained_tradeoff` · `exception_applies` · `compatible` / `duplicate_ok`.
- **An exception to one rule never excuses another.** Every rule's evaluation is recorded, including the passes, so the story can show *why* a persona was not raised.

### 7. Issues
- Relations labelled `conflict` or `unexplained_tradeoff` become **issues**. The same relation seen across several personas is grouped into one issue with its reach.
- **Delta:** each issue is marked *new*, *changed*, *pre_existing* or *resolved*, with the features that changed.
- **Severity** and **confidence** are computed independently (factors in the architecture doc).

### 8. Verify
For each issue, the applicable steps are run and recorded:
1. `reproduced`: the episode is re-run, and the same events appear.
2. `evidence_linked`: every cited event resolves to a capture, a locator and an exact quote that matches the DOM text.
3. `cross_model`: the *other* model re-extracts the directives and re-labels the relation.
4. `defended`: a defense pass tries to explain the issue away using the principles, exceptions, release notes and tradeoff criteria.
5. `oracle_checked` (fact kinds only).

Each step yields a **verification status** (`unverified` → `partially_verified` → `verified`, or `failed`: `not_reproducible` or `disputed`). The steps also feed confidence. Failed candidates go to the **not raised** list with their reasons. They are shown, not hidden.

*Verified* means the evidence reproduced and resolves exactly, and an independent model re-reached the judgment and could not explain it away. It does not make a subjective product judgment objectively true; that is the owner's decision.

### 9. Recommend and report
- `release_policy.yaml` turns (severity, confidence, verification) into the recommendation. This is a rule, not a model opinion.
- Outputs:
  - `report.html` (the Release Story view and the issue list);
  - `issues/*.json`;
  - `not_raised.jsonl` (candidates cleared by a rule, with the reason, plus candidates whose verification failed);
  - `ledger.json` (tokens, $, time per stage);
  - `pr-summary.md`.
- Exit code: `0` Ship · `1` an owner decision is needed · `2` could not measure (a release would not boot, an oracle was unreachable, the budget ran out before coverage). Exit `2` never reads as a pass.

### 10. Owner decisions → memory
| Command | Effect |
|---|---|
| `semaudit decide <issue> fix` | the next review must show it `resolved`, or it is re-raised as `still_open` |
| `semaudit decide <issue> accept --scope … --expires …` | creates a **scoped exception**: conditions, features, surfaces, personas, expiry. Never broader than the issue's own events |
| `semaudit decide <issue> not-an-issue --reason …` | that exact relation signature is not re-raised; a variant is |
| `semaudit decide <issue> rule` | only when the issue is expressible (fact equality, presence/absence under a condition, a precondition). Writes a deterministic check to `.semaudit/checks/` |
| `semaudit decide <issue> expect "…"` | records an **approved semantic expectation**, evaluated by the relation layer every release. Not claimed to be deterministic |
| `semaudit repro <issue>` | replays exactly that persona, scenario and release, and re-runs verification |

Questions for the owner (new vocabulary, new surfaces, unknown claims, unknown exception conditions) appear in the next `semaudit contract review`.

## The legitimate-difference checklist (applied before anything is raised)

A candidate is **not** an issue when any of these holds, and the report says which one:
- a scoped exception applies, and every one of its conditions was evaluated as *met*. This clears only the rule the exception belongs to, never a universal or coherence rule;
- a message that `reconciles` both directives is shown while both are live and before the user decides (`explained_tradeoff`), which satisfies the coherence rule;
- the messages are never live at the same time, because their validity windows do not overlap in this story;
- the difference follows from the persona's own facts (another party size, another fare);
- it is a transactional repetition (`duplicate_ok`);
- a post-purchase suggestion is still actionable (precondition true, with a deadline).
