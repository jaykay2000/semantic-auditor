# Batch 2: 5 more runs after restarting the two storefront dev servers (2026-11-01)

**Result: C1-04 `fix_confirmed` in 4 of 5 runs, C1-04-v1 in 4 of 5 (8 of 10 check runs). All 20 browser replays
succeeded. The 2 misses are both garbled record values, in the same run. No wrong outcome. $2.755.**

| Run | Check | beta2 votes | beta2 evidence | beta3 votes | beta3 evidence | Outcome | Run cost |
|---|---|---|---|---|---|---|---|
| ic-stab-6 | C1-04 | fail 3 | verified | pass 3 | verified | **fix_confirmed** | $0.6456 |
| | C1-04-v1 | fail 3 | verified | pass 3 | verified | **fix_confirmed** | |
| ic-stab-7 | C1-04 | fail 2, pass 1 | verified | pass 3 | partially verified | not_confirmed (garbled record value) | $0.6269 |
| | C1-04-v1 | fail 3 | verified | pass 3 | partially verified | not_confirmed (garbled record value) | |
| ic-stab-8 | C1-04 | fail 3 | verified | pass 3 | verified | **fix_confirmed** | $0.4493 |
| | C1-04-v1 | fail 3 | verified | pass 3 | verified | **fix_confirmed** | |
| ic-stab-9 | C1-04 | fail 3 | verified | pass 3 | verified | **fix_confirmed** | $0.5534 |
| | C1-04-v1 | fail 3 | verified | pass 3 | verified | **fix_confirmed** | |
| ic-stab-10 | C1-04 | fail 3 | verified | pass 3 | verified | **fix_confirmed** | $0.4797 |
| | C1-04-v1 | fail 3 | verified | pass 3 | verified | **fix_confirmed** | |

**Next to batch 1 (same command, same code, same approvals):**

| | Batch 1 (`../`) | Batch 2 (this folder) |
|---|---|---|
| Storefront dev servers | running 1 day 20 h; product page 6 to 9 s | restarted just before; product page 0.2 to 0.3 s |
| `fix_confirmed` | 5 of 10 check runs | 8 of 10 |
| Missed: replay timeout | 3 | 0 |
| Missed: garbled record value | 2 | 2 |
| Wrong outcome | 0 | 0 |
| Cost | $1.646 | $2.755 |

So the replay timeouts in batch 1 were the slowed dev servers, not the check: with fresh servers every replay
finished. The garbled record values are the check's own weakness and did not change: in run 7 one of the three
readings on beta3 wrote, on its last re-ask, `'$179.98 converted to 179.98 copied as 179.98'` (C1-04) and an empty
string (C1-04-v1) for the order's item total, so SRA refused those citations and the PASS counted as not
measurable. Run 7 also had one wrong PASS vote on beta2 (C1-04), outvoted 2 to 1.

## How it was run and checked

- **Storefronts:** both stopped and started again through the main harness checkout's own `launch_spree`
  (`stop_storefront`, then `up`: the same `start.sh` path; new PIDs, so its PID files stay right). The main
  checkout's git status was the same before and after. The backend Docker stacks were not touched. Before the first
  run, each journey page was fetched twice (first request after a restart compiles the page). The restarted
  storefronts were left running, as the old ones had been.
- **Runs:** a fresh `publish-prep` (`a82d0aa`) worktree with the main checkout's setup files copied in, and the same
  frozen SRA copy (`cb51ffd`) as batch 1. Command per run, as in batch 1: `run-saved --base current --head candidate
  --run ic-stab-N --max-usd 0.8`, with `contract-imported/dispositions.yaml` restored before each run.
  `run_c2.sh` ran 6 to 8; it was stopped by hand before run 9 because the batch's $2.50 cap would have left run 9
  only about $0.60 of cap. The orchestrator raised the batch cap to $3.30 and `run_c2b.sh` ran 9 and 10, each at
  $0.80 like every other run (`driver.log`). No run reached its cap (the highest was $0.646).
- **Cost:** sum of the result-level `cost_usd` in each `saved-checks.json` (`../summarize.py`, output
  `summary.json`), the same measure as batch 1.
- Every run's `loaded_from_storage` digests equal batch 1's.
