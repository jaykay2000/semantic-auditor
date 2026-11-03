# Brightdesk: a new user's first SRA run, on their own app and endpoint (2026-11-01)

HOLD on the broken release, SHIP on the fixed one, and $0.13 in model calls. (This was the evidence behind an earlier
cut of the demo video; the video's files are not in this repository.)

**Where it comes from.** A separate working folder, `sra-newuser-test`, where a fresh AI agent set up SRA on a small
fictional subscription app it built (Brightdesk, synthetic data, served on 127.0.0.1) and pointed SRA at its own
Muse Spark Open endpoint (model `meta-models/muse-spark-open-1026`). The folder is not part of this repository, so the
files below are an extract, and `record.json` carries the sha256 of each source file it was taken from:

| Source (under `sra-newuser-test/work/runs/`) | What was taken |
|---|---|
| `t3/review-1.1-1.0.json` | the review of the broken release 1.0 against 1.1: recommendation `hold`, the policy row that fired, its 3 issues (each `delta: new`), its own `cost_usd` |
| `t3/review-1.0-1.1.json` | the review of the fixed release 1.1 against 1.0: recommendation `ship`, the same 3 issues as `resolved` |
| `my-app/adapter.py` (beside `work/`) | its size (49 lines) and the four verbs it defines, for beat 6 of v9; `record.json` keeps its sha256 |
| `ledger.jsonl` | every model call of the whole session (58 rows): the 15 billed (uncached) rows go to `ledger-billed.jsonl` with only `ts`, `tag`, `role`, `model`, `priced`, `cached`, `cost_usd`; `record.json` keeps per-tag totals for all 58 |

Absolute paths, the contract folder, cache digests and token details were left out. Nothing key-like was in the
fields taken.

**How $0.1323 is recomputed.** Sum `cost_usd` over the rows of `ledger-billed.jsonl` (all `cached: false`):

```bash
python3 -c "import json; r=[json.loads(l) for l in open('demo/evidence/newuser-brightdesk-2026-11-01/ledger-billed.jsonl')]; print(len(r), round(sum(x['cost_usd'] for x in r), 6))"
# 15 0.132284
```

A cached call is replayed from SRA's cache and bills nothing, so the 43 cached rows are not in the sum. The total covers
the session start to finish: the agent's three attempts (`t1`, `t2`, `t3`) and their re-runs. The final pair alone
(`t3`) billed $0.0770 in 7 calls, which matches the hold review's own `cost_usd` of 0.077 (the ship review was fully
cached, `cost_usd` 0.0). The frame rounds the total to $0.13.

**The adapter.** The reviews' manifests record the contract files' hashes but not the adapter's, so the link between
`adapter.py` and the `t3` reviews is by time only: the file was last changed at 08:53:45, before both `t3` reviews were
written (08:58:28). The broken release's prices on the frame (`$12` on pricing and in the inbox, `$15` at checkout) are
the hold review's own issue text (`plan_price 12 on pricing; 15 on checkout; …`); the app's docstring says the same
($15/month at checkout, $12/month elsewhere).

**What is not established here.** "Given only SRA's docs" is the orchestrator's account of how the new-user session
was set up; these files do not show what the agent read. No duration is claimed: the ledger's 58 rows span about 12 minutes,
but when the session started reading the docs is not recorded.

**Checks.** The extractor that wrote this folder lived with the video files and is not in this repository.
`tests/test_brightdesk_evidence.py` checks what the folder itself claims: the billed rows add up to the record, every
source carries a sha256, and the two reviews are hold then ship.
