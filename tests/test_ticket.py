"""Ticket drafts are read from the review alone."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pytest  # noqa: E402
from semaudit.report.ticket import ticket  # noqa: E402

REVIEW = ROOT / "runs" / "e2e-2" / "review-2.3-2.4.json"


@pytest.mark.skipif(not REVIEW.exists(), reason="needs the e2e-2 review")
def test_a_ticket_quotes_every_cited_message_and_the_steps():
    r = json.loads(REVIEW.read_text())
    i = r["issues"][0]
    md = ticket(r, i["id"])
    p = next(x for x in r["personas"] if x["id"] == i["occurrences"][0]["persona"])
    cited = [e for e in p["events"] if e["id"] in i["occurrences"][0]["events"] and e["kind"] == "message"]
    assert cited and all(e["text"].strip().splitlines()[0][:40] in md for e in cited)
    assert i["why"] in md and i["repro"] in md and "## Steps to reproduce" in md
    assert "1. " in md and "a person decides whether to file it" in md


def test_an_unknown_issue_is_refused():
    with pytest.raises(KeyError):
        ticket({"issues": [], "resolved": []}, "I-x")


def test_a_long_message_is_quoted_at_the_lines_that_state_the_figure():
    from semaudit.report.ticket import _quote
    text = "\n".join(["intro line"] * 40 + ["Step 3: toward the IRS max ($24,500/yr for 401(k))"] + ["tail"] * 40)
    q = _quote(text, "claim 24500 vs true limit_401k 32500")
    assert "$24,500/yr" in q and q.count("intro line") == 1 and "…" in q
