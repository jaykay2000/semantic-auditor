# Sound cues for the v10 cut (2026-11-01, timed to the recorded voice-over: 174.19 s)

The clips are silent; the voice is `publish-audit/voice/clean/<beat>.wav`, placed 0.15 s into each clip. Every clip
time below comes from that clip's `CUES` table, which holds the second each word starts in the recorded take
(`publish-audit/voice/word-times-v10.json`), minus the 0.25 s lead every visual takes, plus any offset the element
names. So a cue sits 0.25 s before the word it pairs with, the moment the visual lands. Cut times assume the beats
placed back to back from 0:00 at the lengths below, then the 5 s end card. Required by the owner review: FAIL, PASS,
HOLD, SHIP, merged. The rest are optional.

| Beat | Clip | Starts at | Length |
|---|---|---|---|
| b1 | `m9-b1-hook` | 0:00.0 | 17.71 s |
| b2 | `m9-b2-what-sra-does` | 0:17.7 | 23.19 s |
| b3 | `m9-b3-spree` | 0:40.9 | 21.62 s |
| b4a | `m9-b4-1-discovery-to-check` | 1:02.5 | 22.18 s |
| b4b | `m9-b4-2-fail-pass-reload` | 1:24.7 | 8.76 s |
| b5 | `m9-b5-intent` | 1:33.5 | 21.30 s |
| b6 | `m9-b6-your-app` | 1:54.8 | 21.01 s |
| b7 | `m9-b7-finablo` | 2:15.8 | 14.78 s |
| b8 | `m9-b8-close` | 2:30.6 | 18.64 s |
| end | `m9-b8-end-card` | 2:49.2 | 5.00 s |

Total 174.19 s (the recorded lengths, rounded to 0.01 s each; 174.2 s as recorded).

| Cut time | Clip · clip time | Cue | On screen (the word it lands on) | Suggested sound |
|---|---|---|---|---|
| 0:06.1 | `m9-b1-hook` · 6.07 s | optional | 354 finishes counting up ("…fifty-four") | soft tick |
| 0:12.0 | `m9-b1-hook` · 11.97 s | optional | $24,500 struck through ("Neither"; $32,500 follows 0.25 s later) | short low thud |
| 0:13.6 | `m9-b1-hook` · 13.58 s | optional | cut to the dark frame ("Tests check the code") | soft whoosh |
| 0:52.1 | `m9-b3-spree` · 11.22 s | optional | Muse Spark Open's reading: Confirmed ("confirmed") | soft confirm |
| 1:00.6 | `m9-b3-spree` · 19.68 s | **merged** | PR 289 "Merged" pulses ("merged") | positive chime |
| 1:19.4 | `m9-b4-1-discovery-to-check` · 16.88 s | optional | the gate card ("A gate refuses…") | soft tick |
| 1:22.7 | `m9-b4-1-discovery-to-check` · 20.19 s | optional | "✓ Approved by Jayant Kumar" ("I approved it") | soft confirm |
| 1:25.5 | `m9-b4-2-fail-pass-reload` · 0.80 s | **FAIL** | FAIL pops, older release ("older") | short error buzz |
| 1:26.5 | `m9-b4-2-fail-pass-reload` · 1.84 s | **PASS** | PASS pops, next release ("passes") | short success ding |
| 1:31.3 | `m9-b4-2-fail-pass-reload` · 6.63 s | optional | "✓ fix confirmed" ("Fix confirmed") | soft confirm |
| 1:51.8 | `m9-b5-intent` · 18.32 s | optional | Maya: Flagged ("flags") | short error buzz (quieter than FAIL) |
| 1:52.8 | `m9-b5-intent` · 19.34 s | optional | Lena: Cleared ("clears") | short success ding (quieter than PASS) |
| 2:10.8 | `m9-b6-your-app` · 16.02 s | **HOLD** | HOLD pops, broken release ("hold") | short error buzz |
| 2:12.4 | `m9-b6-your-app` · 17.60 s | **SHIP** | SHIP pops, fixed release ("ship") | short success ding |
| 2:21.0 | `m9-b7-finablo` · 5.18 s | optional | "$35,750 in all 8 of 8" (the figure is said) | soft confirm |
| 2:26.4 | `m9-b7-finablo` · 10.58 s | optional | "3 fixes found" ("three") | soft confirm |
| 2:27.6 | `m9-b7-finablo` · 11.86 s | optional | "1 regression found" ("regression") | short low thud |
| 2:49.2 | `m9-b8-end-card` · 0.00 s | optional | the end card | soft closing tone (5 s) |

Keep FAIL / HOLD and PASS / SHIP as the same two sounds, so the viewer learns the pair once (beat 4b) and recognises
it in beat 6. In v10 FAIL and PASS are 1.04 s apart (the voice reads "fails on the older release and passes" quickly):
keep both sounds under about 0.5 s so they don't overlap.
