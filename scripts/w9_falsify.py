"""W9 falsifiability: the verifier must REJECT planted bad issues, not just pass real ones.

1. A real issue whose quoted text was altered          -> evidence_linked fails, status failed.
2. A real issue whose re-capture lacks the event        -> reproduced fails, status failed (not_reproducible).
3. A fabricated P2 issue on Lena, whose tradeoff the concierge reconciled in time
                                                        -> the defender explains it away; confidence low.
4. A fabricated U4 issue on a plain confirmation        -> the defender explains it away; confidence low.
Run: python3 scripts/w9_falsify.py --run runs/w6 --max-usd 0.3
"""
import argparse
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.decide.issues import Issue, Occurrence, build_issues  # noqa: E402
from semaudit.decide.pipeline import evaluate_release  # noqa: E402
from semaudit.models.router import Router  # noqa: E402
from semaudit.relate.rules import Entry  # noqa: E402
from semaudit.verify.steps import verify  # noqa: E402


def fabricated(rule, rule_kind, persona, story, events, label=None, subject=None, meta=None):
    entry = Entry(rule, subject or events[0], "violated", label=label, meta=meta or {})
    return Issue(id=f"I-planted-{rule}-{persona}", signature=("planted",), rule=rule, rule_kind=rule_kind,
                 layer="release", label=label, occurrences=[Occurrence(persona, story.id, events, entry,
                                                                        "before_decision")],
                 severity={"level": "major", "factors": {}}, why="planted for the falsifiability check")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--max-usd", type=float, required=True)
    a = ap.parse_args()
    c = load_contract(ROOT / "examples" / "northbound" / "contract")
    router = Router(root=ROOT, max_usd=a.max_usd)
    h = evaluate_release(a.run, "2.4", c, router)
    stories = {p: s for p, (s, _) in h.results.items()}
    issues = {i.rule: i for i in build_issues("2.4", h.results, c)}
    ok = True

    # 1. altered quote
    hero = copy.deepcopy(next(i for i in build_issues("2.4", h.results, c) if i.rule == "P2" and i.label == "unexplained_tradeoff"))
    tampered = {p: s.model_copy(deep=True) for p, s in stories.items()}
    for e in tampered["maya"].events:
        if e.copy_key == "fl.banner":
            e.text = e.text.replace("48 h", "72 h")
    verify(hero, tampered, h.episodes, a.run, c, router, repro=tampered, models=False)
    r1 = hero.verification
    print("1 altered quote ->", r1["status"], r1["reason"]); ok &= r1["status"] == "failed"

    # 2. not reproduced
    hero2 = copy.deepcopy(hero)
    gone = {p: s.model_copy(deep=True) for p, s in stories.items()}
    gone["maya"].events = [e for e in gone["maya"].events if e.copy_key != "fl.banner"]
    verify(hero2, stories, h.episodes, a.run, c, router, repro=gone, models=False)
    r2 = hero2.verification
    print("2 not reproduced ->", r2["status"], r2["reason"]); ok &= r2["reason"] == "not_reproducible"

    # 3. fabricated P2 on Lena (reconciled in time)
    lena = stories["lena"]
    pw = next(e.id for e in lena.messages() if e.copy_key == "pw.card")
    fl = next(e.id for e in lena.messages() if e.copy_key == "fl.banner")
    subj = "fare_lock|price_watch@when_to_book:tradeoff"
    f3 = fabricated("P2", "coherence", "lena", lena, [pw, fl], label="unexplained_tradeoff", subject=subj,
                    meta={"pairs": [[pw, fl]], "decision": "when_to_book", "pair_kind": "tradeoff",
                          "material": c.decision("when_to_book").tradeoffs[0].material})
    f3.why = ("wait_for_drop and lock_fare are compatible with a material tradeoff; nothing explained it "
              "before the traveller decided.")
    verify(f3, stories, h.episodes, a.run, c, router, repro=stories, fresh=True)
    print("3 planted P2 on Lena ->", f3.verification["status"], f3.verification["reason"], "| confidence",
          f3.confidence["level"], "|", f3.verification["steps"]["defended"]["detail"][:160])
    ok &= f3.confidence["level"] == "low"

    # 4. fabricated U4 on a booking confirmation
    maya = stories["maya"]
    conf = next(e.id for e in maya.messages() if e.copy_key == "core.confirmed")
    f4 = fabricated("U4", "universal", "maya", maya, [conf])
    f4.why = "a retrospective message after the traveller had committed."
    verify(f4, stories, h.episodes, a.run, c, router, repro=stories, fresh=True)
    print("4 planted U4 on a confirmation ->", f4.verification["status"], "| confidence", f4.confidence["level"],
          "|", f4.verification["steps"]["defended"]["detail"][:160])
    ok &= f4.confidence["level"] == "low"
    print(f"spent ${router.spent_usd:.3f}")
    print("VERIFIER BITES" if ok else "VERIFIER DOES NOT BITE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
