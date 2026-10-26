# 6. Demo vision: the 3-minute video

The demo is designed first. Everything in the minimum compelling version exists to make these three minutes true, using **real run output only**, with no mock screens.

## What the judges must leave believing

1. **It finds bugs that tests and a frontier model with a prompt both miss.** We show this with a scoreboard, not a claim.
2. **It learned the product; nobody hand-wrote the rules.** Onboarding visibly turns an app plus a voice note into a contract.
3. **It is honest.** It shows what it rejected and why. It separates intended changes from bugs.
4. **It works on a real product**, not only on our demo app.
5. **Meta's models do distinct, essential jobs** (Muse Spark, Muse Spark Open, Voice Transcribe, SAM 3.1).
6. **Everything shown was built during the hackathon.** Finablo appears only as the app *under audit*, and is labelled so on screen.

## The hook

> "This release passed every test. It also told the same traveller two different prices."

Open on a split screen. Left: the checkout, **€1,284**. Right: the confirmation email, **€1,248**. Both look fine on their own.

## Script (target 2:55)

| Time | Beat | On screen | Voice-over (draft) |
|---|---|---|---|
| 0:00–0:12 | **Hook** | Split screen: checkout vs email; a CI badge reading "312 tests passed" | "This release passed every test. It still tells one traveller two different prices. Functional QA checks that screens work. Nothing checks that they agree." |
| 0:12–0:22 | **What it is** | Title card: Semantic Release Auditor, open source, built on Meta models | "So we built an auditor for meaning. It learns your product, then checks every release for contradictions, false claims and advice that's wrong for the user." |
| 0:22–0:55 | **Onboarding** | `sra onboard` against Northbound: the explorer agent clicking through (sped up), a 15-second clip of the owner's voice note, its transcript, then the contract review page filling in with surfaces, facts, oracles and plain-English invariants. The owner clicks approve. | "Point it at your app and talk for a minute. Muse Spark explores every surface: pages, emails, PDFs, the AI concierge. It finds where each number's truth lives, and turns what you said into rules. You approve them. That's the contract." |
| 0:55–1:40 | **The audit** | `sra audit --base v1 --head v2`. A live persona × surface matrix fills in (8 personas × 7 surfaces) and cells turn red. Cut to three evidence packets: **(1)** the email total contradiction, family persona, with the root shape; **(2)** the concierge saying "free cancellation anytime" on a non-refundable fare, marked UNSUPPORTED against the booking record; **(3)** the service fee raised as announced, but the PDF still saying $12: "intended change, partial rollout". | "It generates edge-case travellers and drives every one through both builds. Muse Spark Open extracts every claim, and the claims become a graph. Same traveller, same fact, different surfaces: a contradiction. The concierge promised something the booking doesn't allow. And the fee increase was in the release notes, so it's intended, except the PDF never got it." |
| 1:40–2:00 | **Honesty** | The verifier trail for one finding (re-captured ✓, second model agrees ✓, oracle recomputed ✓). Then the REJECTED list: "family perk shown, but this persona has kids: rejected". | "Nothing is reported until it's verified: re-captured, re-read by a different model, recomputed against the source of truth. And it shows you what it threw out, and why." |
| 2:00–2:25 | **Proof** | Scoreboard on the seeded benchmark: **one prompt** (Muse Spark, same app, all screenshots, 1M context) vs **auditor**, recall / precision / $ / time. Ablation bars: no contract, no verifier, no diff. | "Is this just a prompt? We measured. Same model, same app: one big prompt found X of N with Y false alarms. The auditor found more, with fewer false alarms. Take away the verifier and precision drops. That's the system, not the prompt." |
| 2:25–2:45 | **Real product** | Label: "App under audit: Finablo (existing product, not part of the submission)". The auditor's Finablo run: a 61-year-old persona, the pending report says the 401(k) max is **$24,500**, the export says **$35,750**. Caught blind. | "And on a real product. Finablo's own hand-built test harness missed this bug. The auditor caught it blind, with a persona the team never wrote." |
| 2:45–2:55 | **Ratchet + close** | `sra accept` → a check file appears. The v3 audit runs that check in 0.4 s with $0 of model calls. Closing card: GitHub URL, "open source", the Meta model logos/names. | "Every confirmed bug becomes a permanent check, so the next release is cheaper. The Semantic Release Auditor. Open source, built on Meta models." |

## The single moment that must land

**The partial rollout (packet 3).** It is the bug a careful human reviewer waves through, because the release notes said the fee changed. It shows intent matching, cross-surface joining and oracle grounding together in one finding. If time runs out, this beat stays and the others shrink.

## Production rules

- **Record from real runs.** Every number on screen comes from a committed `runs/<id>/` that a judge can reproduce with `sra repro`. The benchmark numbers in the video are the numbers in `bench/results/`.
- **Honest scoreboard.** If the baseline does better on some category, the scoreboard says so. A defensible 2× beats a suspicious 10×.
- **Pre-recorded runs, live UI.** Runs are executed ahead of time and replayed from cache at real speed for the screen recording. Sped-up segments are labelled "4×".
- **Readable at 1080p on a laptop:** large fonts in the report, no terminal walls longer than 3 lines.
- **One voice, captions burned in.** (Muse Voice Transcribe can generate the captions.)
- **Label what is new.** A corner tag "built during hackathon" on sra screens, and "app under audit" on Finablo screens.

## Artifacts the demo needs (these drive the build)

| Artifact | Built in |
|---|---|
| Northbound demo app with v1 / v2 / v3 builds, 7 surfaces, seeded issues | Phase 1 |
| `sra onboard` with explorer, voice note → contract review HTML | Phase 2 |
| `sra audit` with live matrix progress + run report HTML + evidence packets | Phase 3 |
| Verifier trail + REJECTED list in the report | Phase 3 |
| Benchmark harness + one-prompt baseline + ablations + scoreboard page | Phase 4 |
| Finablo contract (in Finablo's repo) + one recorded run | Phase 5 |
| `sra accept` + ratchet run on v3 | Phase 3 |
| Hosted static report (the "live product" link) | Phase 6 |

## Stretch beats (only if they are real by Nov 2)

- **SAM 3.1 grounding:** on the PDF (a rendered image, no DOM), the contradicting figure is segmented and highlighted, 3 seconds of screen time.
- **iOS:** the same contract format, one screen of a simulator app audited by vision only, 5 seconds, as "what's next".
- **PR comment:** the finding posted as a GitHub PR comment.
