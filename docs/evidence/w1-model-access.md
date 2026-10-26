# W1: Meta Model API access, verified by calls (2026-10-26)

Run: `python3 scripts/w1_smoke.py` (writes `runs/w1/report.json`, not committed). Total spend: **$0.0614**.

| Check | Result |
|---|---|
| Models available to this key | muse-image-1.0, muse-spark-1.1, muse-spark-1.2, muse-spark-1.2-contributor, muse-spark-1.3, muse-spark-1.3-contributor, muse-voice-transcribe-1.0, muse-wonder-1.0, sam-3.1 |
| Text, `reasoning_effort=minimal` (muse-spark-1.3) | ok; 15 in / 24 out tokens (14 reasoning) |
| Strict JSON-schema extraction, 5 canonical copy keys, `low` | all match expected; 5025 output tokens; $0.02384; 27.26 s |
| Same, `medium` | all match expected; 7724 output tokens; $0.03531; 37.77 s |
| Image input (`image_url` data URL) | ok; transcribed "2 seats left at this fare. Lock it for 48 h for EUR9 total." |
| Tool calling | ok; called `get_inventory` with `{"fare_id":"LISBER-07"}` |
| Second model (muse-spark-1.2) | ok |

**Findings that change the plan**
- Reasoning tokens dominate cost: about 1,000 output tokens per short message even at `low`. Extraction therefore batches all of a story's messages into **one call**.
- `low` effort was sufficient for the 5 canonical copy keys, so the extractor defaults to `low` and the interpreter to `medium` until W1b says otherwise.
- Pricing is assumed to be $1.25 / $4.25 per million tokens (Standard), as published in the launch blog; the pricing page URL returned 404, so the ledger records Contributor-mode calls as *unpriced* rather than $0.
- Open-weights (Muse Spark Open) is not tested yet: it needs Modal or Baseten credits. Until then the cross-checker uses `muse-spark-1.2`, and confidence records "reduced independence".
- Not tested yet: Muse Voice Transcribe (no audio sample; W12) and PDF input.
