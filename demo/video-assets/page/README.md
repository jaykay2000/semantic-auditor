# Release review page: video stills

Rendered with Playwright (Chromium) from the built `file://` pages at 1920×1080, device scale 2 (3840×2160 PNGs),
network blocked. Each page was built with `semaudit.report.page.build` into a scratch folder outside any run folder
(the same as `semaudit report <review.json> --out <folder>`); nothing was written into a run folder. Scene numbers refer to `docs/archive/07-demo-reframe-draft.md` (superseded).

| File | Scene | What it shows |
|---|---|---|
| `01-spree-overview.png` | 0:30–1:12 hero, 2:38 close | Spree beta2 → beta3: verdict (policy would say *Needs owner review*, provisional, with the reason), the four delta counts (0 new · 1 resolved · 1 pre-existing · 0 unconfirmed), the issue list, and Jo's email issue: shown **$0.00** vs record **$5.00** |
| `02-spree-email-issue.png` | 0:00 hook, 0:30–1:12 | Same issue, scrolled: Jo's confirmation email (Subtotal … Shipping Standard **$0.00** … Order Total $232.16) beside the order record at that step (delivery_total $5.00 highlighted), then beta2 → beta3 for the same email: $0.00 → $5.00, "no longer shows it" |
| `03-spree-evidence.png` | 0:30–1:12 (trust), 2:25 Meta | Who saw it (30 shoppers; 3 more named without a usable quote, not counted), Evidence (some citations refused), Confidence low with its reasons, Verification *unverified* (evidence checked, nothing else run), Severity; model line (Muse Spark Open on Baseten, $0.00 this run from cache, $9.44 if read fresh) |
| `04-spree-persona-story.png` | 0:30–1:12 ("click one … the shopper's steps") | Jo's 12 checkout steps in order with each step's capture, step 11 ringed, and every message of that step in capture order with the quote marked |
| `05-finablo-limits.png` | 1:50–2:25 | Finablo 10ff1e3 → a183626, 61-year-old: shown **$32,500** vs contract reference **$35,750**; base → head *$32,500 → $35,750*, resolved; the list shows the other limit issues (Walt's $24,500 vs $32,500, the $7,500 IRA) |
| `05b-finablo-ira-unconfirmed.png` | 1:50–2:25 | The IRA headline "Open a Roth for **$7,500**/yr." vs $8,600, *unconfirmed*: both releases still show the quoted text |
| `05c-finablo-overview.png` | 1:50 | Finablo top of page: 0 new · 2 resolved · 3 pre-existing · 1 unconfirmed |
| `06-northbound-maya.png` | 1:12–1:27 | Maya, Northbound (fictional app): *Unexplained tradeoff between Fare Lock and Price Watch*, new in 2.4; moment A (wait for a lower fare) ⇄ moment B (lock today's fare) side by side |
| `06b-northbound-maya-story.png` | 1:12–1:27 | Maya's story lanes with A and B ringed and linked, live intervals drawn |
| `06c-northbound-maya-diff.png` | 1:12–1:27 (optional) | Diff mode: 2.3 ghosted; the Fare Lock banner is *+ added* in 2.4 |
| `07-northbound-lena-cleared.png` | 1:12–1:27 | Lena: nothing raised; *Cleared · P2 explained tradeoff* with the concierge message that explained it |
| `08-spree-draft-ticket.png` | 0:30–1:12 ("Draft ticket"), 2:38 | The draft ticket, the same markdown `semaudit ticket` writes, marked *draft · not filed* |
| `09-spree-tax-inclusive-line.png` | Optional beat | The tax-inclusive line: shown **$43.19** vs item_total **$39.99**, pre-existing in both releases, with the capture crop and the item's neighbours on the page |

Deep links (open the built page with these hashes): Jo `#persona=jo&mode=base&issue=R-v6.0.0.beta2-U1-delivery-total-order-email-order-confirm-b3efaba3&step=s11`
(add `&ticket=1` for the ticket); Finablo `#persona=target_61&mode=base&issue=R-10ff1e3-H1-unnamed-fact-first-move-plan-882347a724-a698fc88`;
Lena `#persona=lena&mode=head&issue=`. To regenerate a still, rebuild the page with
`semaudit report <review.json> --out <folder>` and screenshot `<folder>/index.html#<deep link>` at 1920×1080 (the
one-off script that rendered these stills is not kept).

## Design decisions

- **Every issue is first-class.** The old page put factual issues in a side rail. Now one list holds them all, grouped by
  release delta (new, resolved, pre-existing, unconfirmed). Each row shows its own *shown → true* pair.
- **Delta is the only thing colour encodes.** New is red, resolved green, pre-existing amber and unconfirmed violet (dashed).
  These colours appear on the count tiles, group headers and pills. The one exception is the shown-vs-true hero: the
  wrong figure is red and the true one green. Severity, confidence and verification are written as words in neutral
  chips. They never share a colour, so "unverified" or "low confidence" can't read as stronger than it is.
- **The hero is a split comparison: what the user was shown ≠ what is true.** Both values are in big numerals. Under
  each sits its source: the exact captured text with the quote highlighted, and the record table with the fact highlighted.
  The true value comes from the app's record, or for Finablo from the contract's reference values. If neither holds it,
  the page shows the reader's own statement and labels it "As the reader stated it".
- **Base → head as a two-column diff.** The same message is shown in both releases, with the quote marked red where it
  is still shown and the new figure marked green where it changed. Under the diff sits the review's own `delta_basis`
  sentence.
- **The persona story adapts to its length.** Northbound (≤ 60 messages) keeps the lane timeline with A/B ringed and
  linked. Spree and Finablo (hundreds of page elements) get one card per step with that step's capture, the cited step
  ringed, and a drawer listing every message it showed, in order.
- **Trust is a row of four boxes**: Evidence, Confidence (with its basis), Verification (each step ✓ / ✗ / not run) and
  Severity, plus a model and cost strip read from the manifest.
- **Video legibility**: 15 px body, 26 px titles, 40–44 px key numbers, tabular numerals, system fonts only
  (Inter if installed, else SF Pro / system-ui; ui-monospace for quotes and ids). The page is one offline file: no
  CDN, no web fonts. The old template loaded Google Fonts; that link is removed. It is laid out for 1920×1080 and
  1440×900 with no horizontal scroll.

Borrowed from:
- **Sentry issue detail**: a header with counts and who was affected, highlights promoted above the evidence, and
  evidence sections in order beneath it.
- **GitHub PR diff**: the split base | head view, with red/green marking only the changed span.
- **Stripe dashboard**: KPI tiles with a big number, a label and a one-line subtitle.
- **Linear's redesign**: a neutral base with one restrained accent (indigo, used for selection and actions), surfaces
  separated by elevation, and tight alignment.
- **Vercel Geist**: light tinted fills for chips, mid-tone borders and dark text for status.

## Data the page adds beside review.json (never in place of it)

`page.py` injects a third blob, `extras`. It holds each cited persona's contract reference values and their **base-release**
record snapshots, read from the run's episodes, so a resolved issue's true value comes from the base record and not
from the head's. It also holds the draft ticket for each open or resolved issue, from `semaudit.report.ticket`.
review.json's shape is unchanged.
