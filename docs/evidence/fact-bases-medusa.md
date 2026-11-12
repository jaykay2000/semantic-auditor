# Declared bases on Medusa v2.17.2 → v2.18.0 (2026-11-12)

**Question.** Most of v2.18.0's 129 issues were correct figures in a second form the rules did not know (a line price
shown with VAT and after the promotion; the admin page's tax and total before the discount). The owner accepted
those forms on 2026-11-05. Does declaring them on the facts remove those issues without hiding a real fault?

**How it was measured.** A free replay (no model calls, spend $0.00) of review `medusa-r4`, using the readings the
extractor had already made, under the contract it was read with. The only change is a `bases:` list on five facts
(below). Bases are evaluation only, so every reading came from the cache.

## Result

| | v2.17.2 (real VAT bug) | v2.18.0 (VAT fixed) |
|---|---|---|
| issues without bases | 33 | 129 |
| issues with bases | 29 | 35 |
| VAT rule R10 violations | 160 → 160 | 9 → 0 |
| total rule R7 violations | 179 → 179 | 37 → 27 |
| claims nudged off a basis (+€0.05, ×1.05, VAT twice), accepted by a basis | 0 of 169 | 0 of 868 |

- **The real bug is still caught.** Every R10 and R7 violation on v2.17.2 survives.
- **v2.17.2 lost 4 issues**, all of them the delivery price shown with VAT in parentheses on the order page, the form
  the owner accepted.
- **v2.18.0's 35 remaining issues are not basis questions.** We classified them from the issue notes and the
  captured pages:

| remaining v2.18.0 issues | count | what it is |
|---|---|---|
| admin "Paid Total €0.00" read as the order total | 13 | extraction vocabulary: the contract had no amount-paid fact (added on 2026-11-05 as `amount_paid`) |
| a line amount or subtotal read as the order total | 14 | extraction labels, e.g. "2 x €12.00 … €24.00" read as a €24 total (bruno, step 11 page) |
| one product priced €30 against a single €10 `unit_price` | 8 | contract model: `unit_price` is not keyed by product |

### Which bases accepted claims (v2.18.0 entries)

| basis | entries |
|---|---|
| `unit_price` with_vat / after_promotion / after_promotion_with_vat | 126 / 18 / 45 |
| delivery charge with_vat (rule R15) | 26 |
| admin tax_total before_discount | 27 |
| admin discount_total with_vat | 30 |
| admin order_total before_discount | 40 |

## The bases (from the owner's rulings of 2026-11-05)

```yaml
unit_price:      # line surfaces: storefront_cart, storefront_checkout, storefront_order_page; round 0.01
  with_vat:                 unit_price * (1 + tax_rate / 100)
  after_promotion:          unit_price * (1 - promo_percent / 100)                          when discount_total > 0
  after_promotion_with_vat: unit_price * (1 - promo_percent / 100) * (1 + tax_rate / 100)   when discount_total > 0
delivery_charge: # storefront_order_page
  with_vat:                 delivery_charge * (1 + tax_rate / 100)
tax_total:       # admin_order
  before_discount:          tax_total + discount_total * tax_rate / 100
discount_total:  # admin_order
  with_vat:                 discount_total * (1 + tax_rate / 100)
order_total:     # admin_order
  before_discount:          order_total + discount_total * (1 + tax_rate / 100)
```

## Limits (read before quoting the number)

- **In-sample.** The owner's rulings came before this test, but the expressions were written while looking at
  these issues. 129 → 35 shows the mechanism works and how far it reaches here. It does not show how well bases
  transfer to the next release or another store.
- **One review, one reading per message.** No re-reads, no variance.
- **A basis is a door.** Each one accepts a form that would otherwise be a violation. The negative control
  checks near misses, not every possible wrong value, so a wrong value that happens to equal a declared form
  would pass. Keep bases per surface, and give each one a `when` where possible.
