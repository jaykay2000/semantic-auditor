"""An extraction batch whose reply is unreadable (runaway or over-long) is split and retried in halves."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pytest  # noqa: E402

from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.extract import messages as M  # noqa: E402
from semaudit.models.router import UnreadableReply  # noqa: E402

C = load_contract(ROOT / "examples/northbound/contract")
ROW = {"message_kind": "information", "decision": "none", "action": "none", "strength": "inform",
       "urgency_cue": "", "explains_own_tradeoff": False, "claims": []}


class FakeRouter:
    """Unreadable for any call listing more than `limit` messages."""
    def __init__(self, limit):
        self.limit, self.sizes = limit, []

    def complete(self, role, msgs, **kw):
        listing = json.loads(msgs[1]["content"][msgs[1]["content"].index("["):])
        self.sizes.append(len(listing))
        if len(listing) > self.limit:
            raise UnreadableReply("not JSON")

        class R:
            parsed = {"messages": [{"id": x["id"], **ROW} for x in listing]}
        return R()


def _msgs(n):
    return [{"feature": "core", "channel": "page", "text": f"message {i}"} for i in range(n)]


def test_unreadable_batch_is_split_until_it_reads(monkeypatch):
    monkeypatch.setattr(M, "_prompt", lambda contract, observed: "")
    r = FakeRouter(limit=3)
    out = M.extract_unique(_msgs(10), C, r, batch=10)
    assert len(out) == 10
    assert r.sizes == [10, 5, 2, 3, 5, 2, 3]          # each unreadable call is halved; every message read once
    assert sum(s for s in r.sizes if s <= 3) == 10


def test_a_single_unreadable_message_still_fails(monkeypatch):
    monkeypatch.setattr(M, "_prompt", lambda contract, observed: "")
    with pytest.raises(UnreadableReply):
        M.extract_unique(_msgs(2), C, FakeRouter(limit=0), batch=2)


def test_not_raised_works_for_a_contract_without_a_coherence_rule():
    from types import SimpleNamespace

    from semaudit.report.review import not_raised

    class C:
        def rules_of(self, kind):
            return []
    e = SimpleNamespace(status="passed", rule="U1", label=None, meta={}, subject="x", conditions=[], id="e1")
    head = SimpleNamespace(results={"ana": (SimpleNamespace(events=[]), [e])})
    assert not_raised(head, [], C()) == []
