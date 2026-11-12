# Escape backtest: what Spree fixed in the 16 days after 6.0.0 (2026-11-12, $0)

**Question.** A saved check is worth keeping if it catches what would otherwise escape. Of the defects Spree fixed
after releasing 6.0.0, which ones were SRA's kind of defect, and which could SRA's existing Spree contract have
reached?

**Data (public, read with `gh api` on 2026-11-12).**
- `core-commits.tsv`: all 220 commits on spree/spree between the `v6.0.0` tag (2026-10-27) and `v6.0.4`
  (2026-11-12).
- `storefront.tsv`: the 18 commits on spree/storefront in the same window (the storefront has no tags).
- `tags.txt`: the 6.0 tag dates.

**Method.** One reader (the building session) classified every fix by its title and, for every user-visible one,
its pull request description. A fix is any commit whose title says fix or bug, plus two whose description says
"Fixes #" (#15115, #15065). Four fixes to unreleased PayPal work were left out, because they never shipped
broken. **This is desk classification, not a measurement.** SRA was run on none of these releases, except the
storefront at `8ba5eee` (2026-10-30), where it found #289's defect.

## Result

| class | core | storefront | what it means |
|---|---|---|---|
| **claim**: a shown figure, message or offered action contradicts the record or another surface | 6 | 3 | SRA's kind |
| **broken flow**: a shopper action errors, or a page or feature is missing | 5 | 2 | SRA sees it, but today records it as "not measured", not as a finding |
| layout or visual | 7 | 1 | out of scope |
| staff tool behaviour (import, validation, invitations) | 9 | 0 | out of scope |
| not user-visible (dev, docs, API, upgrade path, agent tools, races) | 33 | 1 | out of scope |
| **total fixes** | 60 | 7 | |

### The nine claim-shaped escapes, and what SRA would have needed

| fix | what the user saw | reach with the existing Spree contract |
|---|---|---|
| storefront #289 | line shows $43.19 beside a $39.99 subtotal and a separate tax line | **caught**: SRA flagged it, we reported it, it was fixed in 2 days |
| spree #15179 | an API or agent client removes a line from a draft order and the order keeps its old total | **not reachable through the UI** (corrected 2026-11-12): the PR says the dashboard saves edits through a different endpoint that already recalculated, so no staff or shopper screen showed it. Reachable only if SRA drives the Admin API as an agent client, and then by the existing rules (U3, U4) |
| spree #14986 | "cannot be delivered" although the region's warehouse could backorder it | new rule (deliverability claims) + scenario: two warehouses, two regions |
| spree #15157 | a shopper holding the last units is refused for insufficient stock | **MEASURED, caught** (2026-11-12): rule `offered_actions_complete` + a last-units scenario. 6.0.3: one issue (2 shoppers, the store's refusal as evidence); 6.0.4: resolved; the control shopper raised nothing. See the Spree workspace's ESCAPE-CATCH.md |
| spree #15057 | admin offers Void on a captured Stripe payment that cannot be voided | new rule on staff actions (the verb exists: an offered action is possible) + Stripe |
| spree #15115, #15158 | a signed-in shopper is asked to confirm a newsletter sign-up again | new rule (no confirmation email for a known customer) + newsletter scenario |
| storefront #273 | "In Stock" beside a disabled "Out of Stock" button | new rule (availability agrees across one page) + a variant with stock but no price |
| storefront #276 | thank-you page says "order not found" after the store refused the order | new rule (a confirmation page only for a placed order) + a refusal scenario |

**Summary for the nine:** 1 caught; 7 need a new rule and a new scenario; 1 (#15179) is not reachable through any
screen, only by driving the Admin API as an agent client. (Corrected 2026-11-12: this said "1 more reachable with
existing rules and one new scenario", from the title alone, before reading the PR.) Every rule needed uses a verb SRA already has (match a record, agree across surfaces, an offered
action is possible).

## What it means

1. **The limit was scenario coverage, not judgment.** Seven of the nine sit in a part of the store our scenarios
   never visited, and one never reached a screen at all: a second warehouse, the last unit, a staff edit, a newsletter sign-up, a variant without a price,
   a refusal. Nothing suggests SRA would have misjudged them once they were on screen.
2. **Broken flows are a cheap gain.** Seven shopper-visible fixes were errors or missing features. SRA already
   records a failed step, but as "not measured". Treating "an action we offer fails" as a finding would turn
   these into issues with no new judging.
3. **Escapes are the input for the next checks.** Each row above names the scenario and rule that would have caught
   it. Keeping that list per release is the cumulative loop: an escape becomes a saved check, and the next release
   is checked against it.

## Limits

- One reader, from titles and pull request text. No second reader, and no agreement figure.
- "Reach" is a judgment of what the contract would have needed, not a run, for every row except #15157, which was
  measured: caught on 6.0.3 and resolved on 6.0.4. The published 6.0.4 Docker image ships the 6.0.3 gems, so the
  measured 6.0.4 runs a local image with the real 6.0.4 gems.
- 16 days of one project, at a fast release cadence (four patch releases).
