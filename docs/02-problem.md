# 2. Problem statement

## The bug class

A **semantic release bug** is a release where every surface works, and the product still tells a user something false, contradictory, unsupported or wrong for them.

These bugs share three properties that make them escape normal QA:

1. **Each surface is individually correct-looking.** The page renders and the email sends. The defect only exists *between* two surfaces, or between a surface and the truth.
2. **They are persona-dependent.** The default test user is fine. A 61-year-old, a user with no debt, or a traveller paying in euros is not.
3. **They are invisible to assertion-based tests**, because nobody wrote an assertion for a sentence that did not exist yet, or for text a model wrote at runtime.

## Evidence from a real product (Finablo)

Finablo is a personal-finance web app. Its report, dashboard, PDF, emails, "Copy for your AI" export and AI assistant all state the same facts about a user's money: freedom age, savings, first recommended move, budget verdict. Over several months it shipped many bugs of exactly this class, despite a deterministic test gate of thousands of tests. Examples from its own bug history:

- **One quantity, two values.** On the pending report page, a 61-year-old read **$24,500** as their 401(k) maximum while the server and the export said **$35,750**. The server was right; the page composed its number from a different, unfinalized list.
- **One stored source, two adjacent endpoints.** The JSON report and the PDF of the same stored report disagreed, because one endpoint finalized the AI plan and the other did not.
- **A dollar the product could not justify.** A tax-loss-harvest saving rendered beside copy saying "we can't size it for you". It took four fixes, because four independent authors could attach a figure to that one claim: the prompt, the ranker, the shared card chrome and a read-path fallback.
- **Verdicts decided in many places.** An inventory found 22 user-facing conclusions, each decided in 4–22 separate places.

Finablo built a deterministic harness for this: 10 hand-coded facts across 22 surfaces and 20 hand-written cohorts. Replayed blind against 5 real past releases, **it caught 2**. The misses were all things nobody had written an extractor or a cohort for. Hand-coded coverage only finds what someone already anticipated, and that is the gap this project targets.

## Why now

- **AI-written copy is everywhere.** Assistants, summaries and generated recommendations produce sentences no test author saw in advance.
- **Surfaces multiply.** Web, email, PDF, push, export, chat, mobile, with one fact rendered through all of them.
- **Frontier multimodal models can read screens.** Muse Spark takes images, PDFs and video with a 1M-token context. Extraction and judgement that needed humans now cost cents. What is missing is the *system* that makes those judgements complete, grounded, verified and remembered.

## Why a prompt is not enough

The obvious alternative: screenshot everything and ask a strong model, "find the inconsistencies." It helps, and we use it as our benchmark baseline. It also has structural limits that no prompt removes:

1. **Coverage is the tester's, not the model's.** It sees only the personas and screens someone chose to capture. The bugs above lived in personas nobody tried.
2. **No oracle.** It can say two numbers differ, but not which one is right, or that both are wrong.
3. **No memory of intent.** It does not know that the fee increase was planned, that "$1.2K" and "$1,199" are the same by policy, or that last release's finding was accepted.
4. **No change awareness.** It reviews a snapshot, not a release. It cannot say "this sentence changed meaning since the last build and nobody said why."
5. **Unmeasured precision.** It reports plausible-sounding issues with no reproduction. Teams stop reading after the third false alarm.
6. **Flat cost.** Every release costs the same model spend, and nothing is learned.

## Problem we are solving in the hackathon

> Given a web application and a new release, automatically find the semantic issues that would mislead a real user, across every surface and the personas that matter. Prove each one with reproducible evidence, separate them from intended changes, and do it with measurably higher recall and precision than asking a frontier model directly.

## Out of scope

- Functional correctness (does the button work): existing E2E tools do that.
- Visual or pixel regressions: existing snapshot tools do that.
- Taste and UX quality judgements beyond explicit persona-fit rules. Human review remains the owner of taste.
- Deciding what is *correct* when the product owner has not said. The auditor asks, and records the answer in the contract.
