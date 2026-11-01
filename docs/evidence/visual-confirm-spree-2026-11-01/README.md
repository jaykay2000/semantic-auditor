# Visual confirmation on the Spree tax line (2026-11-01)

**Result: `confirmed`, basis `evidence_linked`. A wrong-claim control on the same crop came back `contradicted`.
Cost $0.0028 for both calls.**

| Call | What the text record claims | Model reads | `visual` | Tokens (in / out) | Cost |
|---|---|---|---|---|---|
| The issue as reviewed | $43.19 | $43.19 | confirmed | 611 / 199 | $0.00161 |
| Control: claim changed to the subtotal | $39.99 | $43.19 | contradicted | 611 / 109 | $0.00123 |

- **Issue:** `R-v6.0.0.beta3-U1-line-amount-core-4f237b451a-ab6a0c63` in
  `spree-semaudit/runs/spree-scale-2t/review-v6.0.0.beta2-v6.0.0.beta3.reader.json`: after the order is placed,
  the item line shows $43.19 (price plus tax) where the order records $39.99.
- **Why it qualified, and what that means:** it is a reader issue. Its verification status is `unverified` (no
  replay, second model or defense ran), but its quote was checked against the capture (evidence_linked: pass). So the
  basis is `evidence_linked`, not `verifier`. The status is still `unverified` after this run: `visual` sits beside
  the verification and changes nothing in it.
- **Command** (run from a folder whose `semaudit.toml` has `[roles.vision]` = baseten,
  `meta-models/muse-spark-open-1026`, reasoning effort low):
  `semaudit visual <that review> --out review.visual.json --max-usd 0.10 --issue <the id above>`.
  It printed `confirmed 1, contradicted 0, unreadable 0, not eligible 0`.
- **What was sent:** `crop.png` (684 x 361), cut from Ana's beta3 order-placed screenshot at page px
  144,308 to 828,669 around the cited element's box, with the element outlined in red. Its sha256 is in `visual.json`.
- **Nothing else changed:** the written copy, with `visual` removed, equals the review JSON for JSON, compared after
  sorting keys. The review file in the Spree harness was only read.
- **Control:** `probe/control.py` sends the same crop with the claim changed to $39.99. Same image, same seed,
  so a model that answered "yes" to anything would have confirmed it.
- `visual.json`, `control.json` and `ledger.jsonl` (the two ledger rows) are the records. No key is in any of them
  (checked).
- **Not shown by this:** how often the answer is right across many issues or pages. One issue, one seed, plus one
  control.
