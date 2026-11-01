# Sound cues for the v9 cut (2026-11-01, re-timed for beat 3's visual confirmation)

The clips are silent. These are the moments worth a short sound, at **cut time** (the v9 timeline in
`docs/13-demo-script-v9.md`: beats placed back to back from 0:00) and at **clip time** (seconds into that clip, from
the clip's own source comment), so a cue survives a re-timed edit. Required by the owner review: FAIL, PASS, HOLD,
SHIP, merged. The rest are optional.

| Cut time | Clip · clip time | Cue | On screen | Suggested sound |
|---|---|---|---|---|
| 0:07.2 | `m9-b1-hook` · 7.2 s | optional | 354 finishes counting up | soft tick |
| 0:13.4 | `m9-b1-hook` · 13.4 s | optional | $24,500 and $32,500 struck through ("Neither was right") | short low thud |
| 0:14.6 | `m9-b1-hook` · 14.6 s | optional | cut to the dark frame ("Why I built SRA") | soft whoosh |
| 0:58.4 | `m9-b3-spree` · 10.4 s | optional | Muse Spark Open's reading: Confirmed | soft confirm |
| 1:08.7 | `m9-b3-spree` · 20.7 s | **merged** | PR 289 "Merged" pulses | positive chime |
| 1:30.3 | `m9-b4-2-fail-pass-reload` · 1.3 s | **FAIL** | FAIL pops (older release) | short error buzz |
| 1:32.4 | `m9-b4-2-fail-pass-reload` · 3.4 s | **PASS** | PASS pops (next release) | short success ding |
| 1:37.2 | `m9-b4-2-fail-pass-reload` · 8.2 s | optional | "✓ fix confirmed" | soft confirm |
| 1:59.8 | `m9-b5-intent` · 20.8 s | optional | Maya: Flagged | short error buzz (quieter than FAIL) |
| 2:01.0 | `m9-b5-intent` · 22.0 s | optional | Lena: Cleared | short success ding (quieter than PASS) |
| 2:17.8 | `m9-b6-your-app` · 15.3 s | **HOLD** | HOLD pops (broken release) | short error buzz |
| 2:19.5 | `m9-b6-your-app` · 17.0 s | **SHIP** | SHIP pops (fixed release) | short success ding |
| 2:32.1 | `m9-b7-finablo` · 9.6 s | optional | "$35,750 in all 8 of 8" | soft confirm |

Keep FAIL / HOLD and PASS / SHIP as the same two sounds, so the viewer learns the pair once (beat 4) and recognises it
in beat 6.
