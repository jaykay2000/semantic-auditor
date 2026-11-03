# Why SRA keeps discoveries: three AI agents exploring one store (2026-10-29 to 2026-11-01)

**What this shows:** exploring AI agents find real problems, but each run finds a different set, and no single run
finds them all. SRA's own reviews cover less ground and give the same answer every time. So SRA is not offered as a
better explorer. It is the layer that keeps what explorers find, as checks that run again on every release
([imported checks](../imported-checks/README.md)).

**Claim level:** a preregistered exploratory case study on one store (Spree, release 6.0.0.beta2 → beta3), two
trials per system. No significance tests, no ranking of agents.

## Method

- **Systems:** three AI agents, each run as its own product with its own tools: one built on Muse Spark (Meta Model
  API) and two other AI agents, not named here. Plus SRA itself (Muse Spark Open, reader mode). Two fresh trials each.
- **Same input for all:** the store owner's 11 written rules, a glossary, the store's configuration, both releases
  running live, the mail catchers and a read-only view of the store's order records. Same time ceiling (120 minutes).
  Nothing that names the project or the releases' differences was shown to any system.
- **Task:** find places where what a shopper or staff member is shown or sent is wrong, inconsistent or misleading,
  and say which rule it breaks.
- **Grading:** every reported finding was graded `real` or `false_alarm` and assigned a problem type (a "family"),
  blind to which system reported it, by two independent graders, with the owner adjudicating disagreements.
  The protocol, the key and the decisions log were fixed before any result was read.

## Results

| Measure | Result |
|---|---|
| Problem types found by the six agent runs together | 18 |
| Problem types found by the best single agent run | 13 of 18 |
| Two runs of the same agent: problem types found by both | 8 of 17 · 5 of 9 · 7 of 8 (the Muse Spark agent) |
| SRA's own reviews: problem types found | 3 to 4 per run, the same ones run to run (3 of 3, 4 of 4) |
| Agent findings graded real | 63 of 72 (each agent between 83% and 95%) |
| Agent findings graded false alarm that became a saved check | 0 of 6 in the held-out set ([conversions](../imported-checks/heldout-conversions.txt)) |
| Agent findings with a real part that became a saved check | 6 of 51 in the held-out set |

How to read it:

- **Each run finds a different set.** Two runs of one agent, same store, same rules, same time, shared as little as
  about half of the problem types they found. Whatever a run found and the next did not is lost unless something keeps it.
- **No single run is enough.** The best single run found 13 of the 18 types all six runs found together.
- **SRA is narrower and repeatable.** It checks the journeys and rules it was given, so it found fewer types, the same
  ones every time. That is what a release check should be.
- **The two fit together.** Agents give breadth; SRA turns what they find into checks that replay with evidence on
  every later release, and says fixed, still open or came back
  ([saved-check stability](../saved-check-stability-2026-11-01/README.md)).

## Limits

- One store, one release pair, two trials per system. These are descriptions, not rates.
- Only 6 of 57 held-out findings became saved checks (11%): the step check refuses a finding rather than guess a step
  the report does not give. Widening that is the main open work.
- The graders' and agents' raw transcripts are kept privately; this page reports counts only.

## Source

Counts from the experiment's scored results (`scores.json`, sha256
`085d56ee4ba953a148ca82bcd53fd05dd4a46adeb666239082452e19973c928c`; `final-grades.json`, sha256
`47ae43ce0a8ef293ce516552cee7f604b2bfab9c91d4ee08e2b46f7ac28d23df`), kept in the owner's private experiment folder.
The held-out split and conversions are public: [holdout.json](../imported-checks/holdout.json),
[heldout-conversions.txt](../imported-checks/heldout-conversions.txt).
