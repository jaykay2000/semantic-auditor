"""Per-message readings: a message read once is not read again because the batch around it moved.

Before, every distinct message was sorted and read in batches of 25, so adding one persona shifted every batch and
re-read every message. These tests use the real router (its cache files and request digests) with the network call
replaced, and count what is actually sent."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.extract import messages as M  # noqa: E402
from semaudit.models.router import ModelError, Router  # noqa: E402

C = load_contract(ROOT / "examples/northbound/contract")


def _msgs(names):
    return [{"feature": "core", "channel": "page", "text": f"message {n}"} for n in names]


def _router(tmp_path, *, index=True, offline=False, sent=None):
    r = Router(root=tmp_path, offline=offline)
    r.reading_index = index
    calls = sent if sent is not None else []

    def fetch(role, provider, model, body, digest, timeout_s):
        if r.offline:
            raise ModelError(f"offline: no cached answer for {role} ({digest[:12]})")
        content = body["messages"][1]["content"]
        listing = json.loads(content[content.index("\n[") + 1:])
        calls.append([x["text"] for x in listing])
        odd = len(calls) % 2 == 1               # readings from different calls differ, so a test can tell them apart
        rows = [{"id": x["id"], "message_kind": "information", "decision": "none", "action": "none",
                 "strength": "inform", "urgency_cue": "none", "explains_own_tradeoff": odd, "claims": []}
                for x in listing]
        return {"choices": [{"message": {"content": json.dumps({"messages": rows})}}], "usage": {}}, 0.0
    r._fetch = fetch
    return r, calls


def test_adding_messages_reads_only_the_new_ones(tmp_path):
    first = _msgs(range(0, 60, 2))                         # 30 messages
    r, sent = _router(tmp_path)
    M.extract_unique(first, C, r)
    assert [len(c) for c in sent] == [25, 5]
    more = _msgs(range(1, 20, 2))                          # 10 new ones that sort in between the old ones
    r2, sent2 = _router(tmp_path)
    out = M.extract_unique(first + more, C, r2)
    assert len(out) == 40
    assert sent2 == [[m["text"] for m in sorted(more, key=lambda m: m["text"])]]   # one call, only the new ten


def test_without_the_index_every_batch_that_moved_is_read_again(tmp_path):
    """The defect the index removes: the same two runs, plain batching."""
    first, more = _msgs(range(0, 60, 2)), _msgs(range(1, 20, 2))
    M.extract_unique(first, C, _router(tmp_path, index=False)[0])
    r2, sent2 = _router(tmp_path, index=False)
    M.extract_unique(first + more, C, r2)
    assert sum(len(c) for c in sent2) == 40


def test_a_run_recorded_before_the_index_is_reused_with_no_call_and_indexed(tmp_path):
    msgs = _msgs(range(30))
    M.extract_unique(msgs, C, _router(tmp_path, index=False)[0])          # recorded by plain batching only
    assert not (tmp_path / ".semaudit-cache" / "readings").exists()
    r, sent = _router(tmp_path)
    M.extract_unique(msgs, C, r)
    assert sent == [] and len(list((tmp_path / ".semaudit-cache" / "readings").iterdir())) == 30
    r3, sent3 = _router(tmp_path)
    M.extract_unique(msgs + _msgs(["new"]), C, r3)                         # every batch moved; only "new" is read
    assert sent3 == [["message new"]]


def test_a_replay_uses_exactly_the_readings_its_review_pinned(tmp_path):
    first, more = _msgs(range(0, 60, 2)), _msgs(range(1, 20, 2))
    M.extract_unique(first, C, _router(tmp_path)[0])
    r, _ = _router(tmp_path)                                  # the review: 30 readings reused, 10 read now
    before = M.extract_unique(first + more, C, r)
    pinned = dict(r.used_readings)
    assert len(pinned) == 40 and len({e["reply"] for e in pinned.values()}) == 3
    # the index now says something else for every message (as if a later run had read them again): each entry points
    # at a row of a reply whose reading differs
    idx = tmp_path / ".semaudit-cache" / "readings"
    flip = {}
    for e in pinned.values():
        mine = json.loads(json.loads((tmp_path / ".semaudit-cache" / f"{e['reply']}.json").read_text())
                          ["choices"][0]["message"]["content"])["messages"][0]["explains_own_tradeoff"]
        flip.setdefault(mine, e["reply"])
    for k in pinned:
        mine = before[next(key for key in before if M.reading_key(r, "extractor", C.rubric, M._prompt(C, set()),
                                                                    M.extraction_schema(C, set()), key) == k)]
        (idx / f"{k}.json").write_text(json.dumps({"reply": flip[not mine.explains_own_tradeoff], "id": "m0"}))
    unpinned = Router(root=tmp_path, offline=True)
    unpinned.reading_index = True
    assert M.extract_unique(first + more, C, unpinned) != before         # the index alone would answer differently
    replay = Router(root=tmp_path, offline=True)
    replay.pinned_readings = pinned
    assert M.extract_unique(first + more, C, replay) == before


def test_a_pinned_reading_whose_reply_is_gone_is_a_missing_input_not_a_new_paid_read(tmp_path):
    msgs = _msgs(range(3))
    r, _ = _router(tmp_path)
    M.extract_unique(msgs, C, r)
    for f in (tmp_path / ".semaudit-cache").glob("*.json"):
        f.unlink()
    replay, sent = _router(tmp_path, index=False)               # a live replay (compare-prompts runs live)
    replay.pinned_readings = dict(r.used_readings)
    with pytest.raises(ModelError, match="offline: no cached answer"):
        M.extract_unique(msgs, C, replay)
    assert sent == []


def test_recorded_plain_batches_are_used_even_when_the_index_knows_some_of_their_messages(tmp_path):
    """The base release indexes the messages it shares with head; head's plain batches, already recorded, must
    still be used as they are, not re-cut around the indexed messages and read again."""
    msgs = _msgs(range(30))
    plain, _ = _router(tmp_path, index=False)
    M.extract_unique(msgs, C, plain)
    idx = tmp_path / ".semaudit-cache" / "readings"
    idx.mkdir()
    for k, e in list(plain.used_readings.items())[:10]:
        (idx / f"{k}.json").write_text(json.dumps(e))
    r, sent = _router(tmp_path)
    M.extract_unique(msgs, C, r)
    assert sent == []


def test_an_offline_replay_adds_to_the_index_only_when_asked(tmp_path):
    msgs = _msgs(range(5))
    M.extract_unique(msgs, C, _router(tmp_path, index=False)[0])
    replay = Router(root=tmp_path, offline=True)
    replay.reading_index = True
    M.extract_unique(msgs, C, replay)
    assert not (tmp_path / ".semaudit-cache" / "readings").exists()      # a committed sample's cache stays as is
    replay.index_offline = True
    M.extract_unique(msgs, C, replay)
    assert len(list((tmp_path / ".semaudit-cache" / "readings").iterdir())) == 5


def test_the_manifest_pins_the_readings_a_review_used(tmp_path):
    from semaudit.report import manifest as mf
    r, _ = _router(tmp_path)
    M.extract_unique(_msgs(range(3)), C, r)
    m = mf.build(ROOT / "examples/northbound/contract", C, tmp_path, "a", "b", router=r, models=False,
                 max_usd=1.0, repro_run=None)
    assert m["readings"] == dict(sorted(r.used_readings.items())) and len(m["readings"]) == 3
    assert "readings" not in mf.build(ROOT / "examples/northbound/contract", C, tmp_path, "a", "b",
                                      router=Router(root=tmp_path), models=False, max_usd=1.0, repro_run=None)
