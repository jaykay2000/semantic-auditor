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

## The full review, with every rule (paid)

The other rules (figures, totals, the one-email rule) need model readings. Reviews used the Meta Model API
(`muse-spark-1.3` reads, `muse-spark-1.2` cross-checks and defends).

**First pass (capped, unverified).** A $0.635 cap stopped it after 29 reading calls ($0.66): 6.0.3 fully read, 6.0.4
partly, no verification. On 6.0.3 it raised 6 issues: R25 (the real defect), L1 (one email counted twice: its HTML
and text parts) and four U2 "totals disagree" issues (the address step, captured before the address is entered,
compared with the delivery step). Both causes were in how the contract described the captures, not in Spree.

**Fix ($0).** Two surface declarations, now part of the contract format (see [Add your app](../10-add-your-app.md)):
`shown_before_action` (read a surface in the state before its step's action) and `format_of` (an email's second
format is not a second contact). With them, the saved 6.0.3 readings re-score to **one issue, R25**. The totals rule
still runs: it now compares the address step with the cart (30 comparisons in the 6.0.3 run, all agreeing) instead
of the delivery step.

**Second pass (finished, verified).** 5 more reading calls finished 6.0.4 ($0.11). Verification ran on each
release's issues: re-running the affected shoppers on a fresh store, a second model re-reading the cited messages,
and a defender arguing against each issue.

| release | issues | verification | cost |
|---|---|---|---|
| 6.0.3 | 1: R25, lena and milo refused at "Place Order" | **verified**: both refusals reproduced on a fresh run; the defender found no defence | $0.10 |
| 6.0.4 | R25 **resolved**; 4 new issues (U1 + three U2), all from one reading of lena's admin order page | 2 verified, 2 partly verified (low confidence) | $0.44 |

**The four 6.0.4 issues are one false alarm.** On the admin order page, "$955.79" sits between "Completed" and the
"Taxes" heading: it is the payment amount, and the order's tax is $70.80. The reading model labelled it as tax, so
"tax $955.79" disagreed with "$70.80" everywhere else. The defender said exactly this ("the cited $955.79 ... is
not a tax_total claim"), but SRA's rule is that a disputed reading stands only when the two models disagree, and the
second model, from the same family, misread it the same way. So the defence was overruled and the false alarm kept
"verified".

What this measures: one real escape caught and verified on 6.0.3, seen resolved on 6.0.4, with no false alarm left
on 6.0.3 after the contract fix; and one false alarm on 6.0.4 that verification did not remove, because both readers
share the same blind spot. The review's overall outcome is "not measurable": 11 of the contract's rules use check
verbs the rule engine does not have (this contract was written for reader mode), and SRA says so rather than passing
them.

**Third pass: a second reader from another family (2026-11-18).** The same saved captures and readings, verified
again with Claude Sonnet 5.5 (Anthropic API) as the cross-checker; reading and defence stay on Muse Spark. Two code
changes came first. The defender may now dispute which fact a figure states (before, it could only dispute a
message's kind, decision, action, strength or trade-off, so its objection had nothing to stand on). And measuring
this pass exposed two more faults, fixed before the result below. The rule required the other model to call the
figure exactly what the defender called it: Claude read "$955.79" as the order total, the defender as the payment
amount, and that disagreement overruled a defence both sides support. The rule now asks only whether either side
reads it as the tax. And on one occurrence Claude read the figure as the item total, which broke the same rule for
the item total. The cross-check counted that as re-deriving the tax issue; it now requires the same fact.

| release | result | cost |
|---|---|---|
| 6.0.3 | R25 **verified**, as before (the rule needs no model; repro, evidence and defence pass) | $0.10 |
| 6.0.4 | R25 resolved. Of the four false-alarm occurrences, **3 fail verification as disputed** and drop out: Claude does not read $955.79 as tax and the defender's objection stands. **1 remains, partly verified, low confidence**: Claude disagrees, but in that reply the defender argued the point in prose without filling in the structured dispute, and SRA acts only on the structured one | $0.39 |

So the other-family reader removes most of this false alarm but not all of it. It costs $0.04 for the four Claude
cross-checks; the rest of this pass is the defender re-arguing under its new instructions.

**Fourth pass: the misreading fixed at its source (2026-11-18).** A drafted shopper from
[coverage drafting](coverage-drafting-2026-11-18/README.md) placed a discounted order, whose admin page adds an
"Adjustments" row, and the reader shifted that summary by one row. Seen together, the 6.0.4 false alarm is the same
fault: on the admin page each figure follows its label, but the reader sees the labels on both sides and took the
one after it ("Completed | $955.79 | Taxes" read as the tax). Two sentences in the contract's reader instructions fix
it (`contract-escape/rubric.md` in the harness): on the admin order page a figure's label is the text before it, and
the Adjustments row is not a claim; a third tells the reader that the price beside a cart line is the unit price
(the quantity is a form field the page text does not show), which a re-read of milo's cart had misread. Both
releases were read again from scratch under the new instructions and verified, every role on Muse Spark:

| release | result | cost |
|---|---|---|
| 6.0.4 | **no issues**; R25 resolved | $0.52 (the full re-read of both releases) |
| 6.0.3 | R25 only, **verified** (both refusals reproduced; the defender found no defence) | $0.10 |

Both reviews re-derive offline (`semaudit verify-report`: consistent). They are the first to pin each message's
reading in the manifest, 492 of them.

Spend for this test: $2.42 in all ($0.66 first pass, $0.65 second, $0.49 third, $0.62 fourth).

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
- The fourth pass removed this false alarm by telling the reader how this page is laid out: a contract fix for one
  store's layout, not a general one. Before it:
- With one model family (Muse Spark 1.3 and 1.2) a misreading both share is not caught by the cross-check, and the
  defender's correct objection is overruled (second pass). With a second reader from another family (third pass) 3
  of the 4 occurrences drop out; the fourth stays at low confidence because the defender's reply left its structured
  dispute empty. One figure on one page: not a rate. Confidence stays capped at medium while the defender is in the
  reader's family.
- The harness that drove the stores is public: https://github.com/jaykay2000/spree-semaudit (`ESCAPE-CATCH.md`,
  `contract-escape/`).
