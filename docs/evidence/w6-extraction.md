# W6: extraction from real captures (2026-10-26)

**Result: ACCEPTED.** On captures of every persona on 2.3, 2.4 and 2.4.1 (45 stories, 436 message impressions,
55 distinct messages), Muse Spark's extraction matched the hand-authored gold exactly for **every** message on
**3 of 3 fresh repeats**: hero and boundary directives 15/15, the rest 40/40. Bar: hero 100%, rest ≥ 90%.

Reproduce: `semaudit capture --contract examples/northbound/contract --release <r> --run-id w6` for 2.3, 2.4 and
2.4.1, then `python3 scripts/w6_run.py --run runs/w6 --repeats 3 --max-usd 1`. W6 cost **$0.36** in all (three
attempts of three repeats each).

## What runs
- `semaudit.story.build.story_from_episode` (no model): messages from the app's own markers (`data-message-key`,
  `data-feature`, `data-channel`, `data-shown-at`, email/push headers), user actions from the steps that ran,
  user-initiated chat turns from the contract's `user_turn` marker, and **truth snapshots** read from the oracles
  after each step. Rules read a fact's truth **at the moment the message was shown** (Maya's banner: 2 seats;
  after she books: 1), and a charge as finally charged (Sam & Alex: EUR 18).
- `semaudit.extract.messages.extract_unique`: each distinct (feature, channel, text) is extracted once per run,
  in batches. The rubric classifies messages independently, so this is the same task as per-story extraction at
  about a twentieth of the cost, and identical text always gets an identical answer.
- Gold: `tests/fixtures/extraction_gold.py`, hand-authored for every key the app renders (core and 2.3 included);
  seat and room counts are read from the rendered text because they vary by persona.

## What the attempts found
| Attempt | Result | Finding | Change |
|---|---|---|---|
| 1 | hero 9–10/15, rest 95% | Gold errors: the family's banner really says 9 seats; the confirmation's "Switching… is available until…" really is an offer | gold reads counts from the text; that line is a directive |
| 1 | | Rubric ambiguities the model split on: does a conditional message explain its tradeoff? is a stated deadline on an option already held an urgency cue? what decision does a retrospective message carry? is "After you book, you can switch…" an offer now? | rubric made explicit on all four |
| 1 | | A latent false positive: "line-item amounts are fee claims" would read a fare price (EUR 258) as a fee and set up a U2 mismatch | rubric: fares, taxes and totals are not fee claims |
| 2 | hero 13/15, rest 98–100% | The W1b gold had `cg.upgrade` as *urge* (old U-b wording); the README's own strength table uses that copy as its *suggest* example | gold corrected to the README; retrospective strength is *inform* |
| 3 | **15/15 and 40/40, ×3** | — | — |

## Limits
- Development set again: the same author wrote the copy, the rubric clarifications and the gold. The sealed
  benchmark is the honest test.
- The rubric changed after W1b's 75/75; the owner chose not to re-run W1b. W8 re-tests the full status vectors
  from these real captures.
- `pw.card.optin` (2.3 only) flipped between information and directive on 2 of the attempt-2 repeats, then held;
  it is not a hero message, but it is the least stable wording in the set.
- U2 still compares a fee claim with the fee the story finally charged; matching a claim to its own transaction
  item (lock vs upgrade) belongs to W9.
