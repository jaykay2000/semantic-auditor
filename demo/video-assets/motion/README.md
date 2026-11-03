# Motion clips for script v7 (2026-11-01)

1920×1080, 30 fps. Each clip comes as `.webm` (VP9) and `.mp4` (H.264); both play in Canva, QuickTime and browsers.
Each clip also has a still: its last frame at 3840×2160, in `../scenes/` next to the other frames. Binaries
(`*.webm`, `*.mp4`, `*.png`) are **not tracked**, the same as the existing PNGs. Regenerate them from the sources.

Every clip reuses the existing frame's content and tokens, and changes only the **order of appearance**, with one
exception: the three beat-4 clips are new layouts, drawn from the run's saved result files (below). No number,
quote or label is typed by hand. No coding agent and no non-Meta model is named on any frame.

## Regenerate

```bash
cd demo/video-assets
python3 slides-src/extract_beat4.py            # beat-4 data from the owner's run ic-owner-rec-1, as committed in
                                               # docs/evidence/imported-checks/acceptance/ (read-only; refuses on any mismatch)
python3 slides-src/render_motion.py            # every clip + still (~40 s per clip)
python3 slides-src/render_motion.py m7-b4      # only clips whose name starts with this
python3 slides-src/render_motion.py --still m7-b4   # stills only, fast
```

No ffmpeg install is needed. Frames are captured one at a time (deterministic, sharp text). WebM is encoded with the
ffmpeg build that Playwright ships, and MP4 with AVFoundation (`slides-src/jpegs2mp4.swift`, compiled on first use
into `.motion-build/`, macOS only). Opening a non-data clip's HTML directly in a browser plays it as a preview.
The beat-4 clips need `window.DATA`, so preview those through the render.

The committed `scenes-data/beat4.json` is what the default command above writes from
`run-owner-2026-11-01-saved-checks.json` (checked 2026-11-01: identical apart from `_source`). For a different run,
pass its files:

```bash
python3 slides-src/extract_beat4.py --saved <run>/saved-checks.json --transcript <run>.txt
python3 slides-src/render_motion.py m7-b4
```

**As of 2026-11-01 the beat-4 clips come from `ic-owner-rec-1`, approved by the owner under their own name** (C1-04
fix_confirmed; the older release's card shows every vote: 2 fail · 1 not measurable, confidence 2/3).
`extract_beat4.py` prints a **WARNING** while a run's approval record reads "owner has not reviewed this digest".
The transition-1 stamp prints that record verbatim (amber while unreviewed, green once it is the owner's), so the
voice-over line "The owner approves it" only matches the screen after the owner's approval and a fresh run. If the
recording-day run comes back `not_measurable`, the extract refuses ("this clip shows an older-release FAIL and a
next-release PASS"). In that case use the Run 3c clips as they are, labelled with their date (v7 open item 2).

## Clips

| Clip (in `motion/`) | Still (in `scenes/`) | Beat · slot | Length | Source |
|---|---|---|---|---|
| `m7-b1-finablo-limits` | `m7-b1-finablo-limits.png` | 1 · 0:00–0:17 | 17 s | `slides-src/m7-b1-finablo-limits.html`. The content of `s7-b1` (same crop, ring, labels, chip, footnote). The chip pops on "354 automated checks passed"; the two figures arrive on "conflicting retirement guidance"; the 2026 limit arrives on "We fixed the bug" |
| `m7-b2-loop` | `m7-b2-loop.png` | 2 · 0:17–0:39 | 23 s | `m7-b2-loop.html`. The nodes of `s7-b2`, built in voice-over order: Discovery → Saved ("reusable release checks") → Muse Spark drafts, plus three chips on Saved (journey · rule · evidence) → Gate, Owner approves → Replay + the next-release arrow → Status chips in the order said (still open, fixed, came back) → one dot runs the loop. "came back" stays a label |
| `m7-b3a-overlap` | `m7-b3a-overlap.png` | 3 · 0:39–0:50 (default) | 11 s | `m7-b3a-overlap.html`, `_overlap_motion.js`. **No numbers.** Two equal circles drift together and overlap in part |
| `m7-b3b-overlap` | `m7-b3b-overlap.png` | 3 · same slot, **only with the auditor's OK** | 11 s | `m7-b3b-overlap.html`. Same, plus 5 · 8 · 4 and "17 groups of findings · 8 in both runs" from `scenes-data/overlap.json` |
| `m7-b4-1-finding-to-check` | `m7-b4-1-finding-to-check.png` | 4 · transition 1, about 0:50–1:06 | 16.5 s | `m7-b4-1-finding-to-check.html`, `_b4.inc.js`, `scenes-data/beat4.json`. The agent's finding as written (C1#04) → each phrase of its steps lights up as the journey step it became (9 steps, adapter verbs) → Rule U3 and the check's invariant, verbatim → gate rounds → the approval record, verbatim |
| `m7-b4-2-fail-then-pass` | `m7-b4-2-fail-then-pass.png` | 4 · transition 2, about 1:06–1:14 | 11 s | `m7-b4-2-fail-then-pass.html`. The two confirmation emails as the judges cited them; each one's own lines added up. Older: 179.98 − 15.00 + 0.00 + 14.40 = 179.38 ≠ 194.38 → FAIL, "3 readings: 2 fail · 1 not measurable · confidence 2/3" (as `beat4.json` records it). Next: Shipping $15.00 → 194.38 = 194.38 → PASS, 3 readings: 3 pass, confidence 3/3. Caption "Spree's own fix, PR #14725" |
| `m7-b4-3-saved-check-reruns` | `m7-b4-3-saved-check-reruns.png` | 4 · transition 3, about 1:14–1:24 | 11 s | `m7-b4-3-saved-check-reruns.html`. A **generic `run-saved` prompt** (`beat4.json` has `command: null`: the run's transcript holds no command line, so this is a fallback, not transcript text), the four stored files with their hashes, "nothing imported", the run's own C1-04 output lines verbatim, FAIL → PASS, then **fix confirmed**, written to `dispositions.yaml` |
| `m7-b5-fixed-upstream` | `m7-b5-fixed-upstream.png` | 5 · 1:24–1:37 | 13 s | `m7-b5-fixed-upstream.html`, `scenes-data/beat5.json`. Beat 5, "Found, reported, fixed upstream" (renamed from `m7-b5-still-open`, 2026-11-01). SRA's review page (`runs/recording-2026-11-01/shots/beat5-spree-tax-line.png`, copied to `slides-src/img/`), not the small storefront shots. Everything but the issue dims; chip "still open, both releases" (true of beta2 → beta3); caption "Reproduced on Spree's upstream storefront (8ba5eee, 2026-10-30) · reported upstream; fix merged 2026-11-01 (PR #289)". Issue 283 was closed on 2026-11-01 by PR #289 ("Fixes #283"), merged by a Spree organisation member, merge commit `f9fa77a`, checked with `gh api`; SRA has not run the fixed storefront. Sources: `demo/evidence/taxline-upstream-2026-10-30/README.md` |
| `m7-b7-finablo-v706-v707` | `m7-b7-finablo-v706-v707.png` | 7 · 2:09–2:24 | 15 s | `m7-b7-finablo-v706-v707.html`. The crops and text of `s7-b7`: v706 row by row with its two figures, then v707 row by row with "$35,750 everywhere". No "fixed" chip; the headroom line is out of frame (scenes/README note 3; this clip adds no crop) |
| `m7-b8-end-card` | `m7-b8-end-card.png` | 8 · end card 2:40–2:46 | 6 s | `m7-b8-end-card.html`. The content of `s7-b8`, staggered in over 2 s. The repo URL comes from `scenes-data/close.json`: `https://github.com/jaykay2000/semantic-auditor` (2026-11-01) |

**Overlay (a still, not a clip):** `scenes/o7-b6-rule-overlay.png`, a transparent PNG from `slides-src/o7-b6-rule-overlay.html`
for beat 6. Place it full-frame over the live Northbound page (browser at 1920×1080, zoom 100%, scrolled to the top). It:
- carries the owner's rule P2 in v7's elided wording, with the elisions marked, from `examples/northbound/contract/principles.yaml`;
- sits over the page's release header, so it never covers Maya's two messages;
- covers the page's "fictional benchmark app" pill with "fictional test app".

`scenes/o7-b6-rule-overlay-proof.png` shows it composited on `runs/recording-2026-11-01/shots/beat6-northbound-maya.png`.

## Where the beat-4 values come from (`scenes-data/beat4.json`)

| On screen | File and field |
|---|---|
| The agent's finding, its steps, the journey, rule U3's invariant, gate rounds (2: 2 problems, then none), drafting model | `spree-semaudit/contract-imported/checks/C1-04.yaml`: `source`, `clauses`, `scenario.steps`, `invariant`, `conversion`. **Refused unless its sha256 equals the hash the run recorded loading** (`d3408fbc3d2146e2`) |
| Rule title "Summary does not add up" | `contract-imported/principles.yaml` U3 |
| Approval: digest, and "by …" | the saved results' `checks[C1-04].approved_digest` / `approved_by`, verbatim |
| Email lines on each release | the `cited` quotes of the readings that agree with the verdict and whose evidence is `verified`; refused if they disagree |
| Running sums | plain addition of those lines (Decimal); refused if a sum disagrees with the verdict |
| Votes, readings, evidence, replay, judging model | `results.<release>.assertion / semantic_confidence / evidence / replay / models` |
| Files loaded from storage + hashes, run id and time | `loaded_from_storage`, `run`, `at` |
| Command and output lines | output lines: the run transcript's lines starting `C1-04 `, verbatim; refused if it is another run's transcript. Command: the transcript's `$ … run-saved …` line when it has one. `ic-owner-rec-1`'s transcript has none, so `command` is null and the clip types a generic `run-saved`, which is not transcript text |
| "nothing imported" | `docs/evidence/imported-checks/README.md`, run 3 row: "A NEW run from storage only (`run-saved`; nothing imported)" |
| "fix confirmed" and its reason | `checks[C1-04].memory.status / why` |
| v6.0.0.beta2 / beta3 | `docs/11-recording-runsheet.md` (storefront 4030 current/beta2, 4031 candidate/beta3) and the Run 3c card title |
| "the free-shipping discount is counted twice" | the agent's finding (`source.should_be`) and the judges' readings ("double-counts the discount") |

The source line on every beat-4 frame names the run it was drawn from. Cost is not shown: the transcript's cost line
leaves out discarded attempts (v7).

## Fixes made to the existing frames (not just motion)

- **Beat 3:** in `s7-b3a/b`, "in both" (and the 8) crossed the circle outlines. The motion versions widen the overlap
  so the label sits inside the lens. Sizes and overlap width still encode nothing.
- **Beat 6:** the rule text and the "fictional test app" label are now one overlay file, not editor retyping.
- The `s7-*` stills are unchanged. The `m7-*` stills are the recommended replacements wherever a clip is not used.

## v8 clips (script `docs/12-demo-script-v8.md`, 2026-11-01)

The owner's direction for v8 was to put the wins on screen and the caveats in the README. The v8 clips (`m8-*`) drop
the prototype pill, the vote breakdowns, the "provisional" chips and the long source footers (`slides-src/v8.css`
keeps a short source line on every frame). Every claim is still sourced; see the v8 script's source table. Page shots
come from `slides-src/shoot_v8.py`, which writes 2x captures into `slides-src/img/v8/` (untracked). It covers the
Spree, Northbound and Brightdesk review pages, plus tight crops of the public GitHub issue 283 and PR 289. The crops
stop before the PR's branch name and description footer, because both name a coding agent.

| Clip | Beat · slot | Length | Source |
|---|---|---|---|
| `m8-b1-finablo-limits` | 1 · 0:00–0:14 | 14 s | `m8-b1-finablo-limits.html`. `m7-b1` retimed to the v8 hook |
| `m8-b2-what-sra-does` | 2 · 0:14–0:34 | 20 s | `m8-b2-what-sra-does.html`. Test users → two releases (page, email, the app's records) → Muse Spark Open, against your own rules → release review |
| `m8-b3-upstream-fix` | 3 · 0:34–1:01 | 28 s | `m8-b3-upstream-fix.html`, `img/v8/spree-tax-line.png`, `gh-*.png`. Spree review crop, $43.19 ≠ $39.99, reported Oct 30 (issue 283, closed), fix merged Nov 1 (PR #289, "Fixes #283") |
| `m8-b4-0-agents-intro` | 4 · 1:01–1:06 | 5.5 s | `m8-b4-0-agents-intro.html`. Two runs of one agent overlap in part; no numbers |
| `m8-b4-1/2/3-*` | 4 · 1:06–1:39 | 16.5 / 11 / 11 s | the m7 beat-4 layouts with `window.V8`: no prototype pill, no votes, "Approved by Jayant Kumar" (run `ic-owner-rec-1`) |
| `m8-b5-intent` | 5 · 1:39–2:02 | 22 s | `m8-b5-intent.html`. Rule P2, Maya's two messages (crops), flagged; then Lena, cleared |
| `m8-b6-your-app` | 6 · 2:02–2:21 | 19 s | `m8-b6-your-app.html`. Brightdesk reviews (HOLD: 3 new; SHIP: 3 resolved), $0.13 in model calls (15 billed calls, $0.1323). Numbers from `scenes-data/brightdesk.json`, derived from the committed record `demo/evidence/newuser-brightdesk-2026-11-01/` by `extract_brightdesk.py` |
| `m8-b7-finablo-v706-v707` | 7 · 2:21–2:33 | 12 s | `m7-b7` retimed |
| `m8-b8-close` | 8 · 2:33–2:48 | 15 s | `m8-b8-close.html`. The three review pages side by side, plus the one-line idea |
| `m8-b8-end-card` | end card · 2:48–2:54 | 6 s | `m7-b8` with the one-line idea; repo URL from `scenes-data/close.json` |

```bash
python3 slides-src/shoot_v8.py --github    # re-capture the page shots (the --github part needs network)
python3 slides-src/render_motion.py m8     # every v8 clip + still
```

## v9 clips, timed to the v10 voice-over (script `docs/13-demo-script-v9.md`, lines `publish-audit/voice/RECORDING-SHEET.md`, 2026-11-01)

The owner's review of v8, applied: the owner speaks in first person; one thesis (since the second review: "SRA turns
discoveries into checks your next release has to pass", no "every") by 0:25 and again at the close; one persistent header on every beat (SRA badge · an
app chip with its own colour · the model pill); content scaled up and centred; anything a judge must read is at least
24 px; slow push-ins, keyword pulses and two dark contrast frames (the SRA reveal, FAIL → PASS); the Venn is cut and
beat 4's two FAIL → PASS clips are merged; Finablo is labelled on screen as the app under audit, not the submission.
**No frame types a figure it shows:** every number comes from `scenes-data/v9.json` (`slides-src/extract_v9.py`,
which records each source's sha256 and refuses on any mismatch), `beat4.json`, `brightdesk.json` or `close.json`, and
`tests/test_demo_v9.py` fails on a typed figure.

| Clip | Beat · slot | Length | Source |
|---|---|---|---|
| `m9-b1-hook` | 1 · 0:00–0:17.7 | 17.71 s | Finablo's freedom card (v706) → the v706 gate record (354 OK · 0 FAIL) → the two limits this user saw → $35,750 → dark frame "Tests check the code. They don't read what users read." One `CUES` table |
| `m9-b2-what-sra-does` | 2 · 0:17.7–0:40.9 | 23.19 s | dark reveal + thesis → test users, v706 → v707 and the pages they walk → Muse Spark's three jobs (read, with the opt-in "can check the screenshot"; judge; draft: the voice no longer names the chip or the third job, so they land on "get" and just after "rules") → SRA's four release categories, labelled as the review page labels them (New · Resolved · Pre-existing · Unconfirmed). One `CUES` table |
| `m9-b3-spree` | 3 · 0:40.9–1:02.5 | 21.62 s | Ana's order page from the review's own capture, rings from its bounding boxes; $43.19 ≠ $39.99, 25 of 67 shoppers; **visual confirmation**: the crop `semaudit visual` sent Muse Spark Open, which read $43.19 (confirmed; the control claiming $39.99 on the same crop, contradicted; `docs/evidence/visual-confirm-spree-2026-11-01`); the five amounts; issue 283, PR 289 merged. One `CUES` table |
| `m9-b4-1-discovery-to-check` | 4 · 1:02.5–1:24.7 | 22.18 s | "SRA can keep them" → the agent's finding → journey (9 verbs) → rule U3 → the gate (nothing dropped or invented; 2 problems, redrafted → passed) → approved by Jayant Kumar; labelled "a bug Spree had already fixed (PR #14725)". One `CUES` table |
| `m9-b4-2-fail-pass-reload` | 4 · 1:24.7–1:33.5 | 8.76 s | dark: FAIL (beta2) / PASS (beta3) with each email's own sum, then the stored files reloaded and hashed, nothing imported, fix confirmed. One `CUES` table |
| `m9-b5-intent` | 5 · 1:33.5–1:54.8 | 21.3 s | "No test assertion can express this rule", P2, Maya and Lena side by side (both offers, in sans), Flagged / Cleared |
| `m9-b6-your-app` | 6 · 1:54.8–2:15.8 | 21.01 s | Brightdesk 1.0's own pricing and checkout pages (t3 captures), the agent's 49-line adapter and its 4 verbs, its endpoint, open weights, rule B1 with the broken prices, HOLD / SHIP, $0.13 |
| `m9-b7-finablo` | 7 · 2:15.8–2:30.6 | 14.78 s | the 8 steps that state the limit: v706 red ($24,500 at 1, $32,500 at 7), v707 green ($35,750 at all 8); then SRA's own review of v707 → v731 (24 releases apart): 3 fixes found (confirmed by code history), 1 regression found (owner-confirmed, on a test persona) (`docs/evidence/finablo-fresh-releases-2026-11-01/counts.json`). One `CUES` table |
| `m9-b8-close` | 8 · 2:30.6–2:49.2 | 18.64 s | who it is for (finance · health · commerce), the live sample review in a browser frame with a slow push-in onto its "Unexplained tradeoff" card, the thesis. One `CUES` table |
| `m9-b8-end-card` | end card · 2:49.2–2:54.2 | 5 s | thesis, repo URL, live sample URL, run commands, built during the hackathon, owner's name, the models (Muse Spark 1.3 · 1.2 on the Meta Model API; Muse Spark Open, open weights) |

Also: `scenes/m9-thumbnail.png` (beat 1 at 11.6 s, an extra still written by `render_motion.py`) and the sound-cue
sheet `SOUND-CUES-v10.md` (v10 timing; `SOUND-CUES-v9.md` is the superseded v9 one). Total 174.2 s.

```bash
python3 slides-src/extract_brightdesk.py          # beat 6 data (adds the adapter and the broken prices in v9)
python3 slides-src/extract_v9.py                  # beats 1, 3, 5, 7 data + img/v9 crops (reads the Finablo and Spree harness runs
                                                  # and docs/evidence/visual-confirm-spree-2026-11-01)
python3 ../build_sample_review.py                 # docs/sample-review/, the hosted sample (beat 8, end card)
python3 slides-src/shoot_v9.py                    # img/v9/sample-review.png, from docs/sample-review/
python3 slides-src/render_motion.py m9            # every v9 clip + still + the thumbnail
```

Re-timing to the recorded voice: every beat except the end card keeps one `CUES` table, the second each word starts in
the recorded take (`publish-audit/voice/word-times-v10.json`); edit the table, re-render the clip. `tests/test_demo_v9.py`
checks each clip's length against the recording and that its last cue is spoken a second before it ends. `slides-src/_v9.inc.js::applyCues` turns `data-cue="name"` into the element's start time.

## v10 screens: demo cut 3, storyboard v15 (2026-11-02, unvoiced, provisional timing)

Seven screens for the owner's review before recording, same visual language as m9 (`v9.css`), with `v10.css` and
`slides-src/_v10.inc.js` adding the corner marker of the four contributions (V3-V6, the current number lit). Every
cue table is **provisional** (2.3 words a second from 0.3 s, from the storyboard v14.1 lines; V3's are section
placeholders) until the owner's V1-V7 takes exist; re-time by editing each `CUES` table only, as for v9.

| Clip | Beat | Provisional length | Shows |
|---|---|---|---|
| `m10-v1-problem` | V1 | 18.9 s | m9-b1 with the owner-review changes: the two wrong limits struck, beside them "correct for age 61: $35,750" with its basis; the close "They don't check what users see." |
| `m10-v2-contributions` | V2 | 13.5 s | SRA's name and one line → the four contributions, each with its one-line Muse Spark job; they hold ~2 s, then shrink into the corner marker |
| `m10-v3-personas` | V3 | 21.5 s | "1 Judges what no test assertion can check": Finablo's rules H1 and H2 (id, title, text only; finablo-semaudit `contract-wide/principles.yaml`) → v707, all 8 places at $35,750 → Maya's and Lena's persona cards in plain words, "written by the owner" → ONE real Muse Spark verdict for Maya with its reasoning (the sample review's "Unexplained tradeoff"), labelled `muse-spark-1.3` |
| `m10-v4-keeps` | V4 | 37 s | the eight-box flow over the real check card's own sections (the owner's run ic-owner-rec-1); the stamp from `approvals.yaml`; "edit the check and the approval no longer applies"; "prototype: today SRA keeps only reports where it can verify every step (6 of 57)" |
| `m10-v5-checks-itself` | V5 | 28.3 s | "a second, real bug": $43.19 shown ≠ $39.99 in the record → the screenshot crop, read $43.19, Confirmed → the planted control, the same crop claiming $39.99, Contradicted → the review page's "Judge self-check: 6 of 6" |
| `m10-v6-plugs-in` | V6 | 21 s | the two files in plain words (Spree's 13 rules, id + title, from `contract-spree/principles.yaml`; the adapter named, not scrolled) → one real page per app (Spree, a Finablo test user, Maya on Northbound) → "Spree checks: Muse Spark Open (open weights)", from Run 3c's record. No Brightdesk |
| `m10-v7-results` | V7 | 29.5 s | Finablo Fixed (8 of 8) · Finablo 1 regression (introduced in v708, confirmed by me on a test user) · Spree Fix merged (Nov 1, reported Oct 30, github.com/spree/storefront PR #289) · Saved check Kept |

```bash
SPREE_HARNESS_DIR=<spree-semaudit> FINABLO_HARNESS_DIR=<finablo-semaudit> python3 slides-src/extract_v10.py
python3 slides-src/shoot_v10.py                   # img/v10/card-*.png (the check card), maya-verdict.png (sample review)
python3 slides-src/render_motion.py m10           # every v10 clip + still
python3 slides-src/contact_v10.py                 # scenes/m10-contact-sheet.png, with the layout check per frame
```

`tests/test_demo_v10.py` checks `scenes-data/v10.json` against the committed records without the harness repos (the
approval fingerprint is recomputed from the stored check; Spree's rules file is compared by git blob id) and fails on
a figure typed into a frame, or on any agent, model or app name other than Muse Spark's.
