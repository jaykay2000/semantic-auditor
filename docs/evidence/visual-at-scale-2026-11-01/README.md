# Visual confirmation on every eligible issue, with a planted wrong value for each (2026-11-01)

**Combined result (first run + owner-approved extension, three apps): 65 issues sent, which are 31 distinct crops.
Planted wrong values: 58 of 58 `contradicted` (29 distinct crop-and-claim pairs). Real issues: 58 `confirmed`,
2 `contradicted`, 5 `unreadable` (by distinct crop: 26 / 2 / 3). $0.1538 billed.** Details of the extension are in
[its section below](#extension-three-apps-31-distinct-crops); this first section is the first run.

## First run: the two named reviews

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

## Extension: three apps, 31 distinct crops

Approved by the owner on 2026-11-01: the same check on every eligible issue of more reviews, with the control rule
unchanged (`probe/make_controls.py`, byte-identical to its first commit; checked with `git diff cb51ffd`), seed 1, no
prompt or code change, one $0.50 cap over all calls (`probe/run_extension.py`). Reviews (`extension/reviews.txt`; two run folders are listed under neutral labels, `screen-11-session-agent-a` and `screen-11-session-agent-b`, in place of their local folder names):
Northbound 2.4 → 2.4.1 (`e2e-3`), the 15 Spree `S11*` / `screen-11*` reader reviews, and Finablo `r1-run-1` and
`wide-run-3k` (both of its review files).

**Combined with the first run:**

| App | Eligible | Sent | Distinct crops | Real: confirmed / contradicted / unreadable (by issue) | (by distinct crop) | Controls sent | Controls contradicted |
|---|---|---|---|---|---|---|---|
| Northbound (2.3→2.4, 2.4→2.4.1) | 15 | 11 | 5 | 11 / 0 / 0 | 5 / 0 / 0 | 11 | 11 (5 distinct) |
| Spree (spree-scale-2t, S11*, screen-11*) | 32 | 5 | 4 | 4 / 1 / 0 | 3 / 1 / 0 | 5 | 5 (4 distinct) |
| Finablo (r1-run-1, wide-run-3k) | 61 | 49 | 22 | 43 / 1 / 5 | 18 / 1 / 3 | 42 | 42 (20 distinct) |
| **Total** | 108 | 65 | 31 | **58 / 2 / 5** | **26 / 2 / 3** | 58 | **58 (29 distinct)** |

**Why the honest n is 31, not 65.** Many issues point at the same element on the same page: the Northbound
"Departing soon" banner appears on several personas' pages in both releases, and Finablo's two runs and several
rules cite the same messages. `probe/near_duplicates.py` (method fixed before it was run) puts two crops in one group
when their sha256 is equal, or when the claim is the same text and the 64 x 64 grayscale crops differ by under 3/255
on average. 28 of the 65 sent crops are byte-identical to another; the 65 collapse to 31 groups
(`extension/near-duplicates.json`). Within every group the real result was the same. 44 of the extension's 109 calls
were answered from the router's cache, because an identical image, claim and seed had already been sent; they are
counted per issue above but are not new model readings.

**Not sent: 43 of 108 eligible.**
- 16 (Northbound 4, Finablo 12): every cited event is an email, chat or push message, so there is no screenshot.
- 27 (Spree): the review's `captures` folder is a symlink to another run's captures (`runs/S11a/captures`).
  `semaudit visual` refuses a screenshot path that leads outside the review's folder, by design (the same
  containment rule as the review page). These are re-readings of the S11a pages, whose own issue was sent.
- 8 more Spree issues (the `screen-11-session-agent-a` review) and 5 others are not eligible at all: their
  quotes were not matched to the capture, so `basis_of` refuses them. They are not in the 108.

**The 7 real issues that were not `confirmed`:**
- **Spree, `S11c` U1 line amount: `contradicted`, and right.** The reader's issue cites the order Total element
  (which shows $48.59) with the quote $43.19 (the line amount, a different element of the same message). The text
  evidence check accepted it because it looks for a bare figure anywhere in the same message. The crop shows the
  outlined Total reading $48.59 (`extension/crops/S11c__…88803e39.png`). So the visual check caught a mis-cited
  element that the text check let through.
- **Finablo, 1 issue: `contradicted` ("not visible").** In its screenshot the page is dimmed and the outlined element
  is nearly blank; the model said the element is not visible. That looks right from the crop, but it was not checked
  further. Its control also came back `contradicted` for the same reason, not because the planted value was caught:
  so 57 of the 58 controls were caught on the value itself.
- **Finablo, 5 issues (3 distinct crops): `unreadable`, the reply's fields disagree.** In each, the model read the
  text exactly except for an emoji that it left out (3 issues) or a curly apostrophe that it wrote as a
  straight one (2 issues), and said `same_as_text: true`. SRA's comparison does not normalize either, so the reply
  counts as self-contradictory. Normalizing them would make these `confirmed`; it was not changed after seeing the
  results.

**Finablo is a private product.** For it, only ids, result codes, reasons (SRA's own wording) and sha256 hashes are
committed (`extension/results-finablo.json`): no crop, quote, model reading or page text. Northbound and Spree
records are in full (`extension/results-northbound-spree.json`, `extension/controls/`, `extension/crops/`).

**Checked, not a result:** `visual.target` takes the occurrence's first quote even when the first cited web event is
not the occurrence's first event. Of the 92 issues with a web target, 29 use a later event; in none of them does the
quote at that event's position differ from the first quote, so no result here is affected. Not changed.

**Cost:** extension $0.126463 billed (65 calls; the 44 cache hits are not billed; `extension/ledger.jsonl`), first
run $0.027277, together $0.1538.

**Not shown by this:** a rate for hard pages. 31 distinct crops from three apps, one seed, mostly clean text. No
email, PDF or chat. The Finablo results cannot be checked by a reader of this repo beyond the hashes.
