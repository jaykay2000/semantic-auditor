# 5. Release audit workflow

```
sra audit --contract .sra --base <url|ref> --head <url|ref> --notes RELEASE_NOTES.md [--max-usd 5]
```

## Pipeline

```
 0 RATCHET ─► 1 PERSONAS ─► 2 CAPTURE ─► 3 EXTRACT ─► 4 GRAPH+DIFF ─► 5 CHECK ─► 6 INTENT ─► 7 VERIFY ─► 8 REPORT ─► 9 LEARN
 cheap        edge-aimed     both builds   claims       join + diff      6 families   notes→      repro,       packets,     ratchet +
 checks       set            all surfaces  JSONL                                      intended    x-model,     exit code    questions
 first                                                                                             defense
```

### 0. Ratchet checks first
Run every deterministic check in `.sra/checks/` against fresh head captures. These are past confirmed findings, so a regression of a known bug is caught here for near-zero cost.

### 1. Personas
Generate a persona set from `personas.yaml`:
- every archetype;
- **pairwise coverage** of the axes, plus **edge** values (thresholds named in the contract: an age at a statutory limit, a fare at a policy boundary, a currency with no minor unit);
- **change-aimed** personas: if the diff or release notes touch a fact or rule, add personas whose axes exercise it.

The persona count is capped (default 8 for the demo). Personas are materialized through the test-data hook, or by the explorer filling forms.

### 2. Capture
For each (build, persona, journey): replay the recorded steps and capture every surface the journey reaches. Screenshots, DOM text and boxes, emails from the sink, PDF bytes, API responses (the oracles) and chat transcripts are all stored under `runs/<id>/captures/`.
- **Journey repair:** if a recorded step fails on head (selector gone, new screen), the explorer repairs it and logs a `journey_repaired` event. New surfaces are flagged for the owner.

### 3. Extract
Each capture → claims (schema in [03-architecture.md](03-architecture.md)) by the `extractor` (Muse Spark Open), constrained by the contract: "here are the facts this surface is expected to show, plus: report anything else that is a factual claim to the user."
- DOM text is the primary input; the screenshot is the second. For PDFs and email images: page renders, with SAM 3.1 regions as a stretch.
- Values are normalized in code: currency, compact formats per the contract's formatting policy, timezones, units.

### 4. Graph and diff
- Index claims by `(build, persona, fact, surface)`.
- **Semantic diff:** for every cell, compare base and head. Values (after normalization), the presence or absence of claims, and, for qualitative claims (verdicts, recommendations, policy statements), a change in normalized meaning. Changed cells are grouped by fact and change shape, so 40 cells moving the same way read as one change.

### 5. Check: candidates
Run the finding families: CONTRADICTION, ORACLE_MISMATCH, UNSUPPORTED, PERSONA_MISFIT, SEMANTIC_REGRESSION, UNKNOWN_CLAIM. Deterministic families run on all cells. Judge families run only on changed cells, AI-generated surfaces and conditional invariants, which keeps model spend proportional to the change.

### 6. Intent matching
- The `judge` reads the release notes, PR titles/bodies and changelog, and produces an **intended-change list**: `{fact|topic, direction, scope, quote}`.
- Each SEMANTIC_REGRESSION group is classified as **INTENDED** (with the matching quote), **PARTIAL** (intended, but not every surface moved, which is itself a CONTRADICTION), or **UNEXPLAINED**.
- **The important case is a partial rollout:** "service fee raised to $15" is intended, but the PDF still says $12. That is a real bug, which a human reading the release notes would wave through.

### 7. Verify
Re-capture, cross-model re-extraction, deterministic recompute and the defense pass, as specified in the architecture doc. Output: CONFIRMED, PLAUSIBLE or REJECTED, each with reasons.

### 8. Report
For each CONFIRMED finding, an **evidence packet**:
- a one-line claim in plain English: *"Solo EUR traveller: the email total (€1,248.00) differs from checkout (€1,284.00) and from the booking record (€1,284.00)."*
- persona card; both screenshots with the claim region boxed; normalized values; oracle value and fetch;
- which builds (new in head, or pre-existing);
- reproduction: `sra repro <finding-id>` replays exactly that persona and journey;
- verifier trail: which steps ran and what each returned;
- intent: matched release-note quote, or "unexplained";
- **proposed regression check** (YAML), ready to accept.

The run report shows the **persona × surface matrix** per fact (green = agrees, red = finding, grey = not shown), the findings, the PLAUSIBLE list, the REJECTED list with reasons, and the ledger (tokens, $, wall time per stage).

Exit code: `0` no confirmed findings · `1` confirmed findings · `2` could not measure (oracle unreachable, build failed to boot, budget exhausted before coverage). A "could not measure" result must never print as a clean pass.

### 9. Learn
- `sra accept <finding-id>` writes the proposed check into `.sra/checks/` (the ratchet). Next release it runs at step 0, with no model calls.
- `sra allow <finding-id> --reason … --expires …` records an accepted divergence.
- UNKNOWN_CLAIM and new surfaces become owner questions in the next `sra contract review`.

## Ratchet check format

```yaml
# .sra/checks/CHK-0007-email-total.yaml
id: CHK-0007
from_finding: F-r_20261101-03
kind: same_value_across_surfaces
fact: trip_total
surfaces: [checkout, confirmation_email]
personas: {party: [couple, family_with_kids], currency: [EUR]}   # the shapes that broke
locators:                                                       # learned from the finding, so no model needed
  checkout: {selector: "#order-total"}
  confirmation_email: {regex: "Total paid: (?P<v>[€$¥][\\d,\\.]+)"}
```

If a locator stops matching (the UI changed), the check reports `could_not_measure` and asks the extractor to re-learn the locator. It never reports a silent pass.

## What this buys over a prompt, step by step

| Step | Without the system |
|---|---|
| 1 Personas | Tester's one default user; the bug lives in a persona nobody tried |
| 2 Capture | Only the screens someone pasted; emails and PDFs are usually missing |
| 4 Diff | No notion of "changed since last release" |
| 5 Oracle | Can see two numbers differ, cannot say which is true |
| 6 Intent | A partial rollout reads as intended |
| 7 Verify | Unknown false-positive rate |
| 9 Learn | Same cost and the same blind spots next release |
