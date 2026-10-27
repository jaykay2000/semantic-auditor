# Normalized formats and the matching rule (frozen before any benchmark run)

Every condition (semaudit-full, B-judge-1, B-judge-N, B-explore, ablations) is scored by ONE matcher,
`src/semaudit/bench/match.py`, over two formats defined in `src/semaudit/bench/findings.py`:

- `findings.schema.json`: what a system raised on one release, in one run.
- `truth.schema.json`: the ground truth for one release (sealed until scoring; the custodian converts it).

## Target: what a finding or truth item is about

| kind | identity | used for |
|---|---|---|
| `relation` | the unordered feature pair + the decision | coherence rules (P2) |
| `event` | feature + surface + message key | every other single-message rule |
| `story` | the persona's whole experience | load rules (P3) |

Time (`at`) places an event; it is never part of its identity. A truth item made of several events lists one in
`target` and the rest in `also_targets`; a finding about any one of them is about that item.

## Matching rule (refines docs/08-evaluation.md; applied identically to every system)

1. **Units are persona-occurrences.** A finding about three personas is three units, and so is a truth item about
   three. Grouping is therefore neutral: three separate findings and one grouped finding score the same.
2. A finding unit **matches** a truth unit when persona and rule agree, the finding's target is one of the item's
   targets, and the label agrees **where the truth carries one** (P2 only: `conflict` and
   `unexplained_tradeoff` are different answers). Each truth unit is matched at most once.
3. A unit that matches no issue but lands on a **negative control** (same persona, rule and target; label ignored)
   is a false positive on that control's pattern.
4. Every other unit is **unmatched**: a false positive unless the blind adjudication accepts it as a real,
   unseeded issue, in which case it is a true positive and joins every system's denominator.
5. Findings about personas outside `truth.personas` (episodes the release could not measure) are not scored.
6. A rule the auditor reports only as "also violated" on an event another rule's issue owns is scored as a
   finding (`secondary: true`). A baseline may likewise report several rules on one event.
7. **Evidence support:** a finding is supported when it cites at least one event and every cited event exists in
   the captured stories with the quote verbatim in that event's text.

## The custodian's converter

The sealed ground truth stays outside the repo until scoring. Its custodian converts each `bench-NN.yaml` to
`truth.schema.json` with a converter kept beside it: one persona per item, `kind` from issues /
negative_controls, `pattern` = the issue kind or the docs/08 negative-control pattern, `relation` → a relation
target, attention-load items → a story target, other items → an event target per event (first in `target`,
the rest in `also_targets`), `objective`, `severity`, and attribution (`delta`, `features`). Evidence blocks are
dropped. `truth.personas` lists the personas whose head episodes were measured.
