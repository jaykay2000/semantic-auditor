# Finablo 401(k) limit bug: the source finding, picked before conversion

Written 2026-10-31, before the converter has run on it. Nothing below was changed after seeing a conversion or
judgment result.

## The record (the "developers" source of the demo loop)

The bug was filed by a Finablo developer agent (D3) as a deferred follow-up on the §73 phase's handoff card, while
the bug was still open, then fixed by commit 377d5af (PR #423), which first shipped in v707.

- Repo: finlearn. Path: `docs/handoffs/feat-73-assessment-p0.md`, line 216 at tree `a183626` (the v707 tree).
- First written in commit `1a04af01` (2026-10-02, "docs(card 73): record D3 dev block + deferred followups"), which
  is an ancestor of the fix 377d5af.
- Verbatim:

  > - "GUEST-PENDING-FIRST-MOVE-SKIPS-THE-STATUTORY-CORRECTOR: pending/failed guest first move is the raw ranked plan, never corrected; 61-year-old sees $24,500 not $35,750 [P1] (D3) — fix in flight on feat/73-p0-pending-first-move-corrector"

- Re-derive: `git -C ~/Documents/src/finlearn show a183626:docs/handoffs/feat-73-assessment-p0.md | sed -n 216p`
  (sha256 of the line in `finding.json`).

Why this one: it is the bug's own filing, written while it was open. Two other developer records describe the same
defect after the fact and were not used: the fix commit 377d5af's message and the card's "Dev — P1 fix" block
(line 294 at `a183626`). Both describe a development tree where some pages already said $35,750; on the v706
release no page could, because the 60–63 tier itself arrived in v707.

## How the record becomes the converter's input (mechanical, no new words)

The line has the card's follow-up format `CODE: description [severity] (finder) — status`. The finding fields are
cut from it by one regex (`finding.json` holds the result):

| Field | Value |
|---|---|
| claim | the CODE |
| shown | the description, verbatim |
| reproduce | the same description, verbatim |
| where, should_be, rule | empty: the record has none |
| heading (kept as evidence) | the whole line |

The record names no reproduction steps and only one fact about the user: the age, 61. So:

- **Steps** come only from what the converter's gate allows without the text: the declared prerequisite
  (`take_assessment`) and the read verb that reaches the invariant's page (`open_report`, captured while the plan
  is still being written, which is what "pending" names). If the converter cannot build a journey from this, that
  is the outcome and it is reported as is.
- **The rest of the profile** comes from declared defaults in the Finablo import spec: the harness's `target_61`
  answers (income, spending, savings, a 401(k) with an employer match), minus the age. `target_61` was built by the
  harness author to reproduce this known bug, so this journey is "built from the known bug", as beat 7's label
  says. The age is a material field: it must come from the record, not a default.

## The rule and its oracle (written now, before conversion)

The imported contract carries one age-limit rule in place of the wide contract's H1/H2: every 401(k)/403(b) limit
shown is the IRS 2026 limit for the user's own age, and it reads the same everywhere it is shown. The rule's text
carries the statutory table, so the judge checks against it rather than against its own memory:
$24,500 under 50; $32,500 at 50 or older; $35,750 at ages 60–63 (IRS IR-2025-111 and Notice 2025-67, as filed in
finlearn `docs/sources/irs-2026/`). The user's age is read from the app's own record (`current_age` in the report
API).

Model: every conversion and judgment uses `meta-models/muse-spark-open-1026` on Baseten. Nothing runs against
app.finablo.com; both releases launch locally (v706 = `10ff1e3`, v707 = `a183626`).
