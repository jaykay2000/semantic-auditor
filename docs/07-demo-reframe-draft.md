# Demo reframe (draft, 2026-10-28) — not yet approved by the owner

Why: on Finablo the one-call baseline (B-judge-1) found the same headline defects as the auditor with no false
alarms, at about a tenth of the cost (wide-run-3k). The sealed Northbound benchmark said the same. The demo must
not claim an accuracy edge we did not measure. Option B (Spree at scale) may change this; this draft holds either way.

## What we can show honestly

1. A real release defect, before and after (Finablo R1). v706 tells a 61-year-old the 401(k) maximum is $24,500 on
   the report and $32,500 in the export; the true 2026 figure is $35,750. v707: gone, and the auditor marks it
   resolved. Label: target persona, harness rule.
2. What a fix can break (Finablo v707, new). v707 fixed the IRA figure on the report ($8,600) but not in the export
   ($7,500): two surfaces that agreed (both wrong) now disagree. The auditor labels it new in v707. Label: target
   persona, harness rule. A single-release review does not say "new".
3. A live defect on a blind persona (Finablo, walt, 58). The PDF says "IRS max ($24,500/yr for 401(k))"; true
   $32,500. Present in v706 and v707. Label: harness rule, blind persona.
4. A second app, not ours (Spree 6.0.0.beta2 → beta3, PR #14725). The order email's lines do not add up to its own
   total when free shipping applies; the order page is right. Rules written blind from Spree's docs. Result: TBD.
5. Evidence for every claim: the exact text, surface and moment, the true value, and a re-run that reproduces it.

## The baseline, said plainly

"A single strong model call over the same captures finds the same headline bugs. The auditor adds the release
delta (new / resolved), per-claim evidence, and does not need the whole app in one prompt." Show the side-by-side
table from wide-run-3k. If Spree-at-scale shows an edge, add it with its numbers; if not, say so.

## Open

- Finablo blind rules still raise ~40 false alarms (chart labels, two quantities under one name). Either show the
  harness rules only for Finablo, or show the count and why.
- Meta's role: Muse Spark (Meta API) for Finablo; Muse Spark Open (Baseten) for Spree.
