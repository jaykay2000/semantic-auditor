# P2 severity per label, and the page naming what fired the policy and which models ran (Oct 27)

**Why.** An external review of the demo talk track asked why an *unexplained tradeoff* (Maya: a €9, 48-hour lock
offered beside a two-week drop forecast, both true) should hold a release exactly as hard as a *contradiction*
(Kai: "Book now" beside "wait"). With one severity per rule, P2 at `critical` made both hold. The reviewer
suggested having the auditor compute severity from impact; that was declined, because severity is the owner's call
(count-based escalation was removed in audit 2 for the same reason). The owner set a level per label instead.

| Change | Where | Evidence |
|---|---|---|
| `severity_by_label` on coherence rules only (validator refuses it elsewhere); `severity_of` reads the issue's label and records `set_by` | `contract/schema.py`, `decide/issues.py` | `tests/test_issues.py` (per-label level, coherence-only) |
| P2: `conflict` critical, `unexplained_tradeoff` major (owner ruling) | `examples/northbound/contract/principles.yaml` | `tests/test_capture.py` expected 2.4 issues |
| The review records which open issues made the policy row fire (`policy.fired_by`); `verify-report` re-derives it | `report/review.py`, `contract/schema.py`, `verify/report.py` | `tests/test_issues.py`; a tampered `fired_by` fails `verify-report` with the named difference |
| The manifest records `verifier.independence` (`one_family` today); the confidence basis says "a second model agrees", not "independent" | `report/manifest.py`, `verify/steps.py` | both reviews |
| Page: opens on the contract's hero persona (its most severe release issue), the decision bar names the issue(s) that fired the policy (clickable), the severity box says who set it, verification steps in words with the model that ran each, and a model line under the bar | `report/templates/release_story.html` | `tests/test_capture.py::test_page_opens_on_the_hero_even_when_another_personas_issue_is_more_severe` (red before the hero change: the page opened on Kai) |

**Regenerated from cache, $0.000 spent** (`semaudit review … --reuse`):

- **2.3 → 2.4** (`runs/e2e-2`): provisional; the policy would say **hold** (row 1), **fired by** `I-2.4-P2-fare-lock-price-watch-conflict` (Kai, critical, verified, medium). Maya's `I-2.4-P2-…-unexplained-tradeoff` is **major**, verified, medium.
- **2.4 → 2.4.1** (`runs/e2e-3`): provisional; the policy would say **needs owner review** (row 2), fired by Kai's conflict (critical, partially verified, low: the models disagree). Maya's tradeoff resolved.
- `semaudit verify-report`: both CONSISTENT.

Full suite: 235 passed.
