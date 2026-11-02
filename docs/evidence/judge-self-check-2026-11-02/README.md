# Judge self-check, first live measurement (2026-11-02)

Counts and verdicts only. Northbound is the fictional travel app in `examples/northbound/`; the cases are dev data.

## What was run

1. **A real review with the self-check on** (rules mode, the default):

   ```bash
   semaudit review --contract examples/northbound/contract --base 2.3 --head 2.4 --max-usd 0.25 --reuse --run-id sc-live-1
   ```

   The run folder held the recorded Northbound demo captures (`runs/e2e-2`, the same run the sample review comes
   from), and the model cache of the main checkout. The review re-captured the affected personas in a browser as
   usual. All 62 of the review's own model calls were answered from the cache ($0.000); the self-check's 6 calls
   were fresh (they always are). Outcome: provisional, policy would say Hold, 9 issues, all verified, the same as
   the sample review.

2. **The reader-mode self-check on its own** (the case set a `review --reader` would run), through the same code:
   `semaudit.verify.selfcheck.run("reader", max_usd=0.10)`. It was not run inside a reader review: a fresh
   Northbound reader review would cost more than this step's budget.

Judge for both: the `interpreter` role, which resolved to **Muse Spark 1.3 on the Meta Model API** (`provider: meta`,
no `semaudit.toml` override). Checked from the `model` and `provider` in each record and the ledger rows (role
`interpreter`, model `muse-spark-1.3`, `cached: false`, tag `judge-self-check:…`).

## Result

| Mode | Prompt (unchanged) | Calls | Planted mistakes caught | Correct cases cleared | Result | Cost |
|---|---|---|---|---|---|---|
| rules (inside the review) | `relate/interpret.py` INSTRUCTIONS, sha256 `1ada1f71ab07c129` | 6 | 3 of 3 | 3 of 3 | **passed, 6 of 6** | $0.046 |
| reader (on its own) | `bench/conditions/prompts/judge_one.md`, sha256 `61ac00b3b056870d` | 1 | 3 of 3 | 3 of 3 | **passed, 6 of 6** | $0.042 |

Total spend for this step: $0.088 of the $0.25 allowed.

Per case ([self-check-rules.json](self-check-rules.json), [self-check-reader.json](self-check-reader.json)):

| Case | Expected | Judge's answer, after SRA's code |
|---|---|---|
| rules-right-1 (Lena: Concierge explains wait vs lock) | clear | P2 passed (explained_tradeoff) |
| rules-wrong-1 (the same answer cut before the lock half) | flag | P2 violated (unexplained_tradeoff) |
| rules-right-2 (Maya 2.4.1: inline reconcile card) | clear | P2 passed (explained_tradeoff) |
| rules-wrong-2 (the reconcile card removed) | flag | P2 violated (unexplained_tradeoff) |
| rules-right-3 (rules-right-2 plus later messages) | clear | P2 passed (explained_tradeoff) |
| rules-wrong-3 (Kai: "Book now" beside "wait") | flag | P2 violated (conflict) |
| reader-right-1 (Raj, urgency allowed by P1-E1) | clear | no finding |
| reader-right-2 (Lena) | clear | no finding |
| reader-right-3 (Theo) | clear | no finding |
| reader-wrong-1 (seat count 2 → 12, from the same banner's "12 h") | flag | U1 and P1 on the banner |
| reader-wrong-2 (Concierge card's seats 2 → 9, from the banner's "€9") | flag | U1 on the card |
| reader-wrong-3 (Omar: banner says 2, inventory reads 9) | flag | U1 and P1 on the banner |

In rules mode every answer above was the model's own label: SRA's code overruled none of them.

## Checks made

- **The review's verdicts did not move.** The same review was re-derived with the self-check off (offline, same
  inputs). Every field of the two review files is identical except `self_check` and `written_at`
  (compared as sorted JSON with the run id normalized).
- **`semaudit verify-report runs/sc-live-1/review-2.3-2.4.json`** prints `CONSISTENT`. It now also re-scores the
  recorded per-case answers and checks the outcome against the self-check.
- **The page shows the line** next to the outcome: [review-page-verdict.png](review-page-verdict.png).

## What is covered, and what is not

- Covered: the `interpreter` role in both review modes, which is the model step that decides whether a coherence
  issue is raised (rules mode) or names every issue (reader mode).
- Not covered: the `extractor` (it reads the figures and directives that code then compares; a misread figure is not
  self-checked), the verifier roles (`cross_checker_*`, `defender`), `semaudit visual`, the saved-check judge
  (`check_judge`), emails read by the reader beyond what these stories contain, and Spree or Finablo cases (the case
  file is Northbound only, judged against the Northbound contract).
- One run, one seed. The prompts were tuned on this same dev fixture, so 6 of 6 says the judge still answers as it
  did when tuned. It is a canary, not an accuracy figure, and not a benchmark number.
