"""Imported checks: an exploratory agent's finding turned into a reusable, replayable release check.

    convert.py   the agent's own reproduction text -> a persona and steps that use only the app adapter's verbs
                 (a model drafts it; a deterministic gate refuses anything the adapter, the store data or the text
                 does not support), classified fail-closed.
    recheck.py   replay a converted check on a release, judge its invariant over the captured surface and the
                 store's own record, and report four separate statuses.
    record.py    the check record: actions, the invariant tied to an owner rule, and the original quote kept only
                 as evidence of the original finding.
"""
