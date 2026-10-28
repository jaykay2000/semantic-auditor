You are auditing one release of a product for problems in what its users experience. You are given the
product owner's contract (their rules and the product's vocabulary) and the captured experience of each test
persona: every message they were shown and every action they took, in time order.

Apply the contract's rules to what each persona experienced.

What to report, as findings in the required JSON format:
- one finding per problem; you may group personas who experienced the same problem on the same target;
- `rule`: the contract rule id; `label`: only for coherence rules, else null;
- `target`: for coherence, kind `relation` with the two `features` and the `decision`; for load, kind `story`;
  otherwise kind `event` with the message's `feature`, `surface` and `message_key`, exactly as captured;
- `severity`: the level the contract assigns to that rule (and label, where it sets one per label);
- `confidence`: how sure you are;
- `cited`: every event the finding relies on, by persona and event id, each with a VERBATIM quote of that
  event's text (or empty for a user action); `why`: one or two sentences.
Report nothing that you cannot tie to cited events. If there are no problems, return an empty list.

You are given every persona's story for this release in one input. Judge all of them, then return all findings.
