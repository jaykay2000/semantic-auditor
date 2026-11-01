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
python3 slides-src/extract_beat4.py            # beat-4 data from Run 3c (read-only; refuses on any mismatch)
python3 slides-src/render_motion.py            # every clip + still (~40 s per clip)
python3 slides-src/render_motion.py m7-b4      # only clips whose name starts with this
python3 slides-src/render_motion.py --still m7-b4   # stills only, fast
```

No ffmpeg install is needed. Frames are captured one at a time (deterministic, sharp text). WebM is encoded with the
ffmpeg build that Playwright ships, and MP4 with AVFoundation (`slides-src/jpegs2mp4.swift`, compiled on first use
into `.motion-build/`, macOS only). Opening a non-data clip's HTML directly in a browser plays it as a preview.
The beat-4 clips need `window.DATA`, so preview those through the render.

**After the owner approves C1-04 and runs `run-saved` on recording day**, point the beat-4 clips at that run and
re-render:

```bash
python3 slides-src/extract_beat4.py \
  --saved ~/Documents/src/spree-semaudit/runs/ic-owner-rec-1/saved-checks.json \
  --transcript ~/Documents/src/spree-semaudit/runs/ic-owner-rec-1.txt
python3 slides-src/render_motion.py m7-b4
```

`extract_beat4.py` prints a **WARNING** while the run's approval record reads "owner has not reviewed this digest".
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
| `m7-b4-2-fail-then-pass` | `m7-b4-2-fail-then-pass.png` | 4 · transition 2, about 1:06–1:14 | 11 s | `m7-b4-2-fail-then-pass.html`. The two confirmation emails as the judges cited them; each one's own lines added up. Older: 179.98 − 15.00 + 0.00 + 14.40 = 179.38 ≠ 194.38 → FAIL 3 of 3. Next: Shipping $15.00 → 194.38 = 194.38 → PASS 3 of 3. Caption "Spree's own fix, PR #14725" |
| `m7-b4-3-saved-check-reruns` | `m7-b4-3-saved-check-reruns.png` | 4 · transition 3, about 1:14–1:24 | 11 s | `m7-b4-3-saved-check-reruns.html`. The run-saved command and the four stored files with their hashes, "nothing imported", the run's own C1-04 output lines verbatim, FAIL → PASS, then **fix confirmed**, written to `dispositions.yaml` |
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
| Command and output lines | the run transcript (`$ … run-saved …` and the lines starting `C1-04 `), verbatim; refused if it is another run's transcript |
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
