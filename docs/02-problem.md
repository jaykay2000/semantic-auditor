# 2. Problem statement

## The issue class

A **semantic release issue** is product behaviour that is acceptable feature by feature, but, as one user experiences the release over time, conflicts with itself or with what the owner intends. The kinds:

| Kind | Shape | Northbound example |
|---|---|---|
| **Unexplained tradeoff** (coherence) | two features recommend *compatible* actions on the same decision, with a material tradeoff between them that nothing explains. Each message can be entirely true | Price Watch: "likely to drop, we suggest waiting" · Fare Lock: "2 seats left at this fare. Lock it for 48 h for €9". Lock and wait can coexist, but the €9 lock expires long before the 14-day drop window, and nobody says so |
| **Conflicting directives** (coherence) | two features recommend *incompatible* actions on the same decision while both are live, unreconciled | Price Watch: "wait" · Fare Lock (urgent variant): "Book now" |
| **Stale guidance** | advice whose precondition is no longer true for this user | after booking: "Keep waiting to book. We'll tell you when prices drop." |
| **Rule breach for this persona** | behaviour a conditional rule forbids, with no exception's conditions all met | urging immediate booking on a trip six months away |
| **Attention load** | more demands on the user than the owner's rule allows | four non-booking messages in 24 hours |
| **Fact divergence** | the same fact with different values on different surfaces | the lock is shown at €9, and a couple buying it is charged €18 |
| **False claim** | a claim contradicted by the product's own data (a claim with no data to check is *unverifiable*, not false) | "only 2 seats left" when inventory shows 9 |

The first four are **release-level**: no single feature is wrong in isolation, and they are why the auditor exists. The last two are conventional factual defects, kept because they are the most objective evidence an experience contains. The demo presents them as such and never as the hero.

## Why they escape QA

1. **Each feature passes on its own.** Its tests, evals and reviews look at it in isolation.
2. **They depend on order and state.** "Wait" and "lock now" conflict only when both are live; "book refundable" is only wrong *after* a non-refundable booking.
3. **They depend on the persona.** The same urgent banner is fine for a traveller departing tomorrow and a breach for one departing in six months.
4. **They depend on intent.** Whether something is a conflict or a legitimate tradeoff is the owner's call, and rarely written down operationally.
5. **No one sees the whole story.** Emails, pushes and PDFs live outside the app, and AI copy differs per user at runtime.

## Evidence from a real product (Finablo)

Finablo, a personal-finance web app, has shipped both kinds:
- **Objective:** on the pending report page, a 61-year-old was shown $24,500 as their 401(k) maximum while the server and the export said $35,750.
- **Experience-level:** surfaces that each rendered correctly but together gave a user incompatible framing or duplicated the same directive. Finablo found these by hand, after they shipped.

Finablo also built a deterministic, hand-coded cross-surface harness (10 facts, 22 surfaces). Replayed blind against 5 real past releases, it caught 2. Hand-written coverage finds only what someone anticipated, and it cannot represent directives, time or intent at all.

## Why now

- AI-written, per-user copy means the number of distinct experiences grows faster than anyone can review.
- Frontier multimodal models (Muse Spark: image and PDF input, structured output, tool calling, long context) can now read what a surface tells the user at low cost. What is missing is the system that makes that reading **complete, ordered, grounded in the owner's rules, reproducible and consistent across releases**.

## What we are solving for the hackathon

> For a web application and a new release: reconstruct each important persona's time-ordered experience across features and surfaces; identify conflicting product behaviour and messages against the owner's operational principles; distinguish real conflicts from legitimate tradeoffs and approved exceptions; and give the owner reproducible evidence and a Ship / Hold recommendation. Then measure, against the same model given the same context, where this adds coverage, precision, reproducibility and repeatability.

## Out of scope

- Functional correctness, visual regression and performance (existing tools).
- Taste beyond the owner's stated principles. Human design review remains the owner of taste.
- Deciding what is correct when the owner has not said so. The auditor asks.
