# Spree tax-inclusive line: reproduced on today's upstream storefront (2026-10-30)

**Setup:** Spree's storefront at its current upstream commit `8ba5eee` (2026-10-30, github.com/spree/storefront),
installed fresh with its own lockfile and run on 127.0.0.1:4032 against our beta3 Spree backend.
**Order:** one 2-Slice Toaster ($39.99), shipped Standard to New York (8% tax), paid by check.
Test order R1003, shopper `taxline@example.test`. The candidate store was reset afterwards.

| Surface | Line item | Subtotal | Shipping | Tax | Total | Do the shown lines add up? |
|---|---|---|---|---|---|---|
| Checkout summary (`checkout-summary-head-8ba5eee.png`) | **$43.19** | $39.99 | $5.00 | $3.60 | $48.59 | no: 43.19 + 5.00 + 3.60 = 51.79 |
| Order-placed page (`order-placed-head-8ba5eee.png`) | **$43.19** | $39.99 | $5.00 | $3.60 | $48.59 | no |
| Confirmation email (`email-text.txt`) | $39.99 | $39.99 | $5.00 | $3.60 | $48.59 | yes |

Cause in code: the storefront renders each line with `item.total`, which in a US (tax added on top) store already
includes the line's tax ($3.20 of the $3.60), next to a Subtotal without tax and a separate Tax row
(`src/components/checkout/Summary.tsx:51`; same pattern on the order page). Issue/PR search for "tax" in
spree/storefront on 2026-10-30: nothing about this. Not filed upstream (owner decision pending).
First flagged by SRA in the untargeted 67-shopper run (spree-scale-2t), in both beta2 and beta3.
