# 6. Demo vision: the 3-minute video

## What the video must prove

> **The auditor builds a faithful, time-ordered experience of one user, detects a release-level conflict that the feature tests missed, shows that conflict against the owner's own rules, and reproduces it on demand.**

Everything else is supporting evidence. The **Release Story** gets the most screen time, because it *is* the product.

## Storyboard (target 2:55)

| Time | Beat | On screen | Voice-over (draft) |
|---|---|---|---|
| 0:00–0:18 | **Hook** | Three Northbound 2.4 features, each with its own green checks: Fare Lock, Price Watch auto-enroll, Concierge 2.0. Then Maya's phone, in order: *"Prices may drop. We'll tell you when to book."* → *"Only 2 seats left. Lock it for €9."* → after booking: *"We'll tell you when to book"* → day 2, concierge: *"You should have booked refundable."* | "Every feature in this release passed its tests. Together they tell Maya to wait, to hurry, and, after she's paid, that she chose wrong. Every feature passed. The release still failed its users." |
| 0:18–0:45 | **The owner's intent** | A 12-second clip of the owner's voice note → transcript → the drafted principle **P1** and its exception **P1-E1**, with conditions shown as checkable items → the owner clicks *Approve*. | "First the auditor learns what the owner wants. Not 'never pressure anyone', but a rule it can test: no manufactured urgency for flexible travellers; verified, explained urgency is fine for time-sensitive trips." |
| 0:45–1:40 | **Hero: the Release Story** | `sra review --base 2.3 --head 2.4`. Open **Maya's Release Story** (screen spec below). Time runs left to right, one lane per feature, with her actions on the axis. Click the top issue: the two conflicting moments enlarge side by side, the principle card quotes the owner, and evidence chips appear. Toggle **2.3 / 2.4**: in 2.3 her story had one alert and no conflict. The recommendation banner reads whatever the run produced (e.g. *Hold*), with severity, confidence and verification as three separate chips. Then switch persona to **Raj**: the same banner, marked *allowed by P1-E1*, each condition ticked. | "Here's everything 2.4 said to Maya, in order. Two features give her opposite advice about the same decision, and the scarcity claim doesn't match inventory. That breaks the owner's rule, and it's new in this release. Raj sees the same banner, and that's fine: his trip is tomorrow, the seats are real, and the tradeoff is explained. Same message, different user, different verdict." |
| 1:40–2:10 | **Why you can trust it** | Run `sra repro <issue>` live: the episode replays and the same events appear. Then the **rejected** list: the concierge's "book now or wait?" answer, a candidate that verification rejected as an explained tradeoff. Then the **benchmark panel**: the same model given the same stories, principles and release notes, against the auditor on the frozen set, shown with denominators (coverage, precision, recall, negative-control false alarms, run-to-run stability). | "It reproduces on demand. It shows what it threw out, and why. And against the same model given the same context, here's what we measured on releases neither system had seen." *(Numbers spoken exactly as measured.)* |
| 2:10–2:40 | **A real product** | Tag: *Finablo, app under audit (existing product, not part of this submission)*. A panel: **What the auditor was given** (the vision and principles as of that date, synthetic personas, two builds) beside **What the team knew later** (the bug report). Then the finding in a Finablo Release Story: R1, the 61-year-old whose pending page states a different 401(k) maximum than the export, and R2 if it passed adjudication. | "On a real product, given only what the team had written down at the time, the auditor found the issue the team discovered after it shipped." |
| 2:40–2:55 | **Decision and memory** | The owner marks Maya's issue *fix*, and accepts a scoped exception for one minor issue. Then the 2.4.1 review: the fixed issue shows *resolved*; Fare Lock's new hotel placement for a flexible traveller is still raised, with *"nearest exception does not apply"*. Closing card: repo URL · open source · Muse Spark · Muse Spark Open · Muse Voice Transcribe. | "Decisions are remembered, but scoped. An exception for Raj never becomes a licence for Maya. The Semantic Release Auditor: review the release your users actually live." |

**Not scripted in advance:** issue counts, severities and benchmark numbers. The script says what *kind* of thing appears; the screen shows whatever the run actually produced. If a beat's real output does not support its voice-over, the voice-over changes, not the output.

## The Release Story screen (the hero; design before build)

The viewer should understand four things **without the narration**: what Maya experienced and in what order; which features collided; why the owner's rule calls it a problem; and what changed since the last release.

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ Maya · solo · flexible dates · departs in 42 days        Release [2.3] [2.4●] [diff]        │
│ Recommendation: ⟨whatever the release policy computes⟩   Owner decision: pending            │
├───────────────────────────────────────────────────────────────────────┬───────────────────┤
│ time ►   D0 10:00     10:03        10:06          12:00         D2 09:02  │ ISSUES            │
│ actions   ● search    ● open fare  ● booked (non-refundable)              │ ▸ Competing advice│
│ Price Watch  [wait for a drop]──┐               [we'll tell you when…]    │   major · high ·  │
│ Fare Lock            [only 2 seats! €9]──┘ conflict                       │   verified · NEW  │
│ Concierge                                            [you should have…]   │ ▸ Stale guidance  │
│ Core       [results] [fare] [checkout €12] [confirmed]                    │ ▸ Fee €9 vs €12   │
│ state     browsing ─────────────────────► booked · non-refundable ──────► │ ▸ …               │
├───────────────────────────────────────────────────────────────────────┴───────────────────┤
│ ISSUE DETAIL (opens on click)                                                               │
│ ┌ moment A ──────────────┐   ┌ moment B ──────────────┐   Owner principle P1 (core)        │
│ │ D0 10:01 · Price Watch │ ⇄ │ D0 10:03 · Fare Lock   │   "We do not manufacture scarcity  │
│ │ screenshot, highlighted│   │ screenshot, highlighted│    or use urgency to pressure      │
│ │ "Prices may drop…"     │   │ "Only 2 seats left…"   │    flexible travellers…"           │
│ └────────────────────────┘   └────────────────────────┘   source: voice note 0:12          │
│ Why: both are live for the same decision (when to book); Maya is flexible; the "2 seats"     │
│      claim does not match inventory (9).   Exception P1-E1: time-sensitive ✗                │
│ Severity: major (money · core principle · pre-purchase · 2/8 personas)                       │
│ Confidence: high · Verification: reproduced ✓ evidence ✓ cross-model ✓ defended ✓            │
│ Delta: new in 2.4 (features changed: fare_lock, price_watch)   ▶ sra repro I-2.4-maya-03      │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

**Interactions:**
1. Clicking an issue highlights its events on the timeline, draws the relation and opens the detail.
2. The `diff` toggle overlays 2.3, ghosted above 2.4, with added and changed events marked.
3. Switching persona keeps the same lanes and time scale, so Raj's *allowed* banner sits exactly where Maya's *conflict* sat.
4. Every quote is the exact captured text. Clicking a moment opens the full capture.

**Design constraints:** readable at 1080p on a laptop; one lane per feature, colour by feature; severity, confidence and verification are separate chips, never merged into one colour. Tone tokens: severity uses a warm scale; verification uses check marks, never colour alone.

**Process:** design spec first (design pass + wireframe), owner approval, then build. It is the first UI built, and gets the most polish.

## Production rules

- **Real output only.** Every screen comes from a committed run that `sra repro` can replay. The baseline's output is shown verbatim.
- **Label provenance.** A corner tag *"built during the hackathon"* goes on the auditor's screens and *"app under audit"* on Finablo's. Northbound is labelled fictional, and 2.4 is labelled as the demo release, not the benchmark.
- **Honest numbers.** Denominators are on screen. If the baseline wins a measure, the panel shows it.
- Pre-recorded runs, replayed from cache at real speed; sped-up segments are labelled. Captions are burned in.

## Cut order if time is short

1. Shorten the Finablo beat to R1 only (always kept: real-product validation).
2. Reduce the benchmark panel to the two strongest *honest* measures.
3. Drop the 2.4.1 hotel-scope moment; keep "fixed → resolved".

The hook, the owner rule with its exception, Maya's story, Raj's allowed banner, and the live repro are **never cut**.

## Artifacts this requires

| Artifact | Beat |
|---|---|
| Northbound 2.3 / 2.4 / 2.4.1 with the persona and clock hooks | all |
| Voice note → P1 and P1-E1 draft → contract review page | 0:18 |
| Release Story view: lanes, actions, state, relation, issue detail, diff toggle, persona switch | 0:45 |
| `sra repro`; the rejected-candidates list | 1:40 |
| Frozen benchmark results; baseline outputs | 1:40 |
| Finablo onboarding from dated inputs; R1 (and R2 if adjudicated) | 2:10 |
| Dispositions → 2.4.1 review | 2:40 |
