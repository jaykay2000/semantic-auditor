# Demo script v3.1 (draft, 2026-10-29), for owner review

> ⏸ **PAUSED (owner, 2026-10-29): "lets focus on the experiment first and pause on demo recordings".** No recording,
> script lock or new assets until Experiment A's results are in. **Claude comparison (owner: "go with A for the Claude
> comparison"):** the v1 Claude rows are NOT shown in the video; the README describes the v1 plain-agent runs as a
> retrospective case study with unequal conditions. A comparison may appear in the video only from Experiment A,
> worded per `spree-plain-agent-protocol/FAIR-COMPARISON-v4.md` §11. Rulings: `spree-plain-agent-protocol/DECISIONS.md`.

**Story (owner, 2026-10-29):** what the Semantic Release Auditor (SRA) does, and how it builds the right context for a
model to review a release. One call or many is not the point.

**Positioning (owner review of v2, adopted):** the innovation is not a better model. It is a system that assembles the
context a strong model needs to audit a release thoroughly, repeatedly, and with evidence. The video must also keep the
project's category: a **semantic release auditor** (failures that come from how correct pieces combine), not AI-made
regression tests for numbers that don't add up.

**The one sentence the video must leave behind:**
> SRA turns what a team already writes down into the context a model needs to review a release the way users live it:
> the rules, the shoppers to play, every page and email they would see, and the app's own record of what is true. With
> that context, Meta's Muse Spark finds the real bugs, including ones no single check would express, says which
> release introduced or fixed them, and hands the team a ticket they accept.

Target 2:58, about 330 spoken words. Every number below has its source in the "Evidence" table at the end; nothing is
shown that the table does not hold.

## What changed from v2 (owner review)

| Review issue | Change in v3 | Checked how |
|---|---|---|
| A. "Every page was fine on its own" is false: the email itself didn't add up | Hook rewritten in the reviewer's wording | Captured email: lines sum to $227.16, total says $232.16 |
| B. Both examples are arithmetic; the category is at risk | New 15 s beat: Northbound's Maya, two true messages that nothing reconciles. Hero voice-over now says no one wrote a test for this case | Maya's issue: verified, new in 2.4, major (docs/evidence/w9-review.md, w11b) |
| D. Finablo's $32,500 is also wrong for a 61-year-old | Before/after table on screen; voice-over names both wrong figures. **v3.1 correction:** v3 said v707 fixed the IRA on the report. It did not: the report still shows "Open a Roth for $7,500/yr." above a line saying $8,600 | Every 401(k)/IRA line in the 61-year-old's captured stories, both releases (values below) |
| E. The 33/33 result came from a separate judge script | **Done:** `semaudit review --reader` (commit 060db55). The model reads SRA's context; SRA checks each quote against the captures, groups the findings and dates them; output is the normal review, page and tickets. Count is now **30 of 33** with quotes checked (3 more named without a quote) | Reader review of spree-scale-2t and wide-run-3k from cache, $0; 8 tests, each safeguard shown to fail its test when removed |
| Hook candidates: Spree exchange (#14721), coupon (#14762) | Not adopted yet. Exchange is in our release pair but our docs, contract and shoppers never touch exchanges; see Decisions | GitHub API (merge dates below); grep of contract and doc pack |

## Storyboard

| Time | Beat | On screen | Voice-over (draft) |
|---|---|---|---|
| 0:00–0:18 | **Hook: an email that doesn't add up** | Spree 6.0.0.beta2 (open-source store, real release). Jo's order page: *Total $232.16*. Her confirmation email: *Subtotal $214.96 · Promotion (Free Shipping) −$5.00 · Shipping Standard $0.00 · Tax $17.20 · Order Total $232.16*. A running sum under the lines stops at **$227.16**. Caption: *fixed upstream in beta3, PR #14725*. | "A real open-source store confirmed an order for $232.16. Its confirmation email showed the same total, but the line items added up to $227.16. This wasn't hypothetical: Spree's maintainers fixed it in their next beta." |
| 0:18–0:30 | **What SRA is** | Title: *Semantic Release Auditor*. Strip: **Docs → Rules → Shoppers → Captures + truth → Muse Spark → Release review**. | "We built Semantic Release Auditor to rebuild these experiences, find what's inconsistent, and show exactly what changed between releases." |
| 0:30–1:12 | **Hero: building the context (Spree)** | One continuous product run, not separate scripts (needs decision 1). (1) **Rules**, written blind from 15 public Spree doc pages: 25 facts, 11 rules (*every figure we show matches the order record*). On screen, under the rule: *the result in this video used 4 of the 11 rules (U1, U2, U9, L1); SRA now gives the model all 11* (owner decision, 2026-10-29: option A). (2) **67 shoppers**: tax × basket × promo × delivery. (3) **Captures**: 134 checkouts, about 1,800 pages and emails, each beside the order record at that moment. (4) **Release review page** (`semaudit review --reader`): *resolved in beta3*, 30 of the 33 affected shoppers, each quote found in the captured email, none unaffected. Click one: the email text, the record ($5.00 shipping), the shopper's steps, *Draft ticket*. | "Nobody wrote a test for a free-shipping code in an email. SRA wrote the rule from the store's docs and chose the shoppers that would hit it: taxed or not, one item or three, with or without a code. It played each one through checkout on both releases, and kept every page and email next to what the order record said was true. Muse Spark read all of it and found the bug in the old release. SRA checked every quote against the captured email: 30 of the 33 shoppers it hit, and it's gone in the new release." |
| 1:12–1:27 | **Beyond arithmetic: two true messages (Northbound)** | Tag: *Northbound, fictional benchmark app*. Maya, two minutes apart: email *"Prices on your dates are likely to drop… We suggest waiting"* → banner *"2 seats left at this fare. Lock it for 48 h for €9"*. Issue card: *unexplained tradeoff, major, verified, new in 2.4*. Then Lena, whose message explains the tradeoff: *cleared*. | "Not every release bug is a wrong number. Maya is told to wait for a lower fare, then offered a lock on today's price. Both messages are true; nothing helps her choose. SRA flags it, new in this release, and clears Lena, whose message explains the choice." |
| 1:27–1:50 | ⚠️ **ON HOLD: the plain-agent half of this row (Muse/Claude v1 numbers) is withdrawn by owner ruling A; it is rewritten from Experiment A's results.** **Why the context matters (measured)** | Left, the ablation on Northbound: same model, same captures. With SRA's evidence: **15 of 15, 0 false alarms**. Without the order-record readings: **12, 1 false alarm**. Plain-English rules instead of SRA's: **10, 6 false alarms**. Right, the plain-agent benchmark (Spree, blind-graded on the live stores; scene s05b): Muse Spark with SRA's context **2 of 2 known issues, 0 false alarms**; Muse Spark alone **0 and 2** of 2, with **5 and 2** false alarms (each run stopped at its $8 cap); Claude Opus alone **2 and 2**, with **3 and 0** false alarms, plus 15 and 8 other real issues outside SRA's rules. | "Is it the model or the context? Take SRA's evidence away and the same model misses bugs and invents others. On a real store, Muse Spark exploring on its own found both known bugs in one run of two, with seven false alarms. With SRA's context it found both, and none. A strong general agent like Claude found them too, and more besides: SRA doesn't replace exploring, it makes the release check repeatable." *(decision 5)* |
| 1:50–2:25 | **A real product, validated by its team (Finablo)** | Tag: *Finablo, a real personal-finance app (existing product, not part of this submission)*. Table, a 61-year-old's limits (see "Finablo values"): **v706** 401(k) shown as $32,500 and as $24,500, correct $35,750 → **v707** $35,750 everywhere: *resolved*. IRA: *"Open a Roth for $7,500/yr."* above *"…an additional $8,600/yr"*, in both releases: *still open, quoted text still shown*. Then three GitHub issues SRA drafted → the product team reproduced **3 of 3** and accepted the 2 IRA issues. Labels: *target persona*, *rule from IRS 2026 limits*. | "On a real product, a 61-year-old saw two different 401(k) limits, and both were wrong: at 61 the limit is $35,750. The next release fixed both. But the IRA headline still says $7,500, right above a line saying $8,600. SRA marks the first resolved and keeps the second open, because the old text is still on screen. The team reproduced all three tickets it drafted and accepted both IRA issues." |
| 2:25–2:38 | **Meta's role** | Model line from the review manifest: *Muse Spark 1.3 / 1.2 (Meta API) on Finablo and Northbound; Muse Spark Open on Baseten on Spree*. Cost chip: $11.11 for 134 checkouts. | "Muse Spark does the reading and judging. On Spree it ran on Muse Spark Open, on Baseten: about eleven dollars for 134 checkouts." |
| 2:38–2:58 | **Close** | Release review page: verdict, new / resolved, evidence, *Draft ticket*. Closing card: repo URL · open source · Muse Spark. | "Rules from your docs, shoppers from your rules, truth from your app, and every finding tied to what users actually saw. Semantic Release Auditor: review the release your users actually live." |

## Finablo values (61-year-old, target persona)

Read from every 401(k)/IRA line in the persona's captured stories (report, dashboard, export, PDF, guest report).

| | v706 | v707 | Correct, 2026 |
|---|---|---|---|
| 401(k) maximum | $32,500 (report headline, dashboard, export, PDF) and $24,500 (the report's plan list, guest report) | $35,750 everywhere | $35,750 ($24,500 + $11,250 catch-up for ages 60–63, where the plan allows it) |
| IRA | "Open a Roth for $7,500/yr." (report, dashboard, export) above "…an additional $8,600/yr"; the plan list says $7,500 | headline still $7,500; every line $8,600 | $8,600 (age 50+) |

$24,500 is the under-50 limit and $32,500 the ordinary 50+ limit, so v706 showed two different wrong figures, both
on the report. **Correction to v3:** v707 did not fix the IRA on the report; the headline still says $7,500. The
reader review records this as: 401(k) issues resolved; IRA headline "unconfirmed, the quoted text is still shown in
head"; the export's IRA issue pre-existing. SRA's earlier rule-pipeline review had called a report-vs-export IRA
disagreement **new in v707**; that was wrong (both releases show both figures), so the demo no longer says "new".

## What we do NOT say (measured, so not claimable)
- "SRA beats a frontier model." Not measured as such. On Northbound and Finablo the same model given SRA's context in
  one call matched or beat SRA's own multi-step pipeline; on Spree SRA's rule pipeline raised mostly false alarms
  (outside audit: 64 of 66 sampled). The demo shows the **model reading SRA's context**.
- "Every page was fine on its own" (the email didn't add up by itself).
- "Found blind" on Finablo. The 61-year-old is a target persona; the limit rule is ours, from IRS 2026 figures. Only
  walt (58) is a blind persona, and the team closed that one as fixed after v707.
- "Independent second opinion." Every role is the same model family.
- Any exchange or coupon finding as blind: our docs, contract and shoppers never covered them; we would have chosen the
  flow because the upstream fix exists.
- The Spree tax-inclusive line (see Optional) unless it is reproduced on today's upstream code.

## How to say it honestly: SRA checks the rules you write down (owner, 2026-10-30)
Owner: "we should make it clear that it happens because it is for rules and it helps reduce false alarms."
- **What to make clear.** SRA reports only what a written rule covers. Every finding must name the rule it breaks and
  quote the evidence; SRA drops any finding that does not. So a bug no rule describes is not reported, even when the
  evidence is in the recordings. This is by design, not a miss.
- **Why it is built that way.** The rule-and-quote requirement is what keeps false alarms down. Northbound ablation,
  same model, same captures: with SRA's rules **15 of 15, 0 false alarms**; with plain-English rules instead **10, 6
  false alarms** (Evidence table).
- **The cost, stated plainly.** On Spree, 11 of the 17 known bug types in the answer key fall under no rule (for
  example, Check payment instructions promised at checkout but missing afterwards; email links pointing to
  `localhost`). SRA cannot report them; an agent exploring freely can. Source: `spree-plain-agent-protocol/KEY-v4.md`.
- **Suggested line (draft, to fit the 1:27–1:50 slot once Experiment A is graded):** "SRA checks what your team writes
  down, and it only reports what it can prove with a quote. That is why it rarely raises a false alarm. It is also
  why it won't flag a bug no rule describes; for those, keep exploring. SRA makes the release check repeatable; it
  does not replace exploring."
- **Do not say** "SRA finds every bug" or imply it covers bugs outside its rules. Do not add Spree-specific rules to
  close the gap before the results (that would be tuning on the evaluated releases); general rules, tested on another
  app, are a later step.

## Optional beat (only if confirmed before recording)
**A new upstream issue on Spree.** Checkout review and order page show each line with tax included ($43.19 for a $39.99
item in New York) above a separate *Tax $3.60*, so the lines do not add up; in both releases. Confirmed in captured pages
and storefront source; not yet run on today's upstream storefront; no upstream report found. If confirmed and the owner
approves filing, 10 seconds in 1:50–2:25.

## Decisions for the owner
1. ~~Make the context judge part of the product~~ **approved and built** (060db55); external audit pending. Not
   yet: a replay command for reader issues (needs a fresh capture plus a re-read), and a check that the release page
   reads well when every issue is factual (Spree).
2. ~~Northbound Maya beat~~ **approved**, 15 s, as written.
3. **Spree exchange as a hook.** PR #14721 is between our two releases: beta2's packing slip and exchange card name the
   original product, so a warehouse would ship the wrong item. Our setup has never touched exchanges (admin returns,
   shipped orders), so it needs new capture work, and the scenario would be **targeted, not blind**. Recommendation:
   only after decision 1 is done, a 3-hour probe ($0 until capture works, ~$1 judging); use it as supporting proof,
   not the opening. The coupon fix #14762 landed after beta3, so that bug is in both our releases; it needs
   multi-shopper coupon state, so I'd skip it.
4. **Plain-agent line** at 1:27: written after grading, as measured, even if the agent did well. (The Muse arm question
   from my last report is still open.)
5. ✅ **RESOLVED 2026-10-29, owner chose the alternative A: no v1 Claude rows in the video (see the banner at the top). The text below is the superseded recommendation.** **How to say the Claude result (new).** Claude alone found both known issues in both runs and many issues SRA's
   contract does not cover. Recommendation: say it on screen and in the voice-over (as drafted at 1:27), and frame SRA
   as the repeatable release check, not a better explorer. Alternative: show only the Muse rows (same model, cleaner
   contrast) and keep Claude in the README. Hiding Claude entirely is not offered: the protocol says report as measured.

## Evidence (source of every number)
| Claim | Source | How it was checked |
|---|---|---|
| Spree email bug, PR #14725, beta2 only; lines sum $227.16 vs $232.16 | spree-semaudit BOOT-CHECK.md; jo's captured email | Boot check on both releases; captured email text added by hand |
| PR #14725 and #14721 merged 2026-09-24 before beta3 (#14741); #14762 merged 2026-09-30 | GitHub API (`gh api repos/spree/spree/pulls/<n>`, compare beta2...beta3) | Merge dates and the beta2→beta3 commit list |
| Contract: 15 doc pages, 25 facts, 11 rules, written blind | spree-blind-onboarding (MANIFEST, out/) | Session read only its folder; leak terms removed and re-checked |
| The 30-of-33 result used 4 of the 11 rules (U1, U2, U9, L1); reader mode now gets all 11. Must also be said in the submission README | spree-semaudit CONVERSION.md, commit 2aaf09a; semantic-auditor 8529129 | The old conversion moved U3–U8 and P1 to a side file nothing loaded (verified in code); the new contract loads all 11, checked rule by rule against the author's file |
| 67 shoppers, 134 checkouts, ~1,800 captures, 0 problems | spree-semaudit runs/spree-scale-2t, verify_capture.py | Checker over every episode |
| 30 of 33 affected shoppers with quotes found, 3 named without a quote, none unaffected; resolved in beta3 | runs/spree-scale-2t/review-v6.0.0.beta2-v6.0.0.beta3.reader.json (`semaudit review --reader`, from cache) | Affected = beta2 emails with a $0.00 shipping line and a promotion line, counted from captured stories |
| Normal set: 5 of 5 baseline findings real | AUDIT-SPREE-NIGHT.md (outside audit) | Graded against captured text |
| SRA rule pipeline 64 of 66 sampled issues false alarms (unverified) | AUDIT-SPREE-NIGHT.md | Outside audit, seed-1 sample |
| Maya: unexplained tradeoff, major, verified, new in 2.4; Lena cleared | docs/evidence/w9-review.md, w11b-severity-and-page.md (runs/e2e-2) | Review output and page |
| Ablation 15/0, 12/1, 10/6 of 15 | docs/evidence/w13b-sealed-followups.md | Sealed captures, plan committed first (16bd979); n small, one run per variant |
| Finablo values table; 401(k) resolved, IRA headline still shown | finablo-semaudit runs/wide-run-3k episodes (target_61, target_61__wide) and review-10ff1e3-a183626.reader.json | Every 401(k)/IRA line in the captured elements of both releases, listed by surface |
| IRS 2026: 401(k) $24,500, 60–63 catch-up $11,250, IRA $7,500 + $1,100 catch-up | IRS 2026 limits announcement (owner's reviewer checked) | Matches Finablo's own constants |
| Finablo team: 3 of 3 reproduced, #485 #486 (IRA) accepted and closed, #484 already fixed | finablo/finlearn issues 484–486 | Their verdict comments, labels and close state (gh issue view) |
| Cost $11.11 | spree-semaudit review-root ledger + logs | Router ledger |
| Plain agent: SRA 2/2 + 0 FA; Muse alone 0/2 + 5 FA, 2/2 + 2 FA; Claude alone 2/2 + 3 FA, 2/2 + 0 FA | spree-plain-agent-protocol/results/GRADING.md | Two blind graders re-ran all 44 findings on freshly reset stores; joined with grading/key.json |
