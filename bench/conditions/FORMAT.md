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
7. A finding a system raised that the format cannot express (for example a coherence finding naming a single
   feature) is dropped, listed as `malformed`, and **scored as one false positive**. It is never repaired.
   This is how a negative control that no well-formed finding can land on (a `duplicate_ok` repeat of one
   feature's own advice) still costs a system that raises it.
8. **Evidence support:** a finding is supported when it cites at least one event and every cited event exists in
   the captured stories with the quote verbatim in that event's text.

## The custodian's converter

The sealed ground truth stays outside the repo until scoring. Its custodian converts each `bench-NN.yaml` to
`truth.schema.json` with a converter kept beside it: one persona per item, `kind` from issues /
negative_controls, `pattern` = the issue kind or the docs/08 negative-control pattern, `relation` → a relation
target, attention-load items → a story target, other items → an event target per event (first in `target`,
the rest in `also_targets`), `objective`, `severity`, and attribution (`delta`, `features`). Evidence blocks are
dropped. `truth.personas` lists the personas whose head episodes were measured.

## Scoring additions after the Oct 27 audit

- **Evidence support is strict.** Every persona a finding names must have at least one cited event; every cited
  event must exist in the captured stories; a cited *message* needs a non-empty quote found verbatim in its text
  (user actions have no text and need only exist).
- **Every proportion is reported with its raw counts and a 95% Wilson interval** (precision, recall, the
  negative-control false-positive rate overall and per pattern). Small denominators read as small.
- **Attribution (E3)** is scored over matched units whose truth carries a `delta`: is the finding's
  new / changed / existing right, and does it name every responsible feature. A system that reports no delta is
  shown as not reporting, not as wrong.
- **Freshness and cost.** `cost_usd` is what was actually spent (a cache hit costs 0); `cost_if_fresh_usd` is the
  comparable figure. Stability (Jaccard) refuses any run that was not fully fresh.
- **Adjudication.** Pre-adjudication scores treat seeded subjective items as hypotheses and are labelled so.
  Headline scores come only after `apply_verdicts`: a seeded item judged not real leaves the denominator, an
  unseeded finding judged real joins every system's denominator, and all systems are rescored against the same
  adjudicated truth. Sheet evidence is the sorted union of every source's citations, or, for a seeded item no
  system raised, the captured events its target names.
