"""A message whose action the contract lists under several decisions bears on every one of them (relate/rules.py
decisions_of). On the sealed W13b releases, 6 of the auditor's 7 misses were this: one action listed under two
decisions, the model filed the message under the other one, and the rule about the first was never evaluated.
That was rebuilt here from the counts-only report's description only, on the public dev stories (no model)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.relate.interpret import stub_always  # noqa: E402
from semaudit.relate.rules import decisions_of, evaluate, p2_candidates  # noqa: E402
from semaudit.story.model import Extraction, Story  # noqa: E402

FIX = ROOT / "tests/fixtures/stories"
GOLD = json.loads((FIX / "copy_gold.json").read_text())
NB = load_contract(ROOT / "examples/northbound/contract")
# The same contract, except that book_now is ALSO a fare_type action (two decisions now share one action).
SHARED = NB.model_copy(update={"decisions": [d.model_copy(update={"actions": [*d.actions, "book_now"]})
                                             if d.id == "fare_type" else d for d in NB.decisions]})


def story(name, *, file_under=None):
    """The dev story with gold extractions. file_under: re-file every book_now message under that decision, as
    the model did on the sealed releases (its action stays book_now)."""
    s = Story(**json.loads((FIX / f"{name}.json").read_text())["story"])
    for e in s.messages():
        g = dict(GOLD[e.copy_key])
        if file_under and g["action"] == "book_now":
            g["decision"] = file_under
        e.extraction = Extraction(**g)
    return s


def entries(s, contract, rule):
    return sorted((x.subject, x.status, x.conditions) for x in evaluate(s, contract, stub_always("incompatible"))
                  if x.rule == rule)


def test_decisions_of_reads_the_contract_vocabulary():
    x = Extraction(message_kind="directive", decision="fare_type", action="book_now", strength="urge",
                   urgency_cue="none", explains_own_tradeoff=False)
    assert decisions_of(x, SHARED) == ["fare_type", "when_to_book"]
    assert decisions_of(x.model_copy(update={"decision": "when_to_book"}), NB) == ["when_to_book"]
    assert decisions_of(x.model_copy(update={"action": "none", "decision": "none"}), NB) == []


def test_a_conditional_rule_still_applies_when_the_message_is_filed_under_the_other_decision():
    want = entries(story("raj_x"), SHARED, "P1")
    assert want and want[0][1] == "violated"                       # the dev truth: P1 violated on fl_bare
    assert entries(story("raj_x", file_under="fare_type"), SHARED, "P1") == want


def test_a_coherence_pair_is_still_found_when_one_side_is_filed_under_the_other_decision():
    """Kai: book-now vs wait on when_to_book (the dev truth's P2 conflict)."""
    want = sorted(c.subject for c in p2_candidates(story("kai"), SHARED))
    assert any(s.endswith("@when_to_book:incompatible") for s in want), want
    got = sorted(c.subject for c in p2_candidates(story("kai", file_under="fare_type"), SHARED))
    assert set(want) <= set(got), (want, got)


def test_the_unshared_contract_behaves_exactly_as_before():
    for name in ("raj_x", "maya", "kai", "sam_alex"):
        s = story(name)
        assert all(decisions_of(e.extraction, NB) == ([e.extraction.decision] if e.extraction.decision != "none"
                                                       else []) for e in s.messages()), name
