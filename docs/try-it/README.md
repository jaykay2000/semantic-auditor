# Inputs for `semaudit demo`

`semaudit demo` (code: [src/semaudit/demo.py](../../src/semaudit/demo.py)) rebuilds two committed pages from the
files listed in [demo.json](demo.json), with no model key, browser or network, and compares each rebuilt page byte
for byte with its committed copy. Measured on 2026-11-01: both equal, in under 1 second on a laptop.

| Output | Built by | From | Must equal |
|---|---|---|---|
| Release review page, Northbound 2.3 → 2.4 | `report.page.build` (the code `semaudit report` uses) | `northbound-2.3-2.4/review-2.3-2.4.json`, its episodes `northbound-2.3-2.4/episodes/`, the captures in `../sample-review/captures/`, the contract in `examples/northbound/contract/` | `../sample-review/index.html` |
| Saved-check cards, owner run `ic-owner-rec-1` | `imported.card` (the code `semaudit checks card` uses) | `../evidence/imported-checks/acceptance/run-owner-2026-11-01-saved-checks.json` and `spree-saved-checks/contract-imported/` | `../evidence/imported-checks/acceptance/cards-run-owner-2026-11-01.html` |

## Where the inputs come from

- `northbound-2.3-2.4/review-2.3-2.4.json` is the Northbound 2.3 → 2.4 review run **with the judge self-check on**
  (2026-11-02, run `sc-live-1`, [evidence](../evidence/judge-self-check-2026-11-02/README.md)): the same episodes,
  the same 62 cached model replies and the same 9 issues as the review described below, plus the self-check result
  (6 of 6, $0.046 on Muse Spark 1.3). Its three manifest paths are written relative in the same way. It replaced
  the review below on 2026-11-03.
- Before that, the file was the Northbound 2.3 → 2.4 review **rebuilt at commit `8c2c762`**
  (2026-11-01) from the recorded run `e2e-2`: the same episodes and the same recorded re-captures, every model reply
  read from the model cache (62 calls, all cached, $0). The three absolute paths in its manifest (run folder,
  contract, adapter) are written relative to the repository, the same rewrite `demo/build_sample_review.py` makes on
  the hosted page.
  - Why rebuilt: the original review (Oct 27, sha256 `d1a5c025aed4d7a9…`) was made at an earlier commit. Since commit
    `0aebabf` (Oct 28) the code gives one issue a different signature (`fare_lock|fact:units_left`), so
    `verify-report` reported it as not consistent.
  - What did not change: the outcome (provisional; the policy would say hold), the policy row, the measurement, all
    9 issues (severity, confidence, verification status and every step result, personas, delta), the resolved and
    not-raised lists, and every persona's rule results.
  - What changed on the page: U1's "What is true" box shows the app's record value (9 units left) where it said "No
    record value in this review"; claim chips that match the record say so; the model labels name the Meta API; the
    cost line counts the cached calls.
  - Whose replies: the cache keeps one reply per request, and later runs on Oct 27 (`fresh-1`, `fresh-2`,
    `dev-fresh-1`) sent identical requests and replaced the stored replies. So 19 of the 38 defender explanations
    (6 of them with a different label) and 6 of the 89 rule-evaluation notes are those later runs' wording. No
    verification result changed.
- `northbound-2.3-2.4/episodes/` (both releases), `captures/` (the 38 files the cited evidence points at) and
  `model-cache/` (the 10 recorded replies the re-derivation reads) are what `semaudit verify-report` needs. The cache
  files were scanned for key values and local paths: none.
- `spree-saved-checks/contract-imported/` is the Spree harness's `contract-imported/` folder at its `publish-prep`
  commit `a82d0aa`, with only three of its 58 checks kept: `C1-04` and `C1-04-v1` (the two the owner approved) and
  `X1-04` (the gap card). Every kept file is byte-identical to that commit (sha256 checked). The sha256 of
  `approvals.yaml`, `checks/C1-04.yaml` and `checks/C1-04-v1.yaml` match the digests the owner run recorded as
  loaded from storage (`b95ca35159dbcb55`, `d3408fbc3d2146e2`, `df192ed9b46a8907`).

## What it does not show

- No model is called, so nothing here measures a model. It shows that the recorded results re-render exactly from
  the committed inputs.
- `semaudit verify-report` checks the review itself, offline, from these committed inputs:

  ```bash
  .venv/bin/semaudit verify-report docs/try-it/northbound-2.3-2.4/review-2.3-2.4.json
  ```

  It prints `CONSISTENT` (exit 0) in a fresh clone. A missing input gives `cannot verify` (exit 2), not a false
  "not consistent" (`tests/test_verify_report_inputs.py`).
