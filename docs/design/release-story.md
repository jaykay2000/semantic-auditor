# Release Story screen: design spec (W10a)

Status: **draft, awaiting owner approval** (approval gates W10b). The wireframe (three screens: Maya on 2.4 with the top issue selected, Raj after a persona switch, Maya in diff mode; private link given to the owner) is the visual companion to this spec; where the two disagree, this spec wins and the wireframe is corrected.

## Job of the screen

A viewer who has never seen the project should be able to state four facts **from a silent recording**:

1. **What this user experienced, and in what order.**
2. **Which features collided.**
3. **Why the owner's rule calls it a problem.**
4. **What changed since the last release.**

Everything on the screen serves one of those four, or the shipping decision. Anything else is cut or moved behind a click.

## Regions

```
┌ HEADER: persona · trip facts · release switch [2.3][2.4●][diff] · persona switch ─────────────┐
├ DECISION BAR: recommendation (policy result + the policy line that fired) · owner decision ────┤
├ STORY (left, ~70%) ─────────────────────────────────────────┬ ISSUE RAIL (right, ~30%) ────────┤
│ time axis: scenario steps, exact times, gap markers          │ RELEASE-LEVEL  (this persona)   │
│ lane: this user's actions                                    │   issue rows                    │
│ lane per feature (colour = feature)                          │ FACTUAL LAYER  (separate block) │
│ lane: derived state (booking status, fare type)              │ NOT RAISED     (cleared + why)  │
├ ISSUE DETAIL (opens under the story when an issue is selected) ───────────────────────────────┤
│ moment A ⇄ moment B (exact captured text, capture thumbnail, claim truth chips)                │
│ rule card (quoted text + source) · Why (one sentence, generated from the relation) ·           │
│ other rules on these moments · severity │ confidence │ verification · delta · repro command    │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Header
- Persona name, party, flexibility, **departure relative to the first event** ("departs in 42 days"), and the exact departure timestamp on hover.
- Release switch: `2.3`, `2.4`, `diff`. Persona switch: a menu listing every persona in the run, each with its count of raised issues.
- Corner tag on every auditor screen: *built during the hackathon*. Northbound screens also carry *fictional app*; Finablo screens *app under audit*.

### Decision bar
- **Recommendation** is exactly what the release policy computed (`Hold` / `Needs owner review` / `Ship with notes` / `Ship`), followed by the policy line that fired, verbatim ("any verified release-level issue new in head → Hold"). Never hand-set.
- **Owner decision**: `pending` until the owner acts; then the disposition and who/when.

### Story: the time axis (decision)
Events in one scenario span minutes and then days (Maya: 10:00–10:06, then 12:00, 18:00, D2 09:02). A linear axis would stack the hero moments into one pixel. So:
- The axis is **ordinal by scenario step**: each step gets a column; events within a step share its column, ordered top-to-bottom by exact time.
- Each column header shows the exact simulated time (`D0 10:03:00`); between columns a **gap marker** shows elapsed time (`+1 h 54 m`) when it exceeds 10 minutes.
- Columns are keyed by **scenario step**, not by clock time, so switching persona keeps the same columns: Raj's urgent banner lands in the column where Maya's banner sat (interaction 3).
- Liveness: a directive's live interval (its validity window, from the contract lifetimes and preconditions) is drawn as a thin bar extending right from the event to where it ends (or to the edge with an `→ open` cap when the end is unknown). Liveness is what makes two directives "both live", so it must be visible.

### Story: lanes
- Top lane: **this user's actions** (search, open fare, booked non-refundable, asked a question). Neutral ink, filled dot.
- One lane per feature that produced a message for this persona, in contract order: Price Watch, Fare Lock, Concierge, then Core. Each message is a card with: channel icon (page / email / push / chat), a ≤ 60-char excerpt of the exact text, the message key in mono on hover.
- Bottom lane: **derived state** (`not booked` → `booked · non-refundable`, change window open/closed). Drawn as a segmented band.
- Colour = feature, consistently across all screens: Price Watch blue, Fare Lock teal, Concierge violet, Core grey. Feature colour is never used for severity.

### Issue rail
Three visually separate blocks, in this order:
1. **Release-level issues for this persona.** Row: rule id + kind label (`Unexplained tradeoff · P2`), the features involved as colour dots, delta tag (`NEW` / `PERSISTS` / `RESOLVED`), and three small separate chips: severity, confidence, verification. Sorted by severity, then delta (new first).
2. **Factual layer**: claim-vs-oracle issues, including those in other personas' stories (Sam & Alex's €9 shown vs €18 charged, Omar's seat count), each linking to its persona. Different header and background tint, so the hero conflict is never confused with a factual error.
3. **Not raised**: candidates the auditor evaluated and cleared, each with its reason ("explained tradeoff: concierge reconciled at 10:04:10, before she decided"; "P1 excepted: P1-E1 a ✓ b ✓ c ✓"). Collapsed by default to a count; expanded in the video for Lena.

### Issue detail
Opens under the story when an issue is selected; the selected issue's events get a highlight ring on the timeline and a connector is drawn between them (solid for `conflict`, dashed for `unexplained_tradeoff`).
- **Moments**: one card per subject event (two for a P2 pair, one for most others). Each shows: time · feature · surface; the capture thumbnail with the message's locator box highlighted; the **exact captured text**, quoted; and truth chips for each claim (`forecast ✓`, `inventory 2 ✓`, or `✗ contradicted: inventory 9`). Clicking a moment opens the full capture.
- **Rule card**: rule id, kind (`coherence`), the quoted owner text, and its source (`principles draft §P2`). For exception cases, the condition checklist (`a ✓ b ✓ c ✓ scope ✗`) with each condition's measured value (`72 h 00 m 30 s > 72 h`).
- **Why**: one sentence assembled from the relation fields (actions, pair type, live intervals, missing reconciler), not free prose: "`wait_for_drop` (Price Watch, live since 10:00, not booked) and `lock_fare` (Fare Lock, 10:03) are compatible actions with a material tradeoff (lock 48 h vs drop window 14 days); nothing explained it before she booked at 10:06."
- **Other rules on these moments**: every rule evaluated on the same events with its status (`P1 not applicable · suggest, no urgency cue`, `U1 passed · claims true`). This is what lets Raj's screen say "allowed".
- **Severity │ Confidence │ Verification**: three separate boxes, never one colour.
  - Severity: level + the factors that set it.
  - Confidence: level + its basis (model agreement, cross-model, lexicon agreement on strength cue).
  - Verification: the five steps with ✓ / ✗ / `not run` each: reproduced, evidence linked, cross-model, defended, oracle checked (facts only). Status word beside it (`verified`, `partially verified`…).
- **Delta**: `new in 2.4` / `persists from 2.3` / `resolved`, with the features whose change produced it.
- **Repro**: the exact command, `semaudit repro <issue-id>`, copyable.

## Diff mode
`diff` overlays the base release's story for the same persona, ghosted (40% opacity) above each head lane, aligned by `event_key`. Head events carry `+ added` or `~ changed` badges; base-only events show `− removed`. Fuzzy alignments (no message key) carry a `≈` mark. The issue rail shows each issue's delta. In Maya's case the diff shows: 2.3 had one opt-in alert email and no Fare Lock lane; 2.4 added the card, the banner, the post-booking email, the push and the concierge tip.

## States (every one designed)
- **No issues for this persona**: the rail's first block reads "Nothing raised for Raj in 2.4" and the *Not raised* block opens by default, showing each rule evaluated and why it passed or was excepted. This is Raj's screen.
- **Could not measure**: an issue or check whose locator broke shows `could not measure` in grey with the reason; the decision bar then reads `Needs owner review` if policy says so. Never shown as passed.
- **Unverified / partially verified**: shown as such in the verification box; no styling makes an unverified issue look final.
- **Loading / empty run**: the page is static per run, so there is no loading state; an empty run shows the header and "No stories in this run".
- **Long text**: excerpts truncate on the timeline only; the detail always shows the full exact text.

## Visual system
- Light theme for the recording (1080p laptop): ground `#F6F6F3`, panels white, ink `#15171C`, secondary ink `#5B606B` (4.5:1 on white), hairline `#E2E2DC`.
- Type: Inter for UI (13–15 px body, 20 px persona name), JetBrains Mono for timestamps, message keys, rule ids and the repro command.
- Feature colours (blue / teal / violet / grey) differ in lightness as well as hue. Severity: a warm scale with the level always written as a word. Verification: check marks and words, never colour alone.
- Minimum text 12 px; nothing that must be read in the video is under 13 px at 1920×1080.

## Data the page reads (W10b contract)
One JSON per run, `review.json`, from which the static page is generated:
- `release {base, head}`, `policy {recommendation, rule_fired}`, `owner_decision`.
- `personas[]`, each with `trip`, `steps[] {step_id, at}`, `events[] {event_key, id, step_id, at, kind, feature, surface, channel, text, message_key, capture_ref, locator, live_until | open, delta, base_event_key}`, `state[] {from, to, label}`.
- `issues[] {id, persona, layer: release|factual, rule, label, subjects[], severity {level, factors[]}, confidence {level, basis[]}, verification {status, steps{…}}, delta, why, rule_text, rule_source, conditions[], other_rules[], repro}`.
- `not_raised[] {persona, rule, subjects[], status, label, reason}`.
Nothing on the screen is computed in the page except layout; every word and value comes from this file.

## Acceptance (W10b)
Someone who has not seen the project watches a silent 30-second recording of Maya's screen (select top issue, toggle diff, switch to Raj) and states the four facts. Plus: every quote matches the capture byte for byte; switching persona keeps columns; severity, confidence and verification never merge.

## Out of scope for the MCV
Editing rules from this screen, multi-release history beyond base/head, mobile layout (the page must not break below 1024 px, but is designed for desktop).
