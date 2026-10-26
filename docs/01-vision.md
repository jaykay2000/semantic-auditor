# 1. Vision

## One sentence

**Every release should tell every user one true story**, and a machine should be able to check that before the user does.

## The shift

Products no longer show one screen built from one database query. A single user sees the same facts through a dashboard, a PDF, a lifecycle email, a push notification, an exported summary and an AI assistant that writes its own sentences. Each surface is built by a different person, at a different time, often in a different language, and increasingly by a model. Functional tests check that each surface *works*. Nothing checks that they *agree*, that they are *true*, or that they still make sense for *this* user.

The Semantic Release Auditor is a QA layer for meaning. It does not replace unit tests, end-to-end tests or human UX review. It sits on top of them and answers the questions none of them ask:

1. **Consistent:** does every surface give this user the same answer to the same question?
2. **True:** does every claim match the product's own source of truth?
3. **Supported:** is every claim, especially AI-written text, backed by something the product actually knows?
4. **Fit:** does what this user sees make sense for who they are?
5. **Intended:** of everything that changed in meaning this release, what did the team mean to change?

## What it is

A standalone, open-source tool with two phases:

- **Onboard (learn the product).** It reads docs, explores the running app, and interviews the product owner (spoken or written). From these it drafts a **Product Contract**: the surfaces, the facts each one asserts, where the truth for each fact lives, which personas matter, and the rules that must always hold. The owner reviews and approves it. The contract is versioned YAML that lives in the customer's repo, like a schema.
- **Audit (check a release).** Given a base build and a head build, it generates personas aimed at the edges of the contract, drives them through every surface of both builds, and extracts every claim into a graph. It runs the checkers, verifies each finding independently, and separates intended changes from unexplained ones using the release notes. It emits evidence packets, and each confirmed finding becomes a deterministic regression check.

## What makes it more than "ask a frontier model to do QA"

A strong model with a million-token context can look at a pile of screenshots and spot some contradictions. That is our baseline, and we will measure against it. The auditor's advantage comes from the system around the model, not from a better prompt:

| A one-shot prompt... | The auditor... |
|---|---|
| sees only what you paste in | **generates its own coverage**: personas aimed at the contract's edge axes × every surface × both builds |
| forgets the product between releases | keeps a **Product Contract**: intent, oracles and accepted exceptions, versioned with the code |
| judges plausibility | checks claims against the product's **own source of truth** (API, database, rule) |
| reports everything that looks odd | **verifies before reporting**: fresh re-capture, a second extraction by a different model, deterministic recomputation, and an adversarial "explain it away" pass |
| cannot tell a regression from a planned change | **diffs meaning between builds** and matches each change against release intent |
| costs the same every release | runs a **ratchet**: every confirmed finding becomes a cheap deterministic check, so model spend goes to what is new |
| gives no measure of trust | publishes **recall and precision** on a seeded benchmark, against the one-prompt baseline, with ablations |

## Who it is for

- **First customer: Finablo**, a personal-finance web app whose report, dashboard, PDF, email and AI assistant all state the same numbers about a user's money. It has paid for cross-surface bugs repeatedly, and its own hand-built harness caught 2 of 5 real past release bugs blind.
- **Then: any team shipping a multi-surface or AI-written product**: fintech, travel, insurance, SaaS billing, marketplaces, and anything with an LLM writing user-facing copy.
- **Later: native mobile**, where there is no DOM and screens are read by vision and segmentation (iOS is the stretch case).

## Product principles

1. **Precision over volume.** A finding nobody trusts is noise. Nothing is reported unverified, and rejected candidates are shown with the reason they were rejected.
2. **Evidence, not opinions.** Every finding carries the persona, both surfaces, screenshots, the normalized claims, the oracle value and a reproduction.
3. **The contract is the owner's.** The auditor proposes; a human approves. It never silently changes what "correct" means.
4. **Deterministic where possible, model where necessary.** Models extract and judge; arithmetic, joins and diffs are code.
5. **Gets cheaper with use.** The ratchet moves knowledge from model calls into checks.
6. **App-agnostic core, thin adapters.** Web, email, PDF, API and chat ship first; iOS later. A consumer integrates by writing a contract, never by forking the tool.

## North-star metric

**Unexplained semantic regressions reaching users per release**, driven toward zero at a stated precision. For the hackathon: **recall and precision on the seeded benchmark versus the one-prompt baseline**, plus at least one real bug found on a real product.
