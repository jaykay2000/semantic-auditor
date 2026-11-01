# Brightdesk: a new user's first SRA run, on their own app and endpoint (2026-11-01)

The evidence behind beat 6 of the v8 video (`demo/video-assets/slides-src/m8-b6-your-app.html`): HOLD on the broken
release, SHIP on the fixed one, and $0.13 in model calls.

**Where it comes from.** A separate working folder, `sra-newuser-test`, where a fresh AI agent set up SRA on a small
fictional subscription app it built (Brightdesk, synthetic data, served on 127.0.0.1) and pointed SRA at its own
Muse Spark Open endpoint (model `meta-models/muse-spark-open-1026`). The folder is not part of this repository, so the
files below are an extract, and `record.json` carries the sha256 of each source file it was taken from:

| Source (under `sra-newuser-test/work/runs/`) | What was taken |
|---|---|
| `t3/review-1.1-1.0.json` | the review of the broken release 1.0 against 1.1: recommendation `hold`, the policy row that fired, its 3 issues (each `delta: new`), its own `cost_usd` |
| `t3/review-1.0-1.1.json` | the review of the fixed release 1.1 against 1.0: recommendation `ship`, the same 3 issues as `resolved` |
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

**What is not established here.** "Given only SRA's docs" is the orchestrator's account of how the new-user session
was set up; these files do not show what the agent read. No duration is claimed: the ledger's 58 rows span about 12 minutes,
but when the session started reading the docs is not recorded.

**Regenerate:** `python3 demo/video-assets/slides-src/extract_brightdesk.py [--runs <sra-newuser-test/work/runs>]`.
It refuses to write if the recommendations are not hold and ship, if the new and resolved issues differ, or if a
review's cost disagrees with its ledger rows. `tests/test_demo_brightdesk_evidence.py` checks this folder and the
frame data (`demo/video-assets/scenes-data/brightdesk.json`) without the source folder.
