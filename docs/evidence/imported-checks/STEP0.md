# Imported checks, Step 0: does the existing runner already support most of the workflow?

Date: 2026-10-31. Checked by reading the files below (line numbers at commit `4db893b` of this repo and `bc90f03` of
`spree-semaudit`). Verdict: **yes, most of it exists; build the slice.**

## What exists (reuse as is)

| Need | Exists? | Evidence |
|---|---|---|
| Scenario format: persona + timed steps of app verbs | yes | `src/semaudit/contract/schema.py` `Persona` (l.308), `Step` (l.341), `Scenario` (l.348) |
| Spree verbs, driven in a real browser | yes, 15 verbs | `spree-semaudit/adapter.py` `do_open_home` … `do_open_packing_slip` (l.227-508); unknown verb raises `StepFailed` (l.101-104) |
| Fresh capture of one persona on one release, next to the order record | yes | `capture/runner.py` `Runner.capture` (l.127), `run_episode` (l.138); order record = oracle `order` read after every step (`contract-fair/oracles.yaml`) |
| Store reset per episode, release start | yes | `adapter.start_session` waits on `/_semaudit/reset`; `launch_spree.py serve/up` |
| Owner rules usable as invariants | yes, as text | `contract-fair/principles.yaml` U1-U9.persona, P1, L1 (= fair-comparison R1-R11, FAIR-COMPARISON-v4.md l.188-192) |
| Deterministic engine for R3 ("summary adds up") | **no** | `relate/rules.py` `_UNIVERSAL` (l.422-428) has no `sums_to_own_total`; `engine_support` reports U3 as not measured. Only reader mode (a model reading the rule text) judges R3. |
| One model call judging SRA evidence | yes | `bench/judge.py` `render_story` / `render_contract` / `_call` (l.45-133); `decide/reader.py` reuses it |
| Quote checking against captures | yes | `decide/reader.py` `check_citations` (l.75-111) |
| Owner approval pinned by content hash | yes, covers scenarios and personas | `contract/approve.py` `items()` (l.55), `approve()` (l.105) |
| Decisions memory with fix / still_open / regressed / fix_confirmed | yes, for review issues | `decide/memory.py` `apply()` (l.258-305) |
| Replay of a finding from scratch | yes, for review issues | `decide/repro.py` `replay()` (l.123-163) |
| Model calls with a dollar cap and a cost ledger | yes | `models/router.py` `Router(max_usd=…)`, ledger `runs/ledger.jsonl` |

## What must be built

1. **Importer**: agent reproduce text -> persona + steps using only adapter verbs (a model drafts it), plus a
   deterministic gate that refuses any verb the adapter lacks, any catalog item the store lacks, and any part of the
   reproduce text the draft does not account for (mapped, or named as unmapped with a reason).
2. **Check record**: actions + invariant (rule id + surface + statement) + the original quote as evidence only.
3. **Re-check**: replay the scenario with `Runner`, then one small model call per judgment over the cited surface's
   captured messages and the order record; four separate statuses (replay, assertion, semantic confidence,
   evidence verification).
4. **Memory for checks**: `memory.py` handles issues from a review; a check is not a review issue, so the same
   fix / still_open / regressed / fix_confirmed vocabulary is applied to check outcomes (and `load`/`save` must keep
   a new `checks` list instead of dropping it).

## Not available / not decided

- A third Spree release for a "new pair": `launch_spree.py` knows only beta2 and beta3 (`RELEASES`, l.57-60). The
  upstream storefront `8ba5eee` was run once by hand on port 4032 against the beta3 backend
  (`demo/evidence/taxline-upstream-2026-10-30/README.md`); no harness entry exists.
- `contract-fair/` is pinned by the fair-comparison reviews' manifests, so imported scenarios go into a separate
  contract directory (`spree-semaudit/contract-imported/`), never into `contract-fair/`.
