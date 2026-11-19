# Coverage drafting, first validation on a real store: Spree 6.0.4 (2026-11-18)

**Question.** The escape catch test ([write-up](../escape-catch-spree-6.0.3-6.0.4.md)) reviews Spree 6.0.3 → 6.0.4
with three shoppers. What did those three never show the auditor, and can a drafted shopper close it?

**How.** In the Spree harness (`review-root-escape-xfam`, every model role on Muse Spark; no Claude call):
`semaudit coverage runs/esc-2/review-before-after.json --draft` lists the gaps and asks one model call for shoppers
that would close them. A draft is accepted into a copy of the contract (`coverage-accept`), run on the real 6.0.4
store, read, and the map is computed again with it.

## Result

| step | shoppers | gaps a shopper can close | what happened |
|---|---|---|---|
| map from the review | 3 | 8 (first map: 13, see below) | discounts, applied code, fees, total quantity, amount due never compared |
| draft 1, Sofia (2 items, FREESHIP, Express), joins the usual checkout | 4 | 8 | the store refused the code: the usual checkout enters it before a delivery method exists |
| draft 2, Sam (same draft from the model), code step moved after delivery by the owner | 5 | 6 | code accepted; discount total now checked on every surface (U1 and U2 closed) |

Left open, with why: total quantity (the store never shows one), fees (the store has none configured), and the
discount line and amount due (shown 8 and 6 times, never twice comparably). Draft 2 also produced 10 violations on
the admin order page. They are misreadings, not store bugs: a discounted order adds an "Adjustments $58.60" row
(discount plus tax, arithmetic correct), which the reader took as the tax, and it then read the tax as the item
total. That is the same kind of misreading as the known 6.0.4 false alarm, on a row only a discounted order shows,
which no earlier shopper reached. Fixed at its source the same day (two sentences in the contract's reader
instructions), which also removed the 6.0.4 false alarm: see the
[escape catch write-up](../escape-catch-spree-6.0.3-6.0.4.md), fourth pass.

## What the validation corrected

- **The first map was wrong.** It counted every figure in a checked message as checked, so U1 ("every figure
  matches the order record") looked as if it had compared line prices; it never had. It also offered shoppers gaps
  no shopper can close. Fixed: a fact counts only when a check compared it, and two kinds are now listed apart, with
  what the contract would need: 7 figures U1 lists that the store's order oracle never gives a value for (unit and
  line prices, quantities, offered delivery rates, compare-at price, discount line, payment amount), and 2 text
  figures with no word list (delivery method name, applied code).
- **A draft is a guess until it runs.** The model's draft passed every contract check and still failed on the
  store. Running it, then accepting, is the order that works; the owner edited the second draft by hand.
- **Adding a shopper used to re-read every page.** Readings were cached per batch of 25, so one new shopper shifted
  every batch ($0.25 wasted here). Readings are now kept per message: reading Sam's pages took 3 calls ($0.07), and
  every other shopper's readings were reused.

## Cost

$0.68 in all, all Muse Spark: drafting $0.07 (two calls), reading Sofia's pages $0.29, reading Sam's $0.07, and
$0.25 spent re-reading the three existing shoppers' pages before the per-message fix. The map itself is offline and
free.

## Limits

- One store, one release, two drafted shoppers.
- The map counts what the reader read. A figure misread as another (the admin payment read as the tax) looks never
  shown; the map cannot tell "not shown" from "misread".
- The second draft needed a human edit the model could not have known (when this store accepts a code).
