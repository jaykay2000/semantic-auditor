"""The Brightdesk evidence record adds up on its own, without the new-user test's folder.

The video frame and extractor that used to read this record are no longer in the repository (owner, 2026-11-02), so
this checks only what the folder itself claims: 15 billed calls summing to $0.132284, per-tag totals that cover every
ledger row, and a sha256 for each source file.
"""

import json
import re
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parents[1] / "demo" / "evidence" / "newuser-brightdesk-2026-11-01"
RECORD = json.loads((EVIDENCE / "record.json").read_text())
BILLED = [json.loads(line) for line in (EVIDENCE / "ledger-billed.jsonl").read_text().splitlines() if line.strip()]


def test_the_billed_rows_add_up_to_the_record():
    assert BILLED and all(r["cached"] is False for r in BILLED)
    assert len(BILLED) == RECORD["ledger"]["billed_calls"] == 15
    assert round(sum(r["cost_usd"] for r in BILLED), 6) == RECORD["ledger"]["billed_usd"] == 0.132284
    by_tag = RECORD["ledger"]["by_tag"]
    assert sum(t["billed_calls"] for t in by_tag.values()) == len(BILLED)
    assert sum(t["billed_calls"] + t["cached_calls"] for t in by_tag.values()) == RECORD["ledger"]["rows"]


def test_every_source_carries_a_sha256():
    assert RECORD["sources"]
    assert all(re.fullmatch(r"[0-9a-f]{64}", h) for h in RECORD["sources"].values())


def test_the_reviews_are_hold_then_ship():
    assert RECORD["reviews"]["hold"]["recommendation"] == "hold"
    assert RECORD["reviews"]["ship"]["recommendation"] == "ship"
