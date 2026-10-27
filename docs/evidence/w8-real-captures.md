# W7 + W8: stories from real captures, aligned, and the semantic core on them (2026-10-26)

**W8 result: ACCEPTED on the first real attempt.** On stories built from real Northbound captures, every
graded story matched on **5 of 5 fresh runs** (fresh extraction and fresh P2 interpretation each run, candidate
order shuffled): **31/31 per run**. All three falsifiability stubs **failed**. Cost **$0.56**.

Reproduce: capture 2.3, 2.4 and 2.4.1 into one run (`semaudit capture … --run-id w6`), then
`python3 scripts/w8_run.py --run runs/w6 --runs 5 --max-usd 2`.

## What was graded
- **17 stories against hand-authored expected vectors**: every 2.4 persona with a W1b fixture (13), the family
  (NC4, held to Maya's vector with its own totals), Maya on 2.3 (NC6), Rina on 2.4.1, and Maya on 2.4.1 (new:
  the fixes are in, so P2 passes via the inline reconcile message and P3 passes; the regret was not on the fix list).
- **14 negative controls**: every 2.3 story without a fixture must raise nothing.
- Fixture event ids are translated to captured ids by message key, feature and time (fixtures place renders
  +5/+10 s after the action); a fixture event with no unique captured match is reported, never guessed.
- Exact on covered events; no other entry may mention a covered event or be story-level; entries on uncovered
  events (core pages, greetings) must not be violations.
- Stubs: always-conflict fails 6 stories, always-compatible 7, the all-`suggest` extractor 9.

Sample labels (run 1): Maya → `unexplained_tradeoff` ("lock for EUR 9 for 48 h … wait up to 14 days … both
live"); Kai → `conflict` ("incompatible act-now vs wait"); Lena, Maya-R, Maya 2.4.1 → `explained_tradeoff`.

## What the free dry run caught first (gold extraction + gold labels, no model)
| Finding | Fix |
|---|---|
| The confirmation page shown at 10:06:00, the same second Maya books, was judged against the state *before* the booking, so its upgrade offer read as not actionable (U3 false positive on 7 stories) | a message sees the actions of the step that produced it (`state_at(…, inclusive=True)`) |
| Sam & Alex's €30 upgrade-fee policy line was compared with their €18 *lock* charge (U2 false positive) | a fee claim is checked only against the claiming feature's own charges (`match_feature`) |
| The script graded Rina's 2.4 story against her 2.4.1 fixture | fixtures match on release |

## W7: alignment
`semaudit.story.align.align(base, head)` pairs events by `event_key` (feature / surface / message key /
occurrence; actions by action / occurrence). Leftovers pair **fuzzily** only on the same feature, surface,
channel and moment, and are marked; everything else is explicitly `added` or `removed`. Maya 2.3 → 2.4: card
and concierge reply changed (fuzzy); banner, 12:00 email, push and the upgrade tip added; the "watching" card
removed. 2.4 → 2.4.1: the stale email and push removed, the reconcile message added.

## Limits
- Development set; same author for copy, rubric, gold and vectors. The sealed benchmark is the honest test.
- A job-sent message at exactly the second of a user action is treated as after the action.
- Issue-level delta (new / pre-existing / resolved), severity, confidence and verification are W9.

## External audit (2026-10-26) and what changed
An independent review found three P0s. All were checked against the code; two were defects and were fixed
before W9, the third is the W9/W10b plan itself.

| Finding | Verdict | Change |
|---|---|---|
| No end-to-end path (issues → verification → policy → review.json → Release Story → repro) | agreed; this is W9 + W10b | conceptual work frozen until that path runs on Northbound |
| Evidence lineage lost at episode → story | **defect** | every captured message event now carries `evidence`: episode, step, capture id, element index, source locator, artifact digests, attribution method. `semaudit.verify.evidence.resolve` fails closed: missing capture, moved element, altered quote, edited artifact or a quote absent from the stored DOM/JSON all fail. All 436 captured impressions resolve |
| A reconciler after both directives expired still cleared P2 | **defect, reproduced** | a reconciler counts only if some pair's directives are BOTH live at that moment and the decision has not been made |
| Exception expiry ignored | **defect** | `expiry` is evaluated (inclusive of the expiry date) and reported beside a, b, c and scope |
| A past departure satisfied "≤ 72 h" | **defect** | the gap must be ≥ 0 and ≤ 72 h |
| Incompatible and tradeoff pairs judged as one candidate | **defect** | one candidate per feature pair, decision **and** pair kind (`…@when_to_book:tradeoff` / `:incompatible`) |
| No supersession | **defect** | a later directive from the same feature on the same decision ends the earlier one (`superseded`) |
| Unknown validity treated as live with no penalty | partly | the end stays `None` (never "forever"); every P2 entry now records each directive's liveness basis and an `unknown_validity` flag for W9's confidence |
| Text deadlines not read ("until tomorrow 10:06") | **deferred** | needs an extraction field and a model re-run; no hero case depends on it. Recorded in `validity()` |

Each fix has an adversarial test, and each test was mutation-checked (re-introducing the bug turns it red).
After the fixes the free dry run stayed 31/31, and W8 was re-run with fresh interpretation on 5 runs (cached,
unchanged extraction): **31/31 × 5, stubs fail, $0.30**.
