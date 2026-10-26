# 7. Phased implementation plan

Building period **Tue Oct 27 – Wed Nov 4** (submission 9 PM ET; our internal deadline is **12 PM ET Nov 4**). That is 9 working days, of which the last 1.5 are reserved for the video and submission.

## Minimum compelling version (MCV)

The smallest build that makes the demo true. Anything not on this list is a stretch.

1. **Northbound demo app**: 7 surfaces (search results, fare detail, checkout, confirmation page, confirmation email via an outbox sink, itinerary PDF, AI concierge chat), a booking API as the oracle, a test-data hook, builds `v1`, `v2` (seeded issues + intended changes + decoys), `v3` (fixes).
2. **Contract schema + `sra onboard`**: docs + URL + voice note → explorer map → draft contract → HTML review → approved `.sra/`.
3. **`sra audit`**: personas → capture both builds → extract (Muse Spark Open) → graph + diff → the 6 finding families → intent matching → verifier → report + evidence packets + exit codes.
4. **Ratchet**: `sra accept` writes a deterministic check; the v3 audit runs it with no model calls.
5. **Benchmark**: frozen ground truth for v2, a one-prompt baseline (Muse Spark, all captures, 1M context), the full system, and 3 ablations (no contract, no verifier, no diff). Recall, precision, $ and time.
6. **Finablo run**: a Finablo contract (kept in Finablo's repo) and one recorded audit that reproduces a real historical bug blind.
7. **Report UI good enough to film**: persona × surface matrix, packets, verifier trail, REJECTED list, scoreboard.

**Explicitly not in the MCV:** iOS, SAM 3.1, GitHub Action / PR comments, multi-user hosting, an auth-walled SaaS. These are stretches, in that order of cut.

## Phases

### Phase 0 · Oct 26 (today): setup and de-risking
- [x] Read the rules; write the docs; scaffold the repo.
- [ ] Claim the Meta credits and set a $150 spend limit. Apply for Baseten and Modal credits.
- [ ] Settle the decisions in [decisions.md](decisions.md): name, license, GitHub owner, team, Finablo exposure.
- **Exit:** owner signs off on goals and MCV.

### Phase 1 · Oct 27: model access + target app
- Model router with roles, cache and cost ledger. **Smoke tests that verify, not assume:** Muse Spark chat, image input, PDF input, tool calling, structured (JSON-schema) output, context limits, rate limits; Muse Spark Open 1026 on Baseten (and/or Modal) with structured output; Muse Voice Transcribe on a sample note; SAM 3.1 availability.
- Northbound v1: FastAPI app, 7 surfaces, booking API, outbox sink, PDF, concierge (deterministic templates plus one optional LLM-backed answer path), test-data hook.
- **Exit:** `pytest tests/test_models_smoke.py` green on real endpoints; Northbound v1 boots; a script captures all 7 surfaces for one persona.

### Phase 2 · Oct 28–29: contract + capture + extraction
- Pydantic contract schema + validation + a hand-written **reference contract** for Northbound (the benchmark answer key for onboarding).
- Adapters: web (Playwright), email sink, PDF, API, chat.
- Journey recorder/replayer; persona materialization through the hook.
- Extractor: capture → claims, contract-guided; normalization (money, compact formats, dates/timezones, units).
- `sra onboard` v0: ingest docs + transcript → mapper draft → oracle discovery by value matching → review HTML.
- Seed **Northbound v2**. ⚠️ The issue list is written by a *separate session* that keeps the ground truth in `bench/ground_truth/` and does not share it with the session building the checkers. This limits overfitting to our own bugs.
- **Exit:** claims for v1 × 8 personas extracted with ≥95% value accuracy against the reference; draft contract recovers ≥90% of the reference facts and surfaces.

### Phase 3 · Oct 30–31: checkers, verifier, diff, report, ratchet (**core feature freeze Oct 31 EOD**)
- Claim graph + semantic diff with grouping.
- Checkers: CONTRADICTION, ORACLE_MISMATCH (code); UNSUPPORTED, PERSONA_MISFIT (rules + judge); SEMANTIC_REGRESSION + intent matching; UNKNOWN_CLAIM.
- Verifier: re-capture, cross-model re-extract, recompute, defense pass.
- Report HTML: matrix, packets, verifier trail, REJECTED list, ledger. `sra repro`, `sra accept`, `sra allow`.
- Ratchet: checks run first; v3 run.
- **Exit:** the end-to-end demo runs on Northbound v1→v2→v3 from a cold cache in under 15 minutes and under $5.

### Phase 4 · Nov 1: benchmark + precision tuning
- Unseal the ground truth. Score the full system, the one-prompt baseline and 3 ablations. Write `bench/results/<date>.json` and a scoreboard page.
- Tune prompts and thresholds on v2 **only through a held-out split**: half the seeded issues are used for tuning, half are scored. Report both halves.
- **Exit:** scoreboard committed; numbers reproducible from cache.

### Phase 5 · Nov 2: real product (Finablo) + stretch window
- Run `sra onboard` against local Finablo; owner reviews the contract, which is committed to **Finablo's** repo, never this one.
- Recreate one real historical bug on a local Finablo branch (the pending-page 401(k) limit is the first candidate) and audit base vs that branch blind, using no Finablo-specific code in sra.
- Constraints carried from Finablo: run locally only, never against prod; no Finablo pushes (limited CI minutes); skip Sage chat unless the owner approves its Claude spend.
- Stretch, only if Phases 1–4 are green: SAM 3.1 highlight on the PDF → iOS single-screen spike → PR comment.
- **Exit:** one recorded Finablo run with a CONFIRMED finding matching the historical bug, or an honest write-up of why not.

### Phase 6 · Nov 3: polish + record
- README quickstart (`pip install`, `sra demo` boots Northbound and runs the whole story).
- Static hosted report (GitHub Pages) as the "live product" link.
- Repo public; license; HACKATHON.md provenance ledger final.
- Record video take 1, review it against [06-demo-vision.md](06-demo-vision.md), re-record.

### Phase 7 · Nov 4: submit
- Final video (≤3:00), captions, upload, check the link is public.
- Submission form; all contributors listed; repo public check from a logged-out browser.
- Post the demo on X (Most Viral prize); share in Discord.

## Budget

| Item | Estimate |
|---|---|
| One full Northbound audit, cold cache: 8 personas × 7 surfaces × 2 builds ≈ 112 captures | extraction ~0.5M tokens on open weights; judge + verifier ~0.3M on Muse Spark; **≈ $1–3** |
| Benchmark: system + baseline + 3 ablations, ×3 repeats | ≈ $20–30 |
| Onboarding runs (explorer is the costly part) | ≈ $10 |
| Finablo runs | ≈ $10 |
| Headroom for iteration | the rest of the $150 Meta credit; Baseten/Modal credits for open weights |

Pricing is not yet verified. One source says Muse Spark costs $1.25 per million input tokens and $4.25 per million output. Recheck the pricing on day 1, and keep `--max-usd` on every run.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Meta API capability differs from what we assume (vision, tools, JSON schema, rate limits) | Day-1 smoke tests; router allows swapping roles between Muse Spark and Muse Spark Open |
| Open-weights hosting not granted or slow | Apply to both Baseten and Modal on day 1. The fallback is extraction on Muse Spark, which loses the open-weights bonus but keeps the demo |
| Explorer agent unreliable on arbitrary UIs | Record journeys once at onboarding and replay them deterministically; the agent only repairs |
| Benchmark looks rigged (we wrote the bugs) | Blind seeding by a separate session; held-out split; honest baseline; real-product run |
| Nondeterministic model outputs break the demo | Content-hash cache; demo replays committed runs |
| Disqualification over "what was built during the hackathon" | Provenance ledger; on-screen labels; no Finablo code in the repo |
| Video takes longer than planned | Phase 6 starts no later than Nov 3 morning, whatever is unfinished |
| Solo bandwidth | Claude Code agents for implementation (disclosed in the provenance ledger); cut stretches first |

## Cut order (if behind)

1. iOS spike → 2. SAM 3.1 → 3. PR comment → 4. voice onboarding (fall back to a typed interview) → 5. ablations beyond "no verifier" → 6. Finablo live run (fall back to a run on recorded Finablo captures). The benchmark and the partial-rollout packet are never cut.

## After the hackathon (not planned in detail)

GitHub Action, contract diff review in PRs, iOS/Android adapters (vision + accessibility tree + SAM), a hosted service, and contracts for more real apps.
