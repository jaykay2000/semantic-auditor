# Semantic Release Auditor on Finablo: v707 → v731 (summary)

Finablo is a real personal-finance app in production. This summary gives counts and verdicts only: no Finablo
screenshots, page text, quotes or persona answers. Runs were made 2026-11-01, local only, with synthetic personas
and no real AI calls from the app.

## What was reviewed

| | Run 1 | Run 2 |
|---|---|---|
| Base → head | v728 (`505d5355`) → v731 (`c09505f0`) | v707 (`a183626`) → v731 (`c09505f0`) |
| Release numbers apart | 3 | 24 |
| Contract | the frozen wide contract; only its release list changed | same |
| Adapter changes | 0 | 0 |
| Harness plumbing changes | 1 (launcher entries for the new builds) | 2 (launcher points at its own builds; any build folder can launch, for the bisect) |
| Personas per release | 17: 13 blind, 4 target | same |
| Readings | 2 (one call per release; then SRA's default, 11 personas per call) | 2 (SRA's default; the first reused run 1's v731 answers from cache, the second was fresh on both releases) |
| Model | Muse Spark 1.3, Meta Model API, reader mode | same |
| Cost | $3.5733 | $2.6845 |

"Target" personas were written earlier to reproduce a known 401(k)-limit bug; a finding on one is "given a target
persona", not blind. The other 13 come from the blind contract.

## Results

| | Count | Verdict |
|---|---|---|
| Items SRA labelled **new** (v707 → v731) | 3 | 1 was pre-existing (copy reworded), so 2 truly new |
| Truly new, owner-confirmed | 2 | 1 regression (bisected to v708), 1 small; **both on target personas** |
| **Fixed** items SRA reported (v707 → v731) | 3 | all 3 real per code history and builds; all landed in v708. 2 on target personas, 1 on a blind persona. Not owner-reviewed. |
| **Pre-existing** items raised | 2 | owner: 1 real (blind persona), 1 unsure |
| v728 → v731 new / fixed | 0 / 0 | correct: the captured text was identical in both releases |

Across both runs SRA raised 4 distinct issues in v731. The owner confirmed 3 as real (one of them small) and was
unsure about 1. None was ruled a false alarm; one delta label ("new") was wrong.

## Limits

* **Each reading alone missed items the other caught.** One reading of v707 → v731 missed the small issue and one
  fix; the other missed a pre-existing issue. In run 1, the single-call reading found nothing; the default reading
  found all 4 issues.
* **Reworded copy breaks the delta labels.** It produced 1 false "new" and left 4 fixed items as "unconfirmed"; each
  was corrected by hand against the base release's captures.
* **2 of the 3 confirmed issues come from target personas**, not blind ones (the regression and the small one).
* **v728 → v731 could not show new or fixed issues:** for all 17 personas, every captured word was the same in both
  releases apart from generated names, codes and IDs.
* Confidence on every reader issue is capped at medium: no replay, second model or defense runs in reader mode.

## Machine-readable counts

```json
{
  "app": "Finablo",
  "base": "v707",
  "head": "v731",
  "base_sha": "a183626",
  "head_sha": "c09505f0",
  "releases_apart": 24,
  "personas_per_release": 17,
  "blind_personas": 13,
  "target_personas": 4,
  "readings": 2,
  "model": "muse-spark-1.3",
  "new_labelled_by_sra": 3,
  "new_after_check": 2,
  "regressions_confirmed": 1,
  "regression_introduced": "v708",
  "small_confirmed": 1,
  "new_confirmed_on_target_personas": 2,
  "fixes_reported": 3,
  "fixes_confirmed": 3,
  "fixes_landed": "v708",
  "pre_existing_raised": 2,
  "pre_existing_confirmed_real": 1,
  "pre_existing_unsure": 1,
  "false_new_labels": 1,
  "fixed_left_unconfirmed": 4,
  "adapter_changes": 0,
  "cost_usd_this_run": 2.6845,
  "cost_usd_both_runs": 6.2577,
  "short_window": {"base": "v728", "head": "v731", "releases_apart": 3, "new": 0, "fixed": 0,
                   "identical_text": true, "cost_usd": 3.5733}
}
```

## How each number was checked

* **SHAs and versions:** `git log` in the Finablo repo. v707 = `a183626` (its as-shipped stamp follows it). v708 is
  the merge immediately followed by the "v708 as-shipped stamp" commit. v728 = `505d5355` (the `release/v728`
  merge). v731 = `c09505f0` per the owner's release record (not re-measured against the host).
  `releases_apart` = 731 − 707 = 24 release numbers (37 first-parent merges between the two commits; some releases
  may carry no code change).
* **Persona counts:** the `role` field in the contract's persona file (17 personas; 4 `target`).
* **New / pre-existing:** each issue's quoted text was searched for in the base release's captures; an item counts
  as pre-existing when the same content was shown there, even if reworded.
* **Regression date:** a bisect with real builds of each candidate merge (v707 good; v708 and every later candidate
  bad; the only merges between v707 and v708 are docs and CI).
* **Small issue:** the same per-merge captures show its two halves arriving at different merges: one in v708, the
  other after v711 and before v727 (git records no release numbers between v711 and v727).
* **Fixes:** each fixed figure was checked as wrong in v707's captures and right in v731's, then in a build of the
  v708 merge (already right), plus the source history (`git log -S`) for the code that changed.
* **Identical text (v728 → v731):** every captured element compared per persona and per surface.
* **Costs:** the harness's model-call ledger, fresh rows only (cached rows cost $0): run 1 = 6 fresh calls, $3.5733
  ($1.7321 + $1.8411); run 2 = 6 fresh + 2 cached calls, $2.6845 ($0.8811 + $1.8033); total $6.2577 over 12 fresh
  calls. Captures and bisect builds made no model calls.
* **Owner verdicts:** given by the app's owner on 2026-11-01. The fixes were checked by code history and builds,
  not by the owner.
