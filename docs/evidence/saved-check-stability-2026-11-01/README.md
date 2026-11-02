# Saved-check stability: 5 more runs of C1-04 and C1-04-v1 from storage (2026-11-01)

**Batch 2 (same day, after restarting the two storefront dev servers): 8 of 10 check runs `fix_confirmed`, 0 replay
timeouts, 2 garbled record values, no wrong outcome, $2.755. See [batch-2/README.md](batch-2/README.md).** Both
batches together: 13 of 20 check runs confirmed the fix, none gave a wrong outcome; the 7 misses are 4 garbled record
values and 3 replay timeouts (all 3 in batch 1, on dev servers that had slowed down after nearly 2 days). This page
below is batch 1.

**Result: C1-04 `fix_confirmed` in 3 of 5 runs, C1-04-v1 in 2 of 5. All-in cost $1.646.** Of the 5 check runs that
did not confirm a fix, 2 failed in the judging (one judgment wrote a garbled record value even after its re-asks, so
its evidence was only partly verified) and 3 failed in the browser replay (a page load or click timed out on the
local store). No run gave a wrong answer: when the replay and evidence held, the outcome was always FAIL on beta2 and PASS
on beta3.

Measured: a full `run-saved` from storage against the live local Spree stores (beta2 = `current`, beta3 =
`candidate`), the same command as the owner's run `ic-owner-rec-1`, five times in a row, with nothing changed between
runs.

| Run | Check | beta2 replay | beta2 votes | beta2 evidence | beta3 replay | beta3 votes | beta3 evidence | Outcome | Run cost |
|---|---|---|---|---|---|---|---|---|---|
| ic-stab-1 | C1-04 | ok | fail 3 | verified | ok | pass 3 | verified | **fix_confirmed** | $0.4518 |
| | C1-04-v1 | ok | fail 3 | verified | ok | pass 3 | verified | **fix_confirmed** | |
| ic-stab-2 | C1-04 | ok | fail 3 | verified | ok | pass 3 | verified | **fix_confirmed** | $0.4262 |
| | C1-04-v1 | ok | fail 3 | verified | ok | pass 3 | partially verified | not_confirmed (garbled record value) | |
| ic-stab-3 | C1-04 | ok | fail 3 | verified | ok | pass 3 | partially verified | not_confirmed (garbled record value) | $0.3549 |
| | C1-04-v1 | ok | fail 3 | verified | ok | pass 3 | verified | **fix_confirmed** | |
| ic-stab-4 | C1-04 | **timed out** | none | unverified | ok | pass 3 | verified | not_confirmed (beta2 replay failed) | $0.2446 |
| | C1-04-v1 | ok | fail 2, pass 1 | verified | **timed out** | none | unverified | not_confirmed (beta3 replay failed) | |
| ic-stab-5 | C1-04 | ok | fail 3 | verified | ok | pass 3 | verified | **fix_confirmed** | $0.1686 |
| | C1-04-v1 | **timed out** | none | unverified | **timed out** | none | unverified | not_confirmed (both replays failed) | |

For comparison, the owner's run `ic-owner-rec-1` (same checks, same approvals): C1-04 `fix_confirmed` (beta2 fail 2 /
not measurable 1), C1-04-v1 `not_confirmed` (garbled record value), $0.446.

## The two ways a run failed to confirm

- **Garbled record value (runs 2 and 3, and the owner's run).** A judgment must quote the order record's numbers. One
  of the three judgments wrote `')] }'` for a price of 49.99 (run 2, seed 2003) or `'},{'` for an item total of 179.98
  (run 3, seed 2004). SRA re-asks a judgment with garbled values up to 3 times with a new seed; these were still
  garbled on the last try, so SRA refused the citation, the evidence was `partially_verified`, and a PASS without
  verified evidence counts as not measurable. All three votes were PASS in both cases. This is the known weakness
  recorded since Run 2 (see `../imported-checks/README.md`), unchanged here.
- **Replay timeout (runs 4 and 5).** The browser could not finish the journey: a product page did not load within 60
  s (run 4, beta2), "Add to Cart" was not clickable within 30 s (runs 4 and 5, beta3; the step-2 screenshot of run 5
  shows the button on the page), and the order-placed page did not load within 60 s (run 5, beta2). SRA then records
  the release as not measurable rather than guess. The cause was not established beyond these timeout messages. The
  stores run as Next.js dev servers, started before this session; right after run 5 the beta2 product page took 8.8 s
  to render, and the machine's load average was about 5 to 6. Runs 1 to 3 took 7 to 8 minutes each, run 4 took 16.
- **One wrong vote, outvoted (run 4, C1-04-v1 on beta2).** One of three judgments said PASS, reading the -$15 free
  shipping promotion as already netted out of the shipping line. The other two said FAIL, so the majority was FAIL
  (confidence 2/3).

## How it was run and checked

- Harness: a new git worktree of `spree-semaudit` at `publish-prep` (`a82d0aa`), with the main checkout's ignored
  setup files copied in unchanged (the two `run-v6.0.0.*` compose folders, the admin login, the read-only secret keys,
  `import-root/.env`, and the storefront PID and marker files, so the already running stores and storefronts were
  reused, not restarted). The main checkout and its uncommitted files were not touched. SRA: a copy of commit
  `cb51ffd` (`SRA_DIR`). Its differences from the owner run's SRA (`1a11982`) are path-containment and key-redaction
  hardening plus the opt-in `semaudit visual`; no prompt, schema, parsing or judging code differs.
- Command per run (`run_c.sh`): `python3 imported_checks.py run-saved --base current --head candidate --run ic-stab-N
  --max-usd 0.8`. Before each run, `contract-imported/dispositions.yaml` was restored to the `publish-prep` version,
  so every run started from the same stored state. Each run's `loaded_from_storage` digests are identical: approvals
  `b95ca35159dbcb55`, C1-04 `d3408fbc3d2146e2`, C1-04-v1 `df192ed9b46a8907`, dispositions `174022f22be2f7b4`. The
  approvals and check digests equal the owner run's.
- Cost: the sum of the result-level `cost_usd` over both checks and both releases in each `saved-checks.json`
  (`summarize.py`, output `summary.json`), the same measure as the owner run's $0.446. It includes discarded replies
  (runaways and garbled re-asks). Runs 4 and 5 cost less because failed replays were not judged. Total $1.646138, under
  the $4 cap.
- Model: `meta-models/muse-spark-open-1026` on Baseten, 3 judgments per release, judge role capped at 6,000 tokens
  (as `import-root/semaudit.toml` sets).

## Files

`ic-stab-N-saved-checks.json` (each run's full result: every judgment, citation, evidence check and cost),
`ic-stab-N-transcript.txt` (what the command printed), `summary.json` and `summarize.py`, `run_c.sh` (the driver) and
`driver.log`. The captures (screenshots, page text, emails) stay outside the repo, as for the owner's run.
