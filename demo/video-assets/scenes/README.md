# Video scenes: still frames for the 3-minute demo

3840×2160 PNGs (1920×1080 CSS px, device scale 2), one takeaway each, for assembly in Canva. Scene times follow
`docs/archive/07-demo-reframe-draft.md` (v3.1, superseded). Every number on a frame comes from that file's Evidence table or from a
source named below. Nothing is rounded differently from its source.

## Regenerate

```bash
cd demo/video-assets
python3 slides-src/render.py            # every scene
python3 slides-src/render.py s05b s08   # only scenes whose name starts with these
python3 slides-src/extract_spree.py     # re-derive scenes-data/spree-shoppers.json from the Spree review (read-only)
```

`render.py` renders `slides-src/<name>.html` to `scenes/<name>.png` with Chromium. Network is blocked; only `file://`
loads. Every `scenes-data/*.json` is injected as `window.DATA["<stem>"]`. The script prints, per frame, any page
error and any element that spills outside the 1920×1080 frame or clips its text. All frames currently print `ok`.

**Placeholders to fill later:**
- `scenes-data/plain-agent.json` drives `s05b`. All values are `TBD`. While `status` is `"TBD"` the frame shows a
  dashed *DRAFT · VALUES TBD* badge. A `null` number renders as TBD. When `known_issues` is set, the dot size shrinks
  to fit (checked with 33).
- `scenes-data/close.json` → `repo_url` drives `s08`, `s7-b8` and `m7-b8`. Set to `https://github.com/jaykay2000/semantic-auditor`
  (owner, 2026-11-01); while it holds `TBD` the frames show a dashed placeholder.

## Frames

| File | Scene / time | The one takeaway | Numbers and their source |
|---|---|---|---|
| `s01-hook-email.png` | Hook, 0:00–0:09 | Jo's order is confirmed for $232.16 on the order page and in the email | Email text: Jo's beta2 confirmation email (HTML part), `runs/spree-scale-2t/review-v6.0.0.beta2-v6.0.0.beta3.reader.json`, persona `jo`, `base_events` `order_email_order_confirmation` (Subtotal $214.96 · Promotion (Free Shipping) -$5.00 · Shipping Standard $0.00 · Tax $17.20 · Order Total $232.16; items 3 x $49.99 = $149.97, 1 x $64.99 = $64.99; subject from `captures/…/s11.c01.raw.json`). Order page: a crop of the real beta2 step-10 screenshot (`captures/v6.0.0.beta2/jo__S-buy/…s10.c01.screenshot.png`) |
| `s01b-hook-sum.png` | Hook, 0:09–0:18 | The email's own lines add up to $227.16, not the $232.16 it states | Running sum is plain addition of the email's lines (214.96 − 5.00 + 0.00 + 17.20). Fix: Spree PR #14725, merged before beta3 (Evidence table, GitHub API) |
| `s02-what-sra-is.png` | What SRA is, 0:18–0:30 | SRA builds the context: Docs → Rules → Shoppers → Captures + truth → Muse Spark → Release review | No numbers |
| `s03a-rules.png` | Hero (1), ~0:30–0:40 | Rules were written blind from Spree's public docs: 15 pages → 25 facts → 11 rules | 15 pages: `spree-blind-onboarding/inputs/docs/` (15 files, named on the frame) and BLIND-INPUTS.md. 25 facts: `out/.semaudit/facts.yaml` (25 ids). 11 rules: `out/.semaudit/principles.yaml` (U1–U9, P1, L1; P1-E1 is an exception, not a rule). Rule text: U1 from the review JSON's `rules`. Note line: that review's contract held U1, U2, U9 (+U9.agree) and L1 only; U3–U8 and P1 sat in a side file nothing loaded (spree-semaudit CONVERSION.md; fixed in 2aaf09a / semantic-auditor 8529129, so the model now gets all 11) |
| `s03b-shoppers.png` | Hero (2), ~0:40–0:50 | 67 shoppers per release, spread across tax × basket × promo code × delivery | Every persona's `context` in the Spree review, tallied by `slides-src/extract_spree.py` into `scenes-data/spree-shoppers.json` (the frame reads that file and refuses to render if the cells do not sum to 67). Taxed = ships to NY (36), per the feature "Sales tax (NY 8%, harness-added)"; not taxed = CA 11 · NJ 10 · TX 10 (31). Baskets 1–4 units over 1 or 2 products. Every shopper pays by check, so payment is not an axis |
| `s03c-captures.png` | Hero (3), ~0:50–1:00 | Every page and email is kept beside the order record: 134 checkouts, ~1,800 pages and emails | 134 = 67 shoppers × 2 releases. ~1,800: `runs/spree-scale-2t/verify.json` reports 900 captures per release and 0 problems (storyboard wording kept). Thumbnails: Jo's real beta2 captures; step 3 has no page capture and says so; step 11 (the email) has text only, no screenshot. Record values: as shown on the release review page (page still 02) |
| `s03d-finding.png` | Hero (4), 1:00–1:12 | Muse Spark found the bug; SRA checked every quote: 30 of 33 affected shoppers, resolved in beta3 | 30 shoppers: the resolved issue's `personas` (30) in the Spree reader review. 3 more without a usable quote: its `confidence.basis` (scale03, scale10, scale11). 33 affected and 0 unaffected: Evidence table. Right: crop of page still `02-spree-email-issue.png` |
| `s04-maya.png` | Northbound, 1:12–1:22 | Two true messages two minutes apart, and nothing helps Maya choose; flagged as unexplained tradeoff, new in 2.4 | Quotes, times (10:01, 10:03), "new in 2.4", "severity major", "verified": the Northbound review (runs/e2e-2; docs/evidence/w9-review.md, w11b) as shown in page still 06. 42 days out and flexible dates: Maya's persona summary on that page |
| `s04b-lena.png` | Northbound, 1:22–1:27 | Lena gets the same two offers explained, so she is cleared | Concierge chat at 10:04 and "Cleared · P2 explained tradeoff": page still 07 (Lena, 2.4) |
| `s05-ablation.png` | Context matters, 1:27–1:42 | Take SRA's context away and the same model misses bugs and invents others | docs/evidence/w13b-sealed-followups.md, input ablation (plan committed first, 16bd979): V0 15 found / 0 false alarms, V2 12 / 1, V3 10 / 6, of 15. The frame says the rows are cumulative and one run each. V1 (no written method, still 15 / 0) is left out and named in the source line |
| `s05b-plain-agent.png` | Context matters, 1:42–1:50 | ⏸ **ON HOLD (owner, 2026-10-29):** the v1 plain-agent line is withdrawn (Claude comparison option A); redone only from Experiment A, worded per FAIR-COMPARISON-v4 §11 | `scenes-data/plain-agent.json` (all placeholders today) |
| `s06-finablo.png` | Finablo, 1:50–2:25 | The 401(k) limit is fixed in v707; the IRA headline still says $7,500 where $8,600 is correct. 3 tickets → 3 reproduced → 2 accepted | Storyboard "Finablo values" table (finablo-semaudit runs/wide-run-3k, target_61 + target_61__wide, review-10ff1e3-a183626.reader.json): v706 $32,500 and $24,500, v707 $35,750, correct $35,750 ($24,500 + $11,250); IRA headline $7,500 in both releases, correct $8,600 ($7,500 + $1,100). Tickets: finablo/finlearn #484–#486 (Evidence table). Status words match the review page: resolved; IRA *unconfirmed* (shown as "still open", the quoted text is still shown) |
| `s07-meta.png` | Meta's role, 2:25–2:38 | Muse Spark does the reading and judging on all three apps | Finablo: the review manifest's models (muse-spark-1.3 / muse-spark-1.2). Northbound: 1.3 / 1.2 (page still 07's model strip). Spree: `meta-models/muse-spark-open-1026` on Baseten (Spree review manifest). $11.11: Evidence table (review-root router ledger and logs); see note 1 |
| `s08-close.png` | Close, 2:38–2:58 | Rules from your docs, shoppers from your rules, truth from your app | No numbers. Right: page still `01-spree-overview.png`. Repo URL is a placeholder |

## Notes for the owner

1. **Check the $11.11 label before recording.** `spree-semaudit/NIGHT-LOG.md` line 46 attributes $11.11 to the
   *split baseline* run ("chunks of 11, same judge … $11.11 used"), i.e. the one-judge read of the 134 checkouts. The
   `semaudit review --reader` result shown on the page cost $0.00 from cache and reports **$9.44 if read fresh**
   (`manifest.spend.if_fresh_usd` 9.442132). The frame says "$11.11 to review 134 checkouts" as briefed. If the
   voice-over pairs it with the reader review, $9.44 is the matching figure.
2. The confirmation email has no screenshot in the captures (only its text, `s11.c01/c02.raw.json`), so s01/s01b
   redraw it from the captured text. Each frame says so in its source line.
3. The ablation evidence file does not itself name the app or the model; "Northbound" and "same model" follow the
   storyboard.
4. All frames use the release-review page's tokens (colours, radii, type stacks), copied into `slides-src/slides.css`.
   As on the page, colour means release delta: red new, green resolved, violet dashed unconfirmed. The one extra use
   is accent blue for SRA's own figures (the running sum, the "found" dots).

## Script v7 frames (2026-11-01): beats 1, 2, 7 and the end card

Spec: `docs/09-demo-script-v7.md`, storyboard rows 1, 2, 7 and 8. Same tokens, renderer and size as the frames above.
No coding agent and no non-Meta model is named on any frame.

```bash
cd demo/video-assets
python3 slides-src/crop_finablo.py      # re-cut the Finablo crops + scenes-data/finablo.json from the stored captures
python3 slides-src/render.py s7         # render the four v7 frames
```

`crop_finablo.py` reads the finablo-semaudit captures (read-only), never retypes app text, and records each source's
sha256 in `scenes-data/finablo.json`. It refuses to write anything when a crop box overlaps the place a screenshot
shows the "unused 401(k) headroom" sentence, or when a copied text line mentions headroom or lacks the expected
limit (checked by mutation: a box over y 1690–1750 was refused and no image changed).

| File | Beat | What it shows | Source capture (finablo-semaudit `runs/…`) and SHA |
|---|---|---|---|
| `s7-b1-finablo-limits.png` | 1, 0:00–0:17 | One test user on v706: the Report tab says "IRS max ($24,500/yr)"; the same user's "Copy for your AI" text says $32,500. Label "real product, my own; test persona", chip "354 automated checks: passed", footnote "2026 limit at ages 60–63: $35,750, where the plan allows catch-up contributions" | Finablo v706, tree `10ff1e3`, run locally. Screenshot: `wide-run-3k/captures/10ff1e3/target_61__S-R1/…s03.c01.screenshot.png` (sha256 `5d30b4a4daf0f66c…`), crop (315, 3058, 1185, 3242). Text: `…/target_61__S-R1/…s04.c01.raw.txt` line 50 (`bd2d59ac944daa76…`). 354: v706 deploy gate, 354 OK / 0 FAIL (finlearn `PLAN.md`). Limit: IRS 2026 |
| `s7-b2-loop.png` | 2, 0:17–0:39 | The loop, seven nodes as in the row: discovery → Muse Spark drafts a journey + the rule it broke → gate checks every step → owner approves → replay on a release → status (new · fixed · still open · came back) → saved for later reviews, with one "next release" arrow back to replay. The four statuses are labels only; no result or count is shown | No numbers |
| `s7-b3a-overlap.png` | 3, 0:39–0:50 | Two runs of one agent overlap only in part. **No numbers** (use this unless the auditor clears the counts). Caption: "two runs of one agent, same store and rules; a description, not a score or a ranking" | No numbers; the two circles are equal on purpose, so size encodes nothing |
| `s7-b3b-overlap.png` | 3, 0:39–0:50 | The same with the counts: 5 only in run 1 · 8 in both · 4 only in run 2; "17 groups of findings · 8 in both runs". **Only with the auditor's OK** | `scenes-data/overlap.json`, written by `slides-src/extract_overlap.py` from the private spree-plain-agent-protocol `results-v4/grading/scores/scores.json` (`per_trial` C1 13 groups, C2 12; `repeatability_jaccard` C1/C2 "8/17"; the script refuses to write if they disagree) |
| `s7-b7-finablo-v706-v707.png` | 7, 2:09–2:24 | v706 (`10ff1e3`) beside v707 (`a183626`), label "journey built from the known bug", no "fixed" chip. v706: $24,500 on the report while the plan is being written, $32,500 on the finished report, dashboard, copied text and PDF. v707: $35,750 on all of them | Report, plan being written: `wide-run-3k/…/target_61__S-R1/…s03` (v706 `5d30b4a4…`, v707 `e936f860…`), crop (315, 3058, 1185, 3126). Report, plan finished: `f73-limit-check/…/target_61__wide__S-wide-target/…s06` (v706 `ad12ea25…`, v707 `52844180…`), same crop. Dashboard: `…s10` (v706 `bf2a2b46…`, v707 `ac3581c3…`), crop (310, 2662, 1190, 2728). Copied text: `…s08.c01.raw.txt` line 48; PDF: `…s09.c02.raw.txt` line 50 |
| `s7-b8-end-card.png` | 8, end card 2:40–2:46 | `https://github.com/jaykay2000/semantic-auditor` · open source · "Muse Spark Open (on Baseten)" · "about 5¢ to turn a finding into a check" · "about 14¢ to re-check it on a release" | semantic-auditor `README.md` at `896f4af`: about $0.05 per conversion; Run 3c $0.54 all-in for 2 checks on 2 releases, about $0.14 per check per release. Repo URL from `scenes-data/close.json` (still `TBD`) |

Notes:

1. **Why beat 1 uses the S-R1 run, not f73-limit-check.** In the f73 run the 401(k) line is action 2 on the *guest*
   report, which is blurred until sign-up, so "$24,500" is in the page's HTML but not legible. In S-R1 the same
   answers (personas `target_61` and `target_61__wide` have identical context) sign up while the plan is still being
   written, and the Report tab shows "IRS max ($24,500/yr)" in clear text while "Copy for your AI", a minute later,
   says $32,500. Both figures on beat 1 are that one account's.
2. **Beat 7 mixes two runs with the same answers**: S-R1 for the "plan still being written" row, f73 for the
   rest. The source line says so. The claim "$35,750 on every page" rests on f73: v707 shows $35,750 in all 8 of its
   captures that state the limit, v706 shows $24,500 in 1 (the blurred guest line) and $32,500 in 7
   (`docs/evidence/imported-checks/finablo/README.md`).
3. **The headroom sentence is out of frame on both builds.** "There's roughly $12,500 of unused 401(k) headroom"
   is wrong on v706 and v707 (fixed in v708). In every screenshot used, it is *shown* in one place only: the "What this
   means" line of the "Tax-advantaged space left on the table" card, page y 1700–1739 on the report pages (s03, s06,
   both builds). Every report crop starts at y 3058, **1,319 px below it**. The same sentence also sits inside each
   collapsed "Why this move?" panel; collapsed panels are not painted in these screenshots, and the crops show no
   expanded panel (the line crops on beat 7 end at y 3126, above action 2's own "Why this move?" toggle). The
   dashboard screenshot shows the sentence nowhere (its only copy is inside a collapsed panel). The copied-text and
   PDF lines are single lines (48 / 50); the headroom sentence is a different line in each file (e.g. line 44 of the
   S-R1 copied text). Positions were measured by re-rendering each stored DOM snapshot with that release's own
   stylesheet at 1280 px (page heights match the screenshots exactly, 4767 and 3151) and confirmed by eye.
4. **The red ring on beat 1** marks "($24,500/yr)" at page x 722–812, y 3095–3112, measured with a DOM Range on the
   same re-render ("Ramp" lands at x 394 there and in the screenshot).

## Motion clips and replacement stills (2026-11-01)

Clips for beats 1, 2, 3, 4 (three transitions), 7 and the end card, plus a transparent beat-6 rule overlay, are
mapped in [`../motion/README.md`](../motion/README.md). Their stills (`m7-*.png`, `o7-*.png`) sit in this folder. The
`s7-*` stills above are unchanged.
