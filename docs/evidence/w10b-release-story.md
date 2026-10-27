# W10b: the Release Story page (2026-10-26)

**Result: built to the approved spec** ([design/release-story.md](../design/release-story.md)) and generated
from `review.json` by every `semaudit review` (or `semaudit report <review.json>`). One static HTML file with
inline JS and CSS plus the captures it shows: no server, no build step, hostable anywhere.

Open the demo review: `open runs/e2e-1/report-2.3-2.4/index.html` (after `semaudit review --base 2.3 --head 2.4`).

## What it shows (the spec's four facts)
1. **What Maya experienced, in order**: columns are scenario steps with exact times and gap markers; her actions
   on top; one lane per feature (colour = feature); the derived state lane; live intervals as bars.
2. **Which features collided**: the top issue is selected on open; its moments get A/B rings and an elbow
   connector (dashed for a tradeoff, solid for a conflict); the rail names the features.
3. **Why the owner's rule calls it a problem**: the detail quotes the rule and its source, gives the
   one-sentence why, every other rule on the same moments, and severity, confidence and verification in three
   separate boxes (verification lists each step ✓/✗/○).
4. **What changed since the last release**: the `diff` toggle ghosts the base story above each lane with
   `+ added`, `≈ changed`, `− removed` badges; each issue carries NEW / PRE-EXISTING; resolved issues are listed.

Also: the decision bar shows the policy's recommendation and the row that fired, verbatim; persona switch keeps
the columns (Raj's banner sits where Maya's sat); a persona with nothing raised gets its **rule panel** (Raj:
"P1 applies → a ✓ departs 29 h 57 m 00 s after the message (≤ 72 h) · b ✓ · c ✓ · scope ✓ · expiry ✓ →
excepted", then every rule, "P2 not applicable"); the factual layer is a separate block linking to its stories;
the not-raised list gives each reason; each moment shows the capture crop with the element highlighted (click
for the full capture) and the exact quote; `semaudit repro <id>` is copyable; deep links (`#persona=kai&issue=…`)
open on that issue.

## Decisions taken while building (recorded, within the approved design)
- Columns are the hero's scenario steps plus the current persona's, not every step of every scenario (twelve
  columns made the cards unreadable); alignment across personas is kept because the hero's columns stay.
- The page opens on the most severe release-level issue, coherence first, on the persona the contract marks
  `role: hero`.
- Owner disposition buttons are shown disabled until W11 records dispositions.

## Tests (Chromium, from real captures, no model)
Hero opens on Maya with both moments ringed, the rule, the three boxes and the repro command, and every quote is
the exact captured text; Raj shows "Nothing raised" and his rule panel; diff marks added and removed; a deep link
opens Kai's conflict; the page is self-contained (no external scripts, every referenced capture copied);
2.4 → 2.4.1 lists the resolved issues. No console errors. Four mutation checks turn the suite red.
Checked by hand at 1600×1000 and 375×812 (no page-level horizontal scroll; the timeline scrolls in its box).

## Limits
- The capture crop scales a 1280-px page into the card, so the page text in the crop is small; the quote below
  it is the readable source of truth.
- The acceptance test with someone who has not seen the project (state the four facts from a silent recording)
  belongs to W16, when the recording exists.
