You are auditing one release of a product for problems in what its users experience. You are given the
product owner's contract (their rules, with exceptions, plus the product's vocabulary) and the captured
experience of each test persona: every message they were shown and every action they took, in time order,
with the readings of the product's ground-truth oracles over time.

How to judge, rule by rule:
- Apply each rule exactly as the contract states it, by its `kind`.
  - universal: it holds for every persona; it has no exceptions.
  - conditional: a message is permitted only if EVERY condition of an exception holds, the message is inside
    that exception's scope (features, components, surfaces), and it was shown on or before the exception's
    expiry. Evaluate `data` conditions from the data given (exact timestamps, oracle readings, the persona's
    context); evaluate `judged` conditions from the message text. If any condition fails, the rule is violated.
  - coherence: when more than one feature gives an active recommendation about the same decision, the product
    must reconcile incompatible actions, or explain the material tradeoff between compatible ones, while both
    recommendations are live and before the persona decides. Label each violation `conflict` (incompatible
    actions) or `unexplained_tradeoff` (compatible actions whose material tradeoff is not explained). A
    reconciling message counts only if it addresses both recommendations, while both are live, before the
    decision.
  - load: count only what the rule counts (its channels, its window), and leave out anything it excludes.
- An exception to one rule never excuses a violation of another rule.
- A claim is false only when an oracle reading at that time contradicts it.
- Legitimate behaviour is not a problem: a permitted exception, a reconciled or explained tradeoff, a repeated
  confirmation, a persona-specific difference, an actionable offer after a commitment, recommendations that never
  overlap in time, a claim that cannot be checked, a user-initiated conversation. Do not raise these.

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
