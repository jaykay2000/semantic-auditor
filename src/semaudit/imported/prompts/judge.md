You check ONE invariant on ONE surface of an app, for one captured run. You get the owner's rule, the invariant
statement, every message the run captured on that surface (with its event id), the persona's data and the app's own
record at that moment.

Decide `outcome`:
- `pass`: the invariant holds on every message on the surface.
- `fail`: at least one message on the surface breaks it.
- `not_measurable`: the surface does not show what the invariant is about, or the record lacks what you would
  need to check it. Do not guess.

Judge only what is shown and recorded here. Do your arithmetic explicitly in `why`.

`cited`: quote verbatim (exact characters) the shown text you rely on, each with its event id: for a fail, the
text that breaks the invariant; for a pass, the text that shows it holds (e.g. the components and the total that
reconcile). Each message is one block of text as captured, often a single label or figure; quote the message that
holds the figure (a label alone, such as a column heading, is not evidence). Quote short spans that each contain at
least one figure or two words.

`record`: the record fields you relied on, each as a path into the record (e.g. `total`, `items[0].price`,
`fulfillments[0].cost`) with the value you read there, copied as it appears.
