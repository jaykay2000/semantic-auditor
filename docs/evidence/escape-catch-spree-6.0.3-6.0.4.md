# Escape catch test: Spree 6.0.3 → 6.0.4, a shopper refused for the last units (2026-11-12)

**Question.** Spree fixed spree/spree#15157 (issue #15156) in 6.0.4: a shopper whose cart held the last available
units passed checkout and was then refused at "Place Order". It is one of the nine claim-shaped escapes in
[the backtest](escape-backtest-spree-6.0/README.md). Would SRA have caught it on 6.0.3, and seen it fixed on 6.0.4?

**Answer, measured.** Yes. On 6.0.3 SRA raised one issue from two shoppers, with the store's own refusal as
evidence. On 6.0.4 it raised none and reported the issue **resolved**. The control shopper raised nothing from this
rule on either release. That result came from rule `offered_actions_complete`, which needs no model call, so it
cost $0.

## Setup (local only, 127.0.0.1)

- **Backends.** Spree 6.0.3 from `ghcr.io/spree/spree:6.0.3`. For 6.0.4 we built a local image that upgrades only
  the spree gems to 6.0.4, because **the `:6.0.4` image runs Spree 6.0.3**: `bundle list` inside it shows
  `spree_core (6.0.3)`. Its source revision label is spree-starter `8bb32cd`, the commit before "Bump Spree to
  6.0.4". Spree also published `:6.0.4.1` from the bump commit, which is the real 6.0.4.
- **Storefront.** spree/storefront `2a85a99` (`@spree/sdk ^6.0.3`) behind both. Sample data, an 8% New York tax rate,
  and Check payment visible to shoppers.
- **Contract.** The Spree contract we used for the fair comparison, plus one rule, with three shoppers on the same
  scenario (browse, add to cart, address, delivery, Check, place the order, read every confirmation):

```yaml
- id: R25
  kind: universal
  title: A shopper's action does not complete
  check: {must: offered_actions_complete}
```

| shopper | basket | store setup before the session |
|---|---|---|
| ana (control) | one toaster | normal stock |
| lena | 1 × Automatic Espresso Machine | exactly 1 left, backorders off |
| milo | 2 × Automatic Espresso Machine | exactly 2 left, backorders off |

- **Adapter.** After "Place Order", the thank-you page means the order was placed. The storefront's own Alert
  component on checkout means the store refused it, and the adapter raises `AppFailed` with the alert's text.

**Store API check first** (no browser): with one unit left, 6.0.3 answered `422 Quantity selected of "Automatic
Espresso Machine (Color: Matte Black)" is not available.`, and 6.0.4 placed the order.

## Result

| | ana | lena | milo | R25 issues |
|---|---|---|---|---|
| 6.0.3 | completes | **refused**: "Quantity selected … is not available." | **refused** | 1 (lena, milo) |
| 6.0.4 | completes | completes | completes | 0; the 6.0.3 issue is reported **resolved** |

Both captures exited 0: every step ran or was blocked by the refusal, and nothing went unmeasured.

## The full review, with every rule (paid, stopped at its cap)

The other rules (figures, totals, the one-email rule) need model readings. The review used the Meta Model API with a
hard cap of $0.635 and stopped there after 29 reading calls ($0.66). The estimate had been 20 calls. 6.0.3 was fully
read, 6.0.4 only partly, and **no verification ran**. 6.0.3, all rules, unverified:

| issue | count | our reading (checked against the saved pages and notes, not by SRA's verifier) |
|---|---|---|
| R25: an offered action did not complete | 1 | **the real defect** |
| L1: two outbound contacts within 1 h | 1 (ana) | false alarm: ana got one email, sent as an HTML part and a text part, and the contract counts each part as a contact |
| U2: an order total disagrees across surfaces | 4 | likely false alarms: the address step shows a total before tax and delivery are known, compared with the delivery step; one reading took the $70.80 tax line for the total. A gap in the contract's checkout-state model, plus a mislabel |

So the full rule set adds no second true finding on 6.0.3 and would, unverified, add 5 false alarms. Both causes
belong to the contract, not to the release.

## What went wrong on the way

- The first refusal detector matched any `[role=alert]`. Next.js also renders a route announcer with that role,
  holding the page title, so the detector "refused" every order, including the control's. The fix matches the
  storefront's Alert component only. **The control shopper is what exposed it.**
- One backtest row was wrong: #15179 (draft order totals) never reached a screen; only Admin API clients saw it. It
  is corrected in the backtest.

## Limits

- One escape, one store, one run each. It shows the mechanism catches this class of defect, not a rate.
- The rule's catch depends on the adapter telling an app refusal from a harness failure. That boundary is now part
  of the adapter contract (`AppFailed`, `StepResult(app_error=…)`; see [Add your app](../10-add-your-app.md)).
