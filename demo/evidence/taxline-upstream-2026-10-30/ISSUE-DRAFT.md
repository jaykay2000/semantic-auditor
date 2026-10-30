# Draft issue for github.com/spree/storefront (owner to review and post)

Attach before posting: `checkout-summary-head-8ba5eee.png` and `order-placed-head-8ba5eee.png` from this folder.

---

**Title:** Line items show the price with tax included, above a separate Tax row, so the order summary doesn't add up (US / additional-tax stores)

**Body:**

In a store where tax is added on top of the price (for example US sales tax), the checkout summary and the
order-placed page show each line item with its tax already included, and then list the tax again in the Tax row.
The visible numbers don't add up, and the same item shows a different price in the confirmation email.

### Steps to reproduce

1. Storefront at `main` (8ba5eee, 2026-10-30), backend Spree 6.0.0.beta3 with the sample data, plus an 8% sales tax
   rate for New York.
2. Add one item to the cart (2-Slice Toaster, $39.99).
3. Check out with a New York shipping address and Standard shipping ($5.00). Pay by check and place the order.

### What the shopper sees

| Where | Line item | Subtotal | Shipping | Tax | Total |
|---|---|---|---|---|---|
| Checkout summary | **$43.19** | $39.99 | $5.00 | $3.60 | $48.59 |
| Order-placed page | **$43.19** | $39.99 | $5.00 | $3.60 | $48.59 |
| Confirmation email | $39.99 | $39.99 | $5.00 | $3.60 | $48.59 |

On the two pages, the line reads $43.19 but the Subtotal right under it is $39.99, and $43.19 + $5.00 + $3.60 =
$51.79, not $48.59. The $3.20 of tax on the line is shown twice: once inside the line, once in the Tax row.
The total charged ($48.59) is correct; only the display is inconsistent.

### Expected

The line shows the same basis as the Subtotal and the email ($39.99 here), or is clearly labelled as including tax.

### Cause

The line is rendered with `item.total`, which for a line with additional (non-included) tax already includes that
tax, while the Subtotal comes from `cart.item_total` and tax is shown separately from `cart.tax_total`:

- `src/components/checkout/Summary.tsx:51`: `formatMoney(item.total, item.currency)`
- `src/app/[country]/[locale]/(checkout)/order-placed/[id]/page.tsx:201`: same
- `src/components/order/LineItemCard.tsx:57`: same (account order history; not checked on screen)

In stores with tax included in prices (VAT), the line's tax is already in the price, so the mismatch doesn't show
there. That is probably why it hasn't come up.

### Possible fix

Render the line on the same basis as the Subtotal, for example `price × quantity` (which is what the email shows),
or `total − additional_tax_total`. Alternatively, keep `item.total` and label it "incl. tax", but then the Tax row
double-counts visually.

I didn't find an existing issue or PR about this. Happy to send a PR if that helps.

---

*Optional last line (owner's choice; leave out to keep the project private until submission):*
"Found with an automated release-review tool I'm building, then reproduced by hand on `main`."
