# Inputs for `semaudit demo`

`semaudit demo` (code: [src/semaudit/demo.py](../../src/semaudit/demo.py)) rebuilds two committed pages from the
files listed in [demo.json](demo.json), with no model key, browser or network, and compares each rebuilt page byte
for byte with its committed copy. Measured on 2026-11-01: both equal, in under 1 second on a laptop.

| Output | Built by | From | Must equal |
|---|---|---|---|
| Release review page, Northbound 2.3 → 2.4 | `report.page.build` (the code `semaudit report` uses) | `northbound-2.3-2.4/review-2.3-2.4.json`, its base-release episodes `northbound-2.3-2.4/episodes/2.3/`, the captures in `../sample-review/captures/`, the contract in `examples/northbound/contract/` | `../sample-review/index.html` |
| Saved-check cards, owner run `ic-owner-rec-1` | `imported.card` (the code `semaudit checks card` uses) | `../evidence/imported-checks/acceptance/run-owner-2026-11-01-saved-checks.json` and `spree-saved-checks/contract-imported/` | `../evidence/imported-checks/acceptance/cards-run-owner-2026-11-01.html` |

## Where the inputs come from

- `northbound-2.3-2.4/review-2.3-2.4.json` is the recorded Northbound run `runs/e2e-2/review-2.3-2.4.json`
  (sha256 `d1a5c025aed4d7a9…`, not in git: the run folder is 10 MB) with one change: the three absolute paths in its
  manifest (run folder, contract, adapter) are written relative to the repository, the same rewrite
  `demo/build_sample_review.py` makes on the hosted page. `episodes/2.3/` is that run's base-release episodes, copied
  unchanged; the page reads them for the base record values.
- `spree-saved-checks/contract-imported/` is the Spree harness's `contract-imported/` folder at its `publish-prep`
  commit `a82d0aa`, with only three of its 58 checks kept: `C1-04` and `C1-04-v1` (the two the owner approved) and
  `X1-04` (the gap card). Every kept file is byte-identical to that commit (sha256 checked). The sha256 of
  `approvals.yaml`, `checks/C1-04.yaml` and `checks/C1-04-v1.yaml` match the digests the owner run recorded as
  loaded from storage (`b95ca35159dbcb55`, `d3408fbc3d2146e2`, `df192ed9b46a8907`).

## What it does not show

- No model is called, so nothing here measures a model. It shows that the recorded results re-render exactly from
  the committed inputs.
- `semaudit verify-report` is not part of the demo: re-deriving the Northbound review at today's code gives one
  issue a different signature (`fare_lock|fact:units_left` where the Oct 27 review has `fare_lock`), a change made
  on Oct 28 (commit `0aebabf`). So the recorded review is no longer what today's code would derive from its inputs,
  and the demo does not claim it is.
