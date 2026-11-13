# Add your app, and use another model

For someone who has cloned this repo and wants SRA to review **their own** web app. It covers what SRA needs from
the app, the contract, the adapter, the first run, what it costs, and how to point SRA at a model other than Muse
Spark. Every command below was run on a fresh clone (2026-11-01) unless it is labelled otherwise.

The worked example throughout is the Northbound demo app in [`examples/northbound/`](../examples/northbound/). Copy
its contract and adapter and change them; that is the intended way to start.

## What runs without a model key

Tested on a fresh clone with no key in the environment:

| Step | Works without a key? |
|---|---|
| Install and run the tests ([README, "Run the tests"](../README.md#run-the-tests)) | yes; every model call in the suite is mocked |
| `semaudit contract check <dir>` and `semaudit contract review <dir> --out page.html` | yes |
| `semaudit capture` (drives the app in Chromium and records everything it shows) | yes; it makes no model call |
| `semaudit review`, `repro`, `checks run` | **no** |
| `semaudit verify-report` | **yes**, when the review's pinned inputs and the model cache are present: it runs offline from the cache and spends nothing. A fresh clone has neither |

There is **no cached replay on a fresh clone**. The model cache (`.semaudit-cache/`) and the run folders (`runs/`)
are not committed, so nothing can be reviewed from cached answers. Without a key, `review` stops with
`cannot measure: META_MODEL_API_KEY is not set (expected in .env); provider 'meta' needs it` and exit code 2.
Once you have run a review yourself, re-running it (`--reuse`) is served from your own cache at $0.

## What SRA needs from your app

SRA drives your app like a user, in a real browser, and compares what the app **said** with what the app **knows**.
So it needs two things from you beyond the app itself:

1. **A way to read the app's own record**: "oracle" endpoints that return the true state as JSON (an order's total,
   a booking's status, seats left). The Northbound app serves them at `/api/oracle/...`.
2. **Test hooks** (all optional, each one adds something):
   - `reset`: start every scenario from a clean app;
   - `persona`: create the test user and their situation;
   - `clock`: set a simulated time. Without it, anything the app sends later (a reminder email the next day) is
     recorded as "not measured";
   - `world`: seed the state the oracles will report.

Building these into your app is usually the biggest piece of work. Run them only in a test build, never in
production.

## 1. The contract: a folder of YAML

Start from a copy of [`examples/northbound/contract/`](../examples/northbound/contract/). Each file:

| File | What it says | Northbound example |
|---|---|---|
| `app.yaml` | name, `base_url`, `releases`, test `hooks`, `launch`, `adapter`; `fictional` and `data` (`synthetic` or `real`) | releases `2.3`, `2.4`, `2.4.1`; hooks under `/api/test/` |
| `subject.yaml` | who the user is (`noun`) and the fields that describe their situation | `traveller`; route, departure time, flexible |
| `personas.yaml` | test users: their `context`, the `world` to seed, any experiment arms | Maya, flexible, departs in 42 days |
| `scenarios.yaml` | time-ordered steps: `{at: "D0 10:03", do: <verb>, params: {...}}`; `when_offered: true` for an action a release may not offer | search, open the cheapest fare, book, read the inbox two days later |
| `surfaces.yaml` | every place the app talks to the user, and how to find its messages: `web` (CSS selector), `chat`, `email` and `push` (a folder the app writes to), `pdf` | fare page, checkout, inbox, itinerary PDF |
| `oracles.yaml` | the app's own record: endpoint templates and the JSON fields to read, after every step | `/api/oracle/booking?traveller={traveller}` |
| `facts.yaml` | the kinds of claim a message can make, and which oracle field holds the truth | "seats left" is `inventory.seats_left` |
| `state.yaml` | state derived from the user's actions (booked or not, a lock held) | `booking_status` set by `book` |
| `features.yaml` | the app's features and how a message is attributed to one (a DOM attribute or a header) | `core`, `price_watch`, `fare_lock` |
| `decisions.yaml` | the decisions your app advises on, and which advice conflicts | `when_to_book`: book now vs wait for a drop |
| `principles.yaml` | **your rules**: what must hold for every user, with severity and a `check` | "every scarcity claim matches our own data" |
| `rubric.md` | instructions for reading a message (its kind, urgency cues) | urgency cues U-a to U-c |
| `release_policy.yaml` | how issues become a recommendation (Ship / Hold), top row first | hold on a verified critical issue |

`semaudit contract check <dir>` validates the cross-references and lists the items you have not yet approved.
`semaudit contract review <dir> --out page.html` renders the whole contract for you to read. Without `--out`, it
serves the page with working Approve buttons. `semaudit contract approve` records approval, pinned to each item's
content hash; a review of an unapproved contract is always marked provisional.

```bash
semaudit contract check examples/northbound/contract      # lists each pending item, e.g. "  pending: rule:P2"
semaudit contract approve examples/northbound/contract --item rule:P2 --item persona:maya --by you
```

Item keys are the ones `check` prints: `rule:<id>`, `exception:<id>`, `decision:<id>`, `feature:<id>`,
`persona:<id>`, `scenario:<id>`, `app:<name>`, `policy:release`, and `state:all`, `surfaces:all`, `oracles:all`,
`facts:all`, `subject:all` for the files approved as a whole. Repeat `--item` for each. Change an item and its
approval no longer applies.

### Check verbs: what a rule's `check: {must: …}` can say

A `universal` rule names one verb in `check.must`. These are the verbs the rule engine evaluates
(`src/semaudit/relate/rules.py`, `_UNIVERSAL`):

| `must:` | Also needs | What the code checks |
|---|---|---|
| `match_oracle` | `claims` (fact ids), optional `oracle` (one or a list) | each claim of those facts equals the app's own record at the moment it was shown (`facts.yaml` says which oracle field holds the truth). With `oracle`, the claim is compared with that oracle's field of the fact, not the fact's first source, so one fact can be checked against the store's record by one rule and against an expected value by another. A fact with no recorded value is skipped, never a violation |
| `match_charge` | `claims`, `charge` | each displayed amount equals what the user is finally charged (the state value `charge` names, same feature); no charge in the story means not applicable |
| `agree_across_surfaces` | `claims` | every claim of the same fact that one persona sees reads the same on every surface, when shown in the same state; no oracle needed |
| `agree_across_states` | `claims`, `states: {var: [before, after]}` | a fact shown before a state change (for example signed out → signed in) reads the same after it, when nothing else changed |
| `precondition_holds_at_shown_time` | — | each recommendation's action is possible at the moment it is shown (the action's precondition in `decisions.yaml`) |
| `offered_actions_complete` | optional `actions` (scenario verbs) | every action the app offered and the user took completes; a step your adapter reports with `AppFailed` (or `StepResult(app_error=…)`) is a violation, with the app's own reason as evidence |

**A figure that is correct in more than one form.** A price can be right with or without VAT, before or after a
promotion. If you accept a second form, declare it on the fact as a `basis`. A claim that misses the true value
but states a basis declared for its surface is correct in that basis: the four verbs above all accept it, and the
issue text says which basis. A form you did not declare is still a violation. Bases are evaluation only, so adding
one costs no new reading: re-run the review and it replays for free.

```yaml
- id: unit_price
  sources: [{oracle: expected, field: unit_price}]
  bases:
  - id: with_vat
    value: unit_price * (1 + tax_rate / 100)     # numbers, fact ids, + - * / and parentheses
    surfaces: [storefront_checkout, storefront_order_page]   # omit: every surface
    round: 0.01                                  # round to cents before comparing
  - id: after_promotion
    value: unit_price * (1 - promo_percent / 100)
    when: discount_total > 0                     # the basis applies only when this holds
```

On Medusa v2.18.0, seven bases written from the owner's rulings cut 129 issues to 35 on a free replay. The release
with a real VAT bug kept every one of its VAT violations, and 1,037 claims nudged off a basis were all still
violations ([evidence](evidence/fact-bases-medusa.md)).

A `universal` rule with no `must:` but `applies_to: {message_kind: …, state: …}` forbids that kind of message in
that state. Any other verb is not evaluated: the review lists the rule as not measured, never as passed
(`review --reader` judges the rule's text instead). `conditional`, `coherence` and `load` rules have their own
shapes; Northbound's [`principles.yaml`](../examples/northbound/contract/principles.yaml) has one of each.

Field-by-field formats: `src/semaudit/contract/schema.py`. The Northbound rules and why they read as they do:
[`examples/northbound/README.md`](../examples/northbound/README.md).

### `app.launch`: let SRA start each release

```yaml
launch:                    # in app.yaml; omit it and SRA uses an app you have already started at base_url
  cwd: ..                  # relative to the contract folder
  cmd: ["{python}", "-m", "uvicorn", "northbound.app:app", "--host", "127.0.0.1", "--port", "{port}"]
  env: {NORTHBOUND_OUTBOX: "{scratch}/outbox"}
  sink_root: "{scratch}"   # email and push folders in surfaces.yaml are resolved under this
  health: /                # SRA polls this until the app answers
release_env: NORTHBOUND_RELEASE   # the release to start is passed in this env var
```

`{python}`, `{port}`, `{release}` and `{scratch}` (a fresh temp folder per launch) are filled in by SRA.

### Marking messages

On a web page, a message is an element that matches the surface's `message_selector` and carries a
`data-message-key` attribute (optionally `data-feature`, `data-component` and `data-shown-at`). SRA stores the
element's rendered text as the message, and later accepts a quote as evidence only if that exact text is in the
stored page (after HTML entities are decoded). So:

- **The marked element holds its text directly, with no tags inside it**, not even `<b>` or `<span>`.
  `<p data-message-key="pricing.pro">Pro costs $12 per month.</p>` works.
  `<div data-message-key="pricing.pro"><h2>Pro</h2><p>Pro costs $12 per month.</p></div>` does not: the rendered
  text ("Pro", a line break, "Pro costs…") is not in the page source, so no issue on it can be verified.
- Keep the text on one line with single spaces; the browser collapses runs of spaces and line breaks.
- Mark the innermost element that holds the words. A heading is a separate message, or no message.

Northbound does this with one template macro (`examples/northbound/northbound/templates/macros.html`).
`semaudit capture` and `semaudit review` print a `warning:` line, with the key and the page, for every marked
message whose text is not in the stored page.

### Email and push sinks

SRA does not read a mailbox. The app writes each email or push notification it sends as **one JSON file** in a
folder, and SRA reads every new file after each step, in file-name order. The folder is the surface's `sink` in
`surfaces.yaml`, under `app.launch.sink_root`. Each file:

```json
{
  "message_id": "m000001",
  "sent_at": "2026-11-02T10:01:00+00:00",
  "headers": {"X-Message-Key": "pw.email.forecast", "X-Feature": "price_watch"},
  "text": "Prices on your dates are likely to drop over the next two weeks. We suggest waiting.",
  "subject": "Your fare forecast"
}
```

- `headers["X-Message-Key"]` is **required**: a message without it is captured but not read as a message.
  `capture` and `review` print a `warning:` line with the count. `X-Feature` attributes it to a feature.
- `text` is the message as the user reads it; quotes must come from it.
- `sent_at` (ISO time with a zone) places the message in time when the app runs on the simulated clock; otherwise it
  is placed at the step that received it.
- Every other top-level field (`subject`, `to`, `title`…) and header is kept with the message.

### Two things to declare about how a surface is captured

Both are fields on a surface in `surfaces.yaml`. Without them a review can raise false alarms.

- **An email sent in two formats** (an HTML part and a text part) is one email. If your sink writes each part as
  its own file, put each part on its own surface and mark the second one `format_of: <the first surface>`. Both
  parts are still read for claims, so a figure that differs between them is still found, but a load rule ("one
  confirmation per order") counts the email once. A second email is still counted.
- **A page captured before its step's action takes effect.** A step's captures are normally read in the state
  after the step (a confirmation shown at 10:06 follows the 10:06 action). If your adapter captures a page as it
  first appears and *then* acts (a checkout form before the shopper fills it in), mark that surface
  `shown_before_action: true`. Its figures are then compared with pages in the state before the action, not after
  it. In the Spree test, the address step shows the total before tax and delivery are known; without this
  declaration it was compared with the delivery step and raised four false alarms.

## 2. The adapter: your scenario verbs, in Python

The adapter turns each scenario verb into clicks and requests on **your** app. It is a file named in `app.yaml`
(`adapter: ../adapter.py`) that defines a class `Adapter`. Northbound's is
[`examples/northbound/adapter.py`](../examples/northbound/adapter.py) (about 200 lines). The full interface is in the
docstring of `src/semaudit/adapters/base.py`; the shape is:

```python
from semaudit.adapters.base import AppFailed, StepFailed, StepResult

class Adapter:
    def persona_body(self, persona, context):   # JSON body for your `persona` hook
        return {"user": persona.id, **context}

    def oracle_params(self, persona, session):  # values for the {placeholders} in oracles.yaml
        return {"user": persona.id}

    def run_step(self, step, session):          # one scenario step
        fn = getattr(self, f"verb_{step.do}", None)
        if fn is None:
            raise StepFailed(f"unknown verb {step.do!r}")
        return fn(step, session)

    def verb_open_product(self, step, s):       # session.page is a Playwright page
        s.page.goto(f"{s.base_url}/products/{step.params['id']}")
        return StepResult(landed="product_page")  # a surface id from surfaces.yaml; SRA captures it
```

Drive through the browser wherever a user would. Use `session.http` only for hooks and oracles. A verb the app does
not offer in a release returns `StepResult(offered=False)`; the step is then recorded as skipped, not failed.

**Who failed: the app, or the harness.** When the app refuses or fails an action it offered (an error page, a
disabled button where the action should be, the store's own refusal), raise
`AppFailed("<what the user saw>", landed="<surface>")`. SRA captures that surface, records the step as `app_failed`,
and a rule with `must: offered_actions_complete` turns it into an issue. Later steps that fail because of it are
recorded as `blocked`: the persona is still evaluated up to there, and the review says which steps were not reached.
Raise `StepFailed` (or return `StepResult(error=…)`) only when **your harness** could not do the step (a selector broke, a hook timed out). That is a
hole in the measurement, so the whole persona is reported as not measured, never as passed.

## 3. The first run

```bash
semaudit contract check examples/northbound/contract           # exit 1 while items are not yet approved
semaudit capture --contract examples/northbound/contract --release 2.3 --persona maya --run-id first
semaudit capture --contract examples/northbound/contract --release 2.4 --persona maya --run-id first
```

On a fresh clone (no key), each capture took about 6 seconds and printed
`2.4/maya/S-book-flexible: 8 done, 1 skipped, 0 failed; 10 captures`. The episodes are in
`runs/first/episodes/<release>/` and every page, email, push and PDF is under `runs/first/captures/`. Capture exits 2
if a release would not boot, a step failed, or a surface could not be measured; the episodes are still written.

With a model key in `.env` (see the next section):

```bash
semaudit review --contract examples/northbound/contract --base 2.3 --head 2.4 --run-id first --reuse --max-usd 3
semaudit report runs/first/review-2.3-2.4.json            # a static release review page (--reader: *.reader.json)
semaudit serve --review runs/first/review-2.3-2.4.json --by you   # the same page, with decision buttons
```

`review` exits 0 only for a decided Ship (every persona measured and the contract approved), 1 when the owner must
act (including any provisional recommendation), and 2 when it could not measure. The commands that come after a
review (`repro`, `decide`, `decide-release`, `verify-report`) are listed in the
[README, "Review a release"](../README.md#review-a-release).

**What a run costs** (measured figures, all on Muse Spark; yours depend on your app, rules and personas):

- `capture`: no model cost.
- The Northbound 2.3 → 2.4 review work: about $0.79 in total, including development and the falsifiability
  runs ([evidence](evidence/w9-review.md)).
- The Spree reader review of 134 checkouts: $9.44 if read fresh (`manifest.spend.if_fresh_usd` in the Spree
  harness's review; see [demo/video-assets/scenes/README.md](../demo/video-assets/scenes/README.md), note 1).
- Re-running a review from the model cache: $0.000 ([evidence](evidence/w11b-severity-and-page.md)).
- `--max-usd` is required on every `review` and is a hard cap. A model with no price is refused under a cap, so an
  unknown cost can never slip past it.

## Use another model

Every model call goes through one router (`src/semaudit/models/router.py`). Each **role** (a job: `extractor`,
`interpreter`, `cross_checker_extract`, `cross_checker_interpret`, `defender`; for saved checks `importer` and
`check_judge`) is mapped to a provider and a model in `semaudit.toml`, in the folder you run `semaudit` from.
One more role, `smoke`, is used only by `scripts/w1_smoke.py` to check that a key works; no review or check calls
it (default: Muse Spark 1.3 on the Meta API). Keys go
in a `.env` beside it. Start from [`semaudit.toml.example`](../semaudit.toml.example).

**The measured setup is Muse Spark.** Every result in this repo was produced with Muse Spark 1.3 / 1.2 on the Meta
Model API or Muse Spark Open on Baseten ([README, "Models (measured)"](../README.md#models-measured)). Results with
any other model have not been measured.

Built-in providers: `meta` (`META_MODEL_API_KEY`), `baseten` (`BASETEN_API_KEY`) and `anthropic`
(`ANTHROPIC_API_KEY`; install the `[anthropic]` extra).

### Any OpenAI-compatible endpoint

> **Trust boundary: `semaudit.toml` and the contract are trusted, owner-controlled code.** SRA executes the
> contract's adapter as Python, and a `[providers.<name>]` entry sends the value of the environment variable it names,
> as a bearer token, to the `base_url` it names. So run `semaudit` only in a folder whose `semaudit.toml` and contract
> you wrote or have read, exactly as you would only run code you trust. SRA does not try to sandbox either. A key
> split across fields cannot be caught by redaction (below): the endpoint receives the key anyway, so only use one you
> trust.

> **Untested against a live endpoint.** This config is tested offline only: `tests/test_router_config_providers.py`
> sends the calls to a mocked HTTP layer and checks the URL, the key, the pricing and the failure paths. No real
> provider has been called through it.

```toml
# semaudit.toml
[providers.myhost]
base_url = "https://llm.example.com/v1"   # SRA POSTs to {base_url}/chat/completions
key_env = "MYHOST_API_KEY"                # sent as "Authorization: Bearer <value of MYHOST_API_KEY>"
max_completion_tokens = 8000              # optional: default reply cap for this provider

[providers.myhost.prices]                 # optional: USD per million tokens, [input, output]
"my-model" = [0.5, 1.5]

[roles.extractor]                         # repeat for every role you want on this model
provider = "myhost"
model = "my-model"
```

```bash
# .env, beside semaudit.toml (never in semaudit.toml)
MYHOST_API_KEY=...
```

Rules the router enforces:

- **A new name only.** `[providers.meta]`, `[providers.baseten]` and `[providers.anthropic]` are refused. Their
  address and key are part of what the measured runs mean, and `meta`'s cached answers are not keyed by provider, so
  a redefined `meta` would be served the real one's cache. Point a proxy at a new name.
- `key_env` must be the **name** of an environment variable (capital letters, digits and underscores). A value with
  other characters, as most keys have, is refused, so a key pasted there is caught. A missing key
  fails when the first call is made, naming the variable: `MYHOST_API_KEY is not set (expected in .env); provider
  'myhost' needs it`. The value is never printed.
- **https only.** `base_url` must be `https://`. Plain `http://` is accepted only for a loopback host
  (`127.0.0.1`, `::1`, `localhost`), so a model server on your own machine still works.
- **An echoed key does not reach SRA's files or errors.** If the endpoint echoes the key value back (in a reply or in
  an error), as sent, URL-encoded, base64 (standard or urlsafe, padded or not) or hex, SRA replaces it with
  `[redacted: provider key]` before the reply is cached, logged, written to a run or shown, and in every error message.
  A key split across fields, or transformed some other way, is not caught. Values shorter than 8 characters are not
  redacted.
- **Unpriced means unpriced.** Without a `prices` entry the ledger (`runs/ledger.jsonl`) records each call with
  `"cost_usd": null, "priced": false`, never $0, and `--max-usd` refuses the model rather than guess.
- **Prices belong to the provider.** Your provider's calls are priced only by its own `prices` table, even when
  the model has the same name as one a built-in provider prices (for example `meta-models/muse-spark-open-1026`
  served by your own host is unpriced until you price it). Each ledger row of your provider also records
  `"provider": "<name>"`; rows of the built-in providers are unchanged and carry no `provider` field.

What the endpoint must support:

- **Structured output** (`response_format` of type `json_schema` with `"strict": true`). A reply that is not JSON is
  retried with another seed and logged; if it stays unreadable, that reading is "not measurable". A JSON reply that
  does not match the schema is also a not-measurable reading. Neither can ever become a PASS or a confirmed fix.
- `max_completion_tokens` and `seed`, and `reasoning_effort` when a role sets it (leave it off for a model that does
  not accept it).

One more effect: SRA caps a review's confidence at medium unless the second-pass roles run a **different model
family** from the first. A model SRA does not recognise has no family, so it never counts as independent
(`src/semaudit/verify/steps.py`).

## What is not built

- **Automatic onboarding.** SRA cannot yet draft a contract from your docs; `src/semaudit/onboard/` and
  `src/semaudit/explore/` are empty. You write the contract and the adapter by hand, starting from Northbound's.
- **Spoken intent** (turning the owner's voice notes into draft rules) is not built.
- **No list view of saved checks.** `semaudit checks` has `approve`, `run` and `card` only.
