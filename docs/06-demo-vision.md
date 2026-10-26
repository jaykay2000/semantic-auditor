# 6. Demo vision: the 3-minute video

## What the video must prove

> **The auditor builds a faithful, time-ordered experience of one user, detects a release-level conflict that the feature tests missed, shows that conflict against the owner's own rules, and reproduces it on demand.**

Everything else is supporting evidence. The **Release Story** gets the most screen time, because it *is* the product.

## Storyboard (target 2:55)

| Time | Beat | On screen | Voice-over (draft) |
|---|---|---|---|
| 0:00–0:18 | **Hook** | Three Northbound 2.4 features, each with its own green checks: Fare Lock, Price Watch auto-enroll, Concierge 2.0. Then Maya's screens, in order: *"Prices on your dates are likely to drop. We suggest waiting; we'll tell you when to book."* → *"2 seats left at this fare. Lock it for 48 h for €9 total, for your whole booking."* → after booking: *"Keep waiting to book. We'll tell you when prices drop."* → day 2, concierge: *"You should have booked refundable."* | "Every feature in this release passed its tests, and every one of these messages is true. Together they hand Maya two plans minutes apart, wait or lock in, and nothing helps her weigh them. Every feature passed. The release still failed its users." |
| 0:18–0:45 | **The owner's rules** | The written rules page: **P2**, the coherence rule ("features advising on the same decision must agree or explain the tradeoff"); **P1** with its exception **P1-E1**, conditions shown as a checklist (departs within 72 h · seat count true · tradeoff explained). The owner clicks *Approve*. (If voice onboarding is ready by then, a 10-second voice clip precedes this; it is optional.) | "First, the owner's rules, in a form a machine can test. One is about the relationship between features: if two of them advise on the same decision, the product must reconcile them or explain the tradeoff. Another allows urgency, but only for trips departing within days, with real seat counts, explained." |
| 0:45–1:40 | **Hero: the Release Story** | `semaudit review --base 2.3 --head 2.4`. Open **Maya's Release Story** (screen spec below): time left to right, one lane per feature, her actions on the axis. Click the top issue: the two moments enlarge side by side, each tagged **true** (forecast ✓, inventory ✓); the P2 card quotes the rule; evidence chips appear. Toggle **2.3 / 2.4**: in 2.3 there was one alert and no conflict. The recommendation banner shows whatever the policy computed, with severity, confidence and verification as three separate chips. Then switch to **Raj** (departs tomorrow): the urgent banner sits in the same lane, with the rule panel reading **P1 applies → P1-E1 met (a ✓ b ✓ c ✓)** and **P2 not applicable**: Price Watch forecasts no drop before his departure. | "Here's everything 2.4 said to Maya, in order. Both messages are true, and neither feature is broken. But two features give her two plans for the same decision. Waiting and locking can coexist, but the lock expires long before the drop window, and nothing tells her that. That breaks the owner's coherence rule, and it's new in this release. Raj gets urgency, and that's allowed: his trip is tomorrow, the seats are real, the tradeoff is explained, and nothing is telling him to wait." |
| 1:40–2:10 | **Why you can trust it** | Run `semaudit repro <issue>` live: the episode replays and the same events appear. A quick flash of **Kai**: permitted urgency ("Book now"), while Price Watch says wait. That is an *incompatible* pair, so P2 is raised as a **conflict** ("an exception to one rule never excuses another"). The **not raised** list: Lena's story, where the concierge reconciled both recommendations, cleared as an explained tradeoff. A strip showing the **factual layer** separately: Sam & Alex shown €9 for a lock and charged €18, and Omar's false seat count. Then the **benchmark panel**: the same model with the same stories, rules and release notes (one-shot and budget-matched multi-pass), against the auditor on the frozen set, with denominators. | "It reproduces on demand. It tells a tradeoff from a contradiction, and permission for one thing isn't permission for everything. It shows what it cleared, and why. It still catches plain factual errors, as a separate layer. And here's what we measured against the same model, given the same context, on releases neither had seen." *(Numbers spoken exactly as measured.)* |
| 2:10–2:40 | **A real product** | Tag: *Finablo, app under audit (existing product, not part of this submission)*. A panel: **What the auditor was given** (the vision and principles as of that date, synthetic personas, two builds; no voice note) beside **What the team knew later** (the bug report). Then the finding in a Finablo Release Story: R1, the 61-year-old whose pending page states a different 401(k) maximum than the export, labelled *blind discovery* or *given a target persona*, whichever is true. R2 appears only if it passed adjudication. | "On a real product, given only what the team had written down at the time, the auditor found an issue the team discovered after it shipped." |
| 2:40–2:55 | **Decision and memory** | The owner marks Maya's issue *fix*, and accepts a scoped exception for one minor issue. Then the 2.4.1 review: the fixed issue shows *resolved*; Rina's urgent hotel banner meets every condition of P1-E1 (within 72 h, room count verified, tradeoff explained) and is still raised, because hotels are outside the exception's scope: *"nearest exception does not apply: scope (hotel)"*. Closing card: repo URL · open source · Muse Spark · Muse Spark Open. | "Decisions are remembered, but scoped. Permission granted for one place never silently spreads. The Semantic Auditor: review the release your users actually live." |

**Not scripted in advance:** issue counts, severities and benchmark numbers. The script says what *kind* of thing appears; the screen shows whatever the run actually produced. If a beat's real output does not support its voice-over, the voice-over changes, not the output.

**The hero is deliberately free of factual errors.** Every message in Maya's hero conflict is true. The false seat count and the fee mismatch are shown separately, as the factual layer, so the hero demonstrates the one thing no single-feature test can see.

## The Release Story screen (the hero; design before build)

The viewer should understand four things **without the narration**: what Maya experienced and in what order; which features collided; why the owner's rule calls it a problem; and what changed since the last release.

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│ Maya · solo · flexible dates · departs in 42 days        Release [2.3] [2.4●] [diff]        │
│ Recommendation: ⟨whatever the release policy computes⟩   Owner decision: pending            │
├───────────────────────────────────────────────────────────────────────┬───────────────────┤
│ time ►   D0 10:00     10:03        10:06          12:00         D2 09:02  │ ISSUES            │
│ actions   ● search    ● open fare  ● booked (non-refundable)              │ ▸ Unexplained     │
│ Price Watch  [likely to drop · wait]─┐          [we'll tell you when…]    │   tradeoff (P2)   │
│ Fare Lock            [2 seats · lock €9]┘ P2 tradeoff                     │   · verif · NEW   │
│ Concierge                                            [you should have…]   │ ▸ Stale guidance  │
│ Core       [results] [fare] [checkout] [confirmed]                        │ ▸ U4 post-purchase│
│ state     browsing ─────────────────────► booked · non-refundable ──────► │ FACTUAL LAYER     │
│                                                                           │ (other personas)  │
├───────────────────────────────────────────────────────────────────────┴───────────────────┤
│ ISSUE DETAIL (opens on click)                                                               │
│ ┌ moment A ──────────────┐   ┌ moment B ──────────────┐   Rule P2 · coherence · core        │
│ │ D0 10:00 · Price Watch │ ⇄ │ D0 10:03 · Fare Lock   │   "When more than one feature gives │
│ │ screenshot, highlighted│   │ screenshot, highlighted│    an active recommendation about   │
│ │ "likely to drop…"      │   │ "2 seats left…"        │    the same decision…"              │
│ │ true ✓ (forecast)      │   │ true ✓ (inventory 2)   │   source: principles draft §2       │
│ └────────────────────────┘   └────────────────────────┘                                     │
│ Why: wait_for_drop (live since 10:00, not booked) and lock_fare (10:03): same decision,       │
│      different features, compatible but material tradeoff (lock expires in 48 h; drop window │
│      14 days); nothing explains it to Maya.                                                  │
│ Other rules: P1 not applicable (suggest, no urgency cue) · U1 passed (claims true)          │
│ Severity ⟨level + factors⟩ │ Confidence ⟨level + basis⟩ │ Verification ⟨steps ✓/✗⟩            │
│ Delta: new in 2.4 (features changed: price_watch, fare_lock)    ▶ semaudit repro I-2.4-maya-01│
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

**Interactions:**
1. Clicking an issue highlights its events on the timeline, draws the relation and opens the detail.
2. The `diff` toggle overlays 2.3, ghosted above 2.4, with added and changed events marked.
3. Switching persona keeps the same lanes and time scale, so Raj's *allowed* urgent banner sits where Maya's banner sat, with every rule's evaluation listed (applied, excepted, not applicable, passed).
4. Every quote is the exact captured text. Clicking a moment opens the full capture.

**Design constraints:** readable at 1080p on a laptop; one lane per feature, colour by feature; severity, confidence and verification are separate chips, never merged into one colour; release-level issues and the factual layer are visually separate in the issue rail. Tone tokens: severity uses a warm scale; verification uses check marks, never colour alone.

**Process:** design spec first (design pass + wireframe), owner approval, then build. It is the first UI built, and gets the most polish.

## Production rules

- **Real output only.** Every screen comes from a committed run that `semaudit repro` can replay. The baseline's output is shown verbatim.
- **Label provenance.** A corner tag *"built during the hackathon"* goes on the auditor's screens and *"app under audit"* on Finablo's. Northbound is labelled fictional, and 2.4 is labelled as the demo release, not the benchmark.
- **Honest numbers.** Denominators are on screen. If the baseline wins a measure, the panel shows it.
- Pre-recorded runs, replayed from cache at real speed; sped-up segments are labelled. Captions are burned in.

## Cut order if time is short

1. Shorten the Finablo beat to R1 only (always kept: real-product validation).
2. Reduce the benchmark panel to the two strongest *honest* measures.
3. Drop the 2.4.1 hotel-scope moment; keep "fixed → resolved".

The hook, the coherence rule plus P1 with its exception, Maya's story, Raj's rule panel, and the live repro are **never cut**. The factual strip is the first thing to shrink; Kai stays, because he is the proof that a tradeoff and a contradiction are told apart.

## Artifacts this requires

| Artifact | Beat |
|---|---|
| Northbound 2.3 / 2.4 / 2.4.1 with the persona and clock hooks | all |
| Written rules (U1, P1, P1-E1, P2) → contract review page; voice onboarding optional | 0:18 |
| Release Story view: lanes, actions, state, relation, issue detail, diff toggle, persona switch | 0:45 |
| `semaudit repro`; the *not raised* list | 1:40 |
| Frozen benchmark results; baseline outputs | 1:40 |
| Finablo onboarding from dated inputs; R1 (and R2 if adjudicated) | 2:10 |
| Dispositions → 2.4.1 review | 2:40 |
