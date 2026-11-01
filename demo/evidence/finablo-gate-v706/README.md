# Finablo v706: the "354 automated checks passed" claim

**From Finablo's private repository; not publicly verifiable.** Finablo is the author's own app and its source is
not public. This file records where the number comes from so a reader knows exactly what it is, and what it is not.

## The record

Finablo's release record for v706 (its `PLAN.md`, the v706 as-shipped stamp, written 2026-09-30) says, verbatim:

> **Gate on `9aead58`** (== the merged tree): `✓ All checks passed. Safe to deploy.`, exit 0, **354 OK /
> 0 FAIL**, **133 labels all distinct**, **no `SKIPPED:` line (SKIP LEDGER 0)**, 6345 pytest, 768 parity,
> interpreter pins OK — re-counted from the saved log.

- **The gate's own summary line:** `✓ All checks passed. Safe to deploy.` (exit 0).
- **Commit it ran on:** `9aead58620e2caecff73ffdbc85d31005d2209bc` (2026-09-30), the head of the pull request that
  became v706.
- **How that relates to v706:** v706 deployed tree `10ff1e3eac9284e0b0d53dd520cef8de966c7905`, the merge commit of
  that pull request (parents `1611a23` and `9aead58`, 2026-09-30). Both commits have the **same tree**,
  `25e017e4db4e43177358b5d53da2913e8834654e`, and `git diff --stat 9aead58 10ff1e3` is empty. So the gate ran on
  exactly the code v706 deployed. Checked 2026-11-01 with `git rev-parse <commit>^{tree}` in the Finablo repo.
- **Date:** 2026-09-30 (the commit and the stamp).

## What "354" counts

**Gate checks, not tests.** The deploy gate (`scripts/pre-deploy-check.sh`) is a list of checks, and each one
prints `OK` when it passes. At `10ff1e3` the script has exactly 354 places that print a green `OK`
(`git show 10ff1e3:scripts/pre-deploy-check.sh | grep -c 'GREEN}OK'` → 354), grouped under 133 labelled blocks.
"354 OK / 0 FAIL" therefore means every check in the gate passed. Several of those checks each run a whole test
suite, and the same run reported **6345** pytest tests and **768** parity checks; those are separate counts.

## What this does not show

- The saved gate log itself is not in this repository; the counts above are the release record's, quoted.
- Passing the gate did not catch the 401(k) limit bug shown in beat 1 of the demo: that is the point of the beat.
