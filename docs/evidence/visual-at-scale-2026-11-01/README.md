# Visual confirmation on every eligible issue, with a planted wrong value for each (2026-11-01)

**Result: 7 of 7 real issues `confirmed`; 7 of 7 mutated controls `contradicted`. 14 model calls, $0.0273.**
The sample is small: two reviews hold only 7 issues that can be sent, so this shows the check works on these pages,
not a rate.

| App and review | Issues | Eligible | Sent | Real: confirmed / contradicted / unreadable | Controls sent | Controls: confirmed / contradicted / unreadable |
|---|---|---|---|---|---|---|
| Northbound 2.3 → 2.4 (`runs/e2e-2/review-2.3-2.4.json`) | 9 | 9 (basis `verifier`) | 6 | 6 / 0 / 0 | 6 | 0 / 6 / 0 |
| Spree beta2 → beta3 (`spree-scale-2t` reader review) | 1 | 1 (basis `evidence_linked`) | 1 | 1 / 0 / 0 | 1 | 0 / 1 / 0 |
| **Total** | 10 | 10 | 7 | **7 / 0 / 0** | 7 | **0 / 7 / 0** |

- **Not sent: 3 Northbound issues.** Every event they cite is an email, chat or push message, not a web page, so there
  is no screenshot. `semaudit visual` records them as `unreadable` ("no cited event has a web capture") without a
  model call. They are counted as eligible and not sent; they are not in the 7.
- **Eligible** means `visual.basis_of` accepts the issue: verification `verified` (basis `verifier`), or not failed
  and its quote matched to the capture (basis `evidence_linked`). All 10 issues in the two reviews qualify.
- **The control.** For each sent issue, the same crop (sha256 equal to the real call's, checked for all 7) and the
  same seed, with the claimed value changed. `probe/make_controls.py` picks the change by a fixed rule, written before
  any call of this run: the first figure in the quote is replaced by a different figure of the same kind (same
  currency sign, or both plain numbers) that appears in another message on the same page. All 7 changes came from the
  same page; the "+1" fallback was not needed. The changes (`controls-*.json`):

  | Issue | Real claim | Control claim |
  |---|---|---|
  | 3 Northbound "Departing soon" banners (P2 price-watch conflict, U1, P1-a) | "only 2 seats left …" | "only 1 seats left …" |
  | Northbound P1-bare-c | "Only 2 seats left. Book now." | "Only 1 seats left. Book now." |
  | Northbound U2 (couple) | "2 seats left …" | "14 seats left …" |
  | Northbound P2 unexplained trade-off (family) | "9 seats left …" | "4 seats left …" |
  | Spree tax line | $43.19 | $39.99 (the subtotal on the same page) |

  Most controls change one figure inside a 15 to 25 word sentence. The model's `reads` was the real on-screen text
  in all 14 calls, and its own `same_as_text` flag agreed with SRA's text comparison in all 14 (a disagreement would
  have made the call `unreadable`).
- **The real issues:** `confirmed` needs the model's `reads` to contain the whole quote and its `same_as_text` to be
  true. All 6 Northbound quotes are full sentences, and all 6 were read back word for word.

## How it was run and checked

- Code: SRA at `ae440ab`, `semaudit visual` unchanged (no prompt or code change in this experiment). Model
  `meta-models/muse-spark-open-1026` on Baseten, reasoning effort low, seed 1, from a fresh root (empty cache;
  `cached: false` on all 14 ledger rows). Root `semaudit.toml`:
  `[roles.vision] provider = "baseten", model = "meta-models/muse-spark-open-1026", reasoning_effort = "low"`.
- Real issues: `semaudit visual <review> --out real.visual.json --max-usd 0.3`, once per review. It printed
  `confirmed 6, contradicted 0, unreadable 3, not eligible 0` (Northbound) and `confirmed 1, … unreadable 0` (Spree).
- Controls: `python probe/make_controls.py <review> controls-<app>.json`, then
  `python probe/run_controls.py <review> controls-<app>.json <out> <crops> --max-usd 0.3`. It calls the same
  `visual.check_issue` as the CLI, on a copy of the issue whose quote is the control claim.
- Each written review copy, with `visual` removed, equals its review JSON (compared after sorting keys), for both
  reviews. The reviews themselves were only read.
- Cost: sum of `cost_usd` over the 14 rows of `ledger.jsonl` = $0.027277 (real $0.013503, controls $0.013775). No key
  is in any file here (the ledger has none by design; checked with grep).

## Files

- `results.json`: per issue, the real call's `visual` record (basis, event, crop box, sent sha256, model reads,
  result, reason, cost) and the control's claim and `visual` record.
- `crops/`: the 7 PNGs that were sent (the controls sent the same bytes).
- `controls-northbound.json`, `controls-spree.json`: the control claims, made before the calls.
- `ledger.jsonl`: the 14 ledger rows. `probe/`: the two scripts.

## Not shown by this

- A rate. 7 issues, 3 of them the same banner text on three personas' pages (different screenshots, different crops); one seed.
- Hard cases: small or low-contrast text, long tables, values that need scrolling, pages where the outlined element
  is covered. None of the 7 crops is hard to read.
- Emails, PDFs and chat: the check reads web screenshots only.
