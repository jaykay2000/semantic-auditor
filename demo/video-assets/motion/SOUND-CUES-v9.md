# Sound cues for the v9 cut — SUPERSEDED by SOUND-CUES-v10.md (the recorded voice-over). Kept for the record.

The clips are silent. These are the moments worth a short sound, at **cut time** (the v9 timeline in
`docs/13-demo-script-v9.md`: beats placed back to back from 0:00) and at **clip time** (seconds into that clip), so
a cue survives a re-timed edit. Required by the owner review: FAIL, PASS, HOLD, SHIP, merged. The rest are optional.
For beats 2, 4a, 5, 6 and 7 the clip time follows the clip's `CUES` table (the word's time minus the 0.25 s lead): if
those tables are re-timed to the recorded voice, move these cues with them.

| Cut time | Clip · clip time | Cue | On screen | Suggested sound |
|---|---|---|---|---|
| 0:06.1 | `m9-b1-hook` · 6.1 s | optional | 354 finishes counting up | soft tick |
| 0:13.4 | `m9-b1-hook` · 13.4 s | optional | $24,500 and $32,500 struck through ("Neither was right") | short low thud |
| 0:14.6 | `m9-b1-hook` · 14.6 s | optional | cut to the dark frame ("Why I built SRA") | soft whoosh |
| 0:54.9 | `m9-b3-spree` · 10.4 s | optional | Muse Spark Open's reading: Confirmed | soft confirm |
| 1:05.2 | `m9-b3-spree` · 20.7 s | **merged** | PR 289 "Merged" pulses | positive chime |
| 1:25.4 | `m9-b4-1-discovery-to-check` · 18.4 s | optional | the gate card | soft tick |
| 1:29.6 | `m9-b4-1-discovery-to-check` · 22.6 s | optional | "✓ Approved by Jayant Kumar" | soft confirm |
| 1:32.8 | `m9-b4-2-fail-pass-reload` · 1.3 s | **FAIL** | FAIL pops (older release) | short error buzz |
| 1:34.9 | `m9-b4-2-fail-pass-reload` · 3.4 s | **PASS** | PASS pops (next release) | short success ding |
| 1:39.7 | `m9-b4-2-fail-pass-reload` · 8.2 s | optional | "✓ fix confirmed" | soft confirm |
| 2:02.0 | `m9-b5-intent` · 20.5 s | optional | Maya: Flagged | short error buzz (quieter than FAIL) |
| 2:03.2 | `m9-b5-intent` · 21.7 s | optional | Lena: Cleared | short success ding (quieter than PASS) |
| 2:19.6 | `m9-b6-your-app` · 15.1 s | **HOLD** | HOLD pops (broken release) | short error buzz |
| 2:21.2 | `m9-b6-your-app` · 16.7 s | **SHIP** | SHIP pops (fixed release) | short success ding |
| 2:28.9 | `m9-b7-finablo` · 5.9 s | optional | "$35,750 in all 8 of 8" | soft confirm |
| 2:33.5 | `m9-b7-finablo` · 10.5 s | optional | "3 fixes confirmed" | soft confirm |
| 2:35.6 | `m9-b7-finablo` · 12.6 s | optional | "1 regression flagged" | short low thud |

Keep FAIL / HOLD and PASS / SHIP as the same two sounds, so the viewer learns the pair once (beat 4) and recognises it
in beat 6.
