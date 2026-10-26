# 1. Vision

## Thesis

> **The Semantic Release Auditor reconstructs what a particular user experiences across a release, identifies conflicting product behavior and messages, and gives the owner reproducible evidence to make a shipping decision.**

## The shift

Users do not experience features. They experience a **release**: everything the product says to them, in order, across screens, emails, pushes, PDFs and AI answers, while their own situation changes (they search, they book, time passes).

Each feature in a release is built, tested and reviewed on its own. So a release can pass every feature's QA and still tell one user to wait and to hurry on the same afternoon. It can second-guess a purchase they can no longer change, or apply urgency to exactly the people the product promised not to pressure. These are **semantic release issues**: product behaviour that only becomes wrong when you see the whole experience of one person, judged against what the owner intended.

They are not always bugs. Two messages that look contradictory can be a legitimate tradeoff, or a deliberate, persona-specific exception. So the output is not a pass/fail gate. It is a **release review**: ranked issues with reproducible evidence, and a Ship / Hold recommendation that the owner decides on.

## What it does

1. **Learns the owner's intent.** It turns "we never pressure travellers" into an operational rule with testable conditions and scoped exceptions, and the owner approves it.
2. **Reconstructs each user's experience.** It drives personas through time-ordered scenarios on both releases, and records every message, its feature, the user's actions and the user's state.
3. **Finds conflicts in that story.** Code proposes candidate conflicts (competing advice on the same decision, guidance that went stale after the user acted, rule conditions, message load, facts that disagree), and a model interprets each one against the owner's rules and exceptions.
4. **Separates conflicts from legitimate differences:** an approved exception, an explained tradeoff, messages never live at the same time, a persona's own facts.
5. **Proves it.** Every issue can be replayed with one command. It cites exact captured moments and is cross-checked by a second model, with severity, confidence and verification status shown separately.
6. **Remembers decisions, narrowly.** A *fix* must come back resolved. An *accept* becomes a scoped, expiring exception, and never a blanket suppression.

## Where it sits

Tests check that features work. LLM evals check single AI answers. Visual tools check pixels. Agentic QA platforms increasingly explore apps autonomously and keep a product knowledge base. The Semantic Release Auditor focuses on one distinct objective: **release-level, persona-specific semantic coherence, judged against owner-approved intent, with reproducible evidence.** It is designed to sit alongside those tools, not to replace them.

## Why a system and not a prompt

A strong model with a browser, the docs and the owner's rules can find many of these issues once. The auditor's value is that it finds them **completely, reproducibly and consistently**:

| | One-off agentic review | The auditor |
|---|---|---|
| Coverage | the paths the agent happened to take | every persona × scenario × release, including time-triggered and post-purchase moments |
| Evidence | a narrative, sometimes citing things that are not there | exact captured moments, locators, state and a replay command for every issue |
| False alarms | judged case by case | an exception and tradeoff checklist applied before anything is raised; negative controls measured |
| Repeatability | different answers on different runs | stable issue sets; changes attributed to features; owner decisions respected next release |
| Cost | the same every time | the cache, the deterministic pass and candidate-only interpretation keep model spend proportional to change |

We measure each row against a fair baseline: the same model and the same context ([08-evaluation.md](08-evaluation.md)).

## Who it is for

- **First real consumer: Finablo**, a personal-finance web app whose report, dashboard, PDF, export and AI assistant all speak to the same user about the same money. It has shipped both kinds of issue: numbers that disagreed across surfaces, and surfaces that were each correct but together told the user incompatible things.
- **Then:** any multi-surface or AI-written product (travel, fintech, insurance, SaaS billing, marketplaces).
- **Later:** native mobile, through a vision and accessibility-tree adapter.

## Principles

1. **The user's story is the unit.** Not a screen, not a feature, not a single claim.
2. **The owner's rules, operationalized.** Judgement is against approved principles with conditions and exceptions, not the model's taste.
3. **Separate what is bad from what is certain.** Severity, confidence and verification are never combined into one label.
4. **Evidence or it is not raised.** Every issue replays; every quote is the captured text.
5. **Code narrows, models interpret.** Time, state, joins, conditions and policy are code; meaning is the model's.
6. **Decisions are scoped.** An exception never silently grows.
7. **App-agnostic core.** Everything app-specific lives in the consumer's contract.

## North-star metric

**Unreviewed semantic conflicts reaching users per release.** For the hackathon: coverage, precision and recall, the false-alarm rate on negative controls, and run-to-run stability against a fair baseline on a frozen benchmark, plus one real-product finding.
