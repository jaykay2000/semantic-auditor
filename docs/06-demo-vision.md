# 6. Demo vision: the 3-minute video

## What the video must prove

> **The auditor builds a faithful, time-ordered experience of one user, detects a release-level conflict that the feature tests missed, shows that conflict against the owner's own rules, and reproduces it on demand.**

Everything else is supporting evidence. The **Release Story** gets the most screen time, because it *is* the product.

## Storyboard (target 2:58, about 340 spoken words, at most ~2.5 words per second)

Revised Oct 27 after an external review of the talk track: problem first, product named at 0:18; no claim that
every message is true; Maya's issue is **major** and the release is held by Kai's **conflict** (owner ruling: P2
severity per label); a 12-second architecture overlay; verification shown on a real issue with its real models;
two outcomes in the memory beat, not four. Quotes are the captured copy (`examples/northbound/README.md` table of
copy keys), not paraphrases.

| Time | Beat | On screen | Voice-over (draft) |
|---|---|---|---|
| 0:00–0:18 | **Hook** | Tag: *Northbound, fictional travel app*. Three 2.4 features, each with green checks: Fare Lock, Price Watch auto-enroll, Concierge 2.0. Then Maya's two moments, two minutes apart: 10:01 email *"Prices on your dates are likely to drop over the next two weeks. We suggest waiting; we'll tell you when to book."* → 10:03 banner *"2 seats left at this fare. Lock it for 48 h for €9 total, for your whole booking."* (The after-booking messages stay out of the hook; they appear in her Release Story.) | "Three features, three green checks. Price Watch tells Maya to wait for a lower fare. Two minutes later, Fare Lock offers to hold today's price for 48 hours. Each is valid on its own; nothing helps her weigh them. The features passed. The experience didn't." |
| 0:18–0:38 | **What it is + the owner's rules** | Title: *Semantic Auditor*. The contract review page: **P2** (coherence) and **P1** with **P1-E1** as a checklist (departs within 72 h · seat count true · tradeoff explained). The owner clicks *Approve* (real; until every item is approved the page says *provisional*). | "That's why I built Semantic Auditor. It rebuilds what one user experiences across features, screens and time, and checks it against rules the owner approves. One: features advising on the same decision must reconcile or explain the tradeoff. Another allows urgency only within 72 hours, with real seat counts, explained." |
| 0:38–1:28 | **Hero: Maya's Release Story** | `semaudit review --base 2.3 --head 2.4`. The page opens on Maya: lanes per feature, her actions on the axis. The issue detail: the two moments side by side, the P2 rule quoted, severity **major** ("rule P2 sets unexplained tradeoff at major"). Toggle **2.3 / diff**: in 2.3 she had opted in and got the same forecast email, but there was no Fare Lock offer, so nothing competed with it. The banner: **Hold**, *fired by Conflicting advice (Kai)*: the release is held for another persona, shown at 1:40. Switch to **Raj** (departs tomorrow): **P1 applies → P1-E1 met (a ✓ b ✓ c ✓)**, **P2 not applicable**. | "Here's everything 2.4 said to Maya, in order. Neither feature is broken, but together they give her two plans for one decision, and nothing explains the tradeoff. That breaks the owner's coherence rule, and it's new in 2.4. The owner rates that major. Raj gets urgency, and that's allowed: he leaves tomorrow, the seats are real, the tradeoff is explained, and nothing is telling him to wait." |
| 1:28–1:40 | **Architecture overlay** | A four-step overlay over the Release Story, then the page's model line underneath it: *Replay user journeys* (screens · email · push · user state) → *Muse Spark* (extract meaning · interpret relationships) → *Code + owner-approved rules* (time · state · candidate conflicts · exceptions) → *Verification → Release Story* (challenge · reproduce · recommend). No PDFs: Northbound sends none. | "Under the hood, we replay real user journeys. Muse Spark reads what each message means and how messages relate; code tracks time, state and the owner's rules." |
| 1:40–2:08 | **Why you can trust it** | Maya's verification panel, real statuses: ✓ Replayed · ✓ Evidence linked to captures · ✓ Second model (muse-spark-1.2, same family) 3/3 · ✓ Argued against (muse-spark-1.2) no defense held · – oracle not applicable. Run `semaudit repro` live. Then **Kai**: "Book now" against "wait", **Conflicting advice, critical**, the issue that holds the release. Then **Lena** on the not-raised list: cleared as an explained tradeoff. (The factual layer, Sam & Alex charged €18 against €9 shown and Omar's false seat count, may sit in the rail unnarrated.) | "Every finding is replayed, tied to its evidence, re-derived by a second model, and argued against. Here that's another Muse Spark version, the same family, so it's a second pass and confidence stays medium; when models disagree, we say so. It also tells a tradeoff from a contradiction: Kai is told to book now and to wait. That's critical, and it holds the release. Lena's concierge explained the tradeoff, so hers is cleared." |
| 2:08–2:28 | **Fair benchmark** | The benchmark panel: the same model given the same stories, rules and release notes (one-shot and budget-matched multi-pass) against the auditor, on sealed releases, the two strongest honest measures with denominators. | "Couldn't a capable model just review the release? We gave the same model the same context, on releases neither had seen. [Numbers as measured.]" |
| 2:28–2:43 | **A real product** | Tag: *Finablo, app under audit (existing product, not part of this submission)*. **What the auditor was given** beside **What the team learned later**; R1: the 61-year-old whose pending page states a different 401(k) maximum than the export, labelled *blind* or *given a target persona*, whichever is true. If R1 does not hold up, this beat goes to Northbound. | "On a real product, given only what the team had written down at the time, it found an issue the team discovered after it shipped." |
| 2:43–2:58 | **Decision and memory** | On 2.4 the owner marks Maya's tradeoff *fix*. On 2.4.1: Maya's issue shows **fix confirmed**; the concierge now says *"Prices on your dates are likely to drop, but this fare has 2 seats left. If you can move your dates, wait for the alert; if not, locking protects this price."* Rina's urgent hotel banner meets every condition of P1-E1 and is still raised: *nearest exception does not apply: scope (hotel)*. (Kai is not shown here: on 2.4.1 the models disagree, so the page says *needs owner review*, and that is the only honest label for it.) Closing card: repo URL · open source · Muse Spark. | "Owner decisions are remembered, and checked. Maya's fix is confirmed, not assumed. And permission for flights doesn't spread to hotels. Semantic Auditor: review the release your users actually live." |

**Two different contributions, never conflated on screen.** Cross-model verification (1:40) makes each finding
more trustworthy. The benchmark (2:08) asks whether the whole auditor adds value beyond a capable general-purpose
model given the same context. Say which one a number belongs to.

**Name the models exactly as the review's manifest records them.** Today every role is Muse Spark (the reader
1.3, the second model and the defender 1.2), one family: say *second pass*, never *independent agreement*. If a
different family is added later (an open-weights Muse Spark host, or another provider), the page and the voice-over
change because the manifest does, not because the script does.

**Before recording narration:** show the first 90 seconds of a rough cut, without narration, to one engineer or
product person unfamiliar with the project. Ask what Maya experienced, what the auditor found, and why that could
not be found by checking each message's facts. If they cannot answer, simplify the visuals before adding words.

**Not scripted in advance:** issue counts, severities and benchmark numbers. The script says what *kind* of thing appears; the screen shows whatever the run actually produced. If a beat's real output does not support its voice-over, the voice-over changes, not the output.

**The hero is deliberately free of factual errors.** Both messages in Maya's hero issue are true (forecast and
inventory); her later messages carry other, separate issues (stale guidance after booking, second-guessing). The false seat count and the fee mismatch are shown separately, as the factual layer, so the hero demonstrates the one thing no single-feature test can see.

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

1. The factual layer goes unnarrated, then off screen.
2. The Finablo beat: R1 only, and dropped if it does not hold up (it never blocks the video).
3. The benchmark panel: the two strongest *honest* measures.
4. The 2.4.1 hotel-scope moment; keep "fix confirmed".

The hook, the owner's rules, Maya's story, Raj's rule panel, the verification panel with the live repro, and Kai
against Lena are **never cut**. Kai stays because he is the proof that a tradeoff and a contradiction are told
apart, and he is what holds the release.

## Artifacts this requires

| Artifact | Beat |
|---|---|
| Northbound 2.3 / 2.4 / 2.4.1 with the persona and clock hooks | all |
| Written rules (U1, P1, P1-E1, P2) → contract review page; voice onboarding optional | 0:18 |
| Release Story view: lanes, actions, state, relation, issue detail, diff toggle, persona switch, policy "fired by" | 0:38 |
| Architecture overlay (video edit only; the page's model line is real) | 1:28 |
| Verification panel; `semaudit repro`; the *not raised* list | 1:40 |
| Frozen benchmark results; baseline outputs | 2:08 |
| Finablo onboarding from dated inputs; R1 (and R2 if adjudicated) | 2:28 |
| Dispositions → 2.4.1 review | 2:43 |
