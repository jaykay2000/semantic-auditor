# Finablo's 401(k) limit bug as an imported check (2026-10-31)

Asked: make beat 7 of the demo script true ("My app's 401(k) bug became a saved check too. On the next release it
shows $35,750 everywhere, so SRA marks it fixed on that release"), or report exactly what is true instead.

## Outcome

**The bug did not become a saved check.** The frozen converter (b6d672b, untouched) classified the developers'
written finding as `partially_converted`, so SRA refuses to approve it, and a run from storage loads nothing.

| Step | Result | How checked |
|---|---|---|
| Source picked before conversion | finlearn §73 card, line 216 at `a183626` (D3's filing, verbatim) | `SOURCE-PICK.md`, committed in `8aa31c7` before the converter ran |
| Conversion (Muse Spark Open, 1 call) | `partially_converted`: "no action clause is carried out by any step"; gate passed on round 1 | `F73-D3.check.yaml`; `cards-F73-D3.html` |
| Approval | refused: "F73-D3 is partially_converted; only a converted check can be approved" | `semaudit checks approve`, exit 1; no approvals.yaml written |
| Run from storage (`checks run`, v706 → v707) | nothing loaded, nothing run | `runs/f73-saved-1/saved-checks.json` in the harness: `checks: []` |
| Memory outcome | none recorded | no dispositions.yaml |

Why it stops there: the record says what the user saw ("61-year-old sees $24,500 not $35,750") but names no step
the user took. The converter drafted a sound journey anyway (take the assessment as a 61-year-old, open the report
while the plan is being written) and a sound invariant on the guest report under rule H1. Every one of those steps
came from the declared prerequisites, though, not from the finding's words. The converter fails closed on that:
a finding with no carried-out action is not a reproduction, so it is not approvable. That is the rule working as
designed, not a defect to tune around.

What was not done, on purpose: no new bug report was written, no other record was picked after seeing this result,
and nothing in the converter, gate, prompts or judge was changed.

## What each release shows (separate from the check)

See "Captures" below: a fresh, model-free capture of the harness's `target_61` journey on both releases.

## Captures

Run `f73-limit-check` (harness `runs/`, model-free, $0): the harness's `target_61__wide` persona (61, single, $210K
gross, $1,000/mo to retirement, employer match) walks the wide journey on each build, launched locally: guest report
while the plan is pending (s02) and after (s03), guest "Copy for your AI" (s04), sign-up (s05), signed-in report
(s06, s07), signed-in export (s08), welcome email's PDF (s09), dashboard (s10). All 10 steps `done` on both builds.

| Page | v706 (`10ff1e3`) | v707 (`a183626`) |
|---|---|---|
| s02 guest report, plan pending | "Ramp 401(k) contributions toward the IRS max ($24,500/yr) over the next 2–3 years" | "… IRS max ($35,750/yr) …" |
| s03 guest report, plan settled | "… IRS max ($32,500/yr) …" | "… IRS max ($35,750/yr) …" |
| s05 report right after sign-up | "… IRS max ($32,500/yr) …" | "… IRS max ($35,750/yr) …" |
| s06, s07 signed-in report | "Ramp 401(k) toward $32,500/yr" and "… IRS max ($32,500/yr) …" | "Ramp 401(k) toward $35,750/yr" and "… IRS max ($35,750/yr) …" |
| s08 signed-in export | "**Ramp 401(k) toward $32,500/yr" and "… IRS max ($32,500/yr) …" | the same with $35,750 |
| s09 welcome email PDF | "Step 2: Ramp 401(k) contributions toward the IRS max ($32,500/yr) …" | "… ($35,750/yr) …" |
| s10 dashboard | "Ramp 401(k) toward $32,500/yr" | "Ramp 401(k) toward $35,750/yr" |
| s04 guest export | no limit figure | no limit figure |

File counts across each build's text captures: v706 has $24,500 in 1 file, $32,500 in 7, $35,750 in 0; v707 has
$24,500 in 0, $32,500 in 0, $35,750 in 8.

**So "$35,750 everywhere" holds for the stated limit on v707, with one caveat.** The same report pages on BOTH builds
also say "There's roughly $12,500 of unused 401(k) headroom annually". That is $24,500 − $12,000 (the persona's
yearly contribution), the under-50 limit; at $35,750 the room would be $23,750. Finlearn already tracks this as the
open ledger row `AGE-BLIND-401K-AUTHORS`. A rule that counted the room figure (the wide contract's H1 did) would still
fail v707.

Note: the harness's `launch_finablo.py` carried another session's uncommitted edit during this capture (the email
sink's message key); it touches the welcome email's pairing key only, not any page text above.

## Spend

Converter: 1 call, $0.01763, `meta-models/muse-spark-open-1026` on Baseten (ledger `finablo-semaudit/import-root/`).
Capture: $0. No judge ran (nothing approvable). Running total across imported-check work: $10.0584 (Spree) +
$0.0176 = $10.0760.
