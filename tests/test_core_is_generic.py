"""The core names no app. Northbound's words live in its contract; a non-travel contract runs end to end.

Guard 1 scans src/semaudit for the demo app's vocabulary. Guard 2 loads a small contract with no trip at all
(a household budgeting app) and runs it through validation, story context, conditional rules and explanations.
"""

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.contract.schema import load_contract, resolve_context  # noqa: E402
from semaudit.contract.validate import validate  # noqa: E402
from semaudit.decide.issues import build_issues, condition_details  # noqa: E402
from semaudit.relate.rules import evaluate  # noqa: E402
from semaudit.relate.interpret import stub_always  # noqa: E402
from semaudit.story.model import Event, Extraction, Story  # noqa: E402

# Words of the demo app (domain, features, personas). Any of them in the core means a concept is missing from
# the contract schema. Extend this list when a new example app is added.
APP_WORDS = r"travell?ers?|trips?|depart\w*|flights?|hotels?|seats?|fares?|book(?:ing|ed|s)?|northbound|" \
            r"price[ _]watch|fare[ _]lock|concierge|maya|raj|kai|lena|omar|hana|rina|okafors?|EUR|€"
GENERIC = ROOT / "tests" / "fixtures" / "generic_contract"


def test_core_names_no_app():
    pat = re.compile(rf"\b(?:{APP_WORDS})\b", re.I)
    hits = []
    for p in sorted((ROOT / "src" / "semaudit").rglob("*")):
        if p.suffix in (".py", ".html", ".j2") and "__pycache__" not in p.parts:
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if pat.search(line):
                    hits.append(f"{p.relative_to(ROOT)}:{n}: {line.strip()[:100]}")
    assert not hits, "app vocabulary in the core:\n" + "\n".join(hits)


def test_guard_bites():
    """The pattern would catch the words that used to be in the core."""
    pat = re.compile(rf"\b(?:{APP_WORDS})\b", re.I)
    for line in ('dep = story.trip.get(cond.trip_field)', 'before the traveller decided',
                 'background:var(--${{price_watch: "pw"}})', 'Path("examples/northbound/contract")'):
        assert pat.search(line), line


C = load_contract(GENERIC)
D0 = datetime(2026, 11, 2, tzinfo=timezone.utc)


def msg(id, minutes, strength, explains=False):
    return Event(id=id, at=D0 + timedelta(hours=9, minutes=minutes), kind="message", feature="nudges",
                 surface="dashboard", channel="card", text=id,
                 extraction=Extraction(message_kind="directive", decision="tax_return", action="file_now",
                                       strength=strength, urgency_cue="deadline", explains_own_tradeoff=explains,
                                       claims=[]))


def household(pid):
    p = C.persona(pid)
    return Story(id=pid, release="1.1", persona=pid, context=resolve_context(p, C.subject, D0),
                 events=[msg("urgent", 0, "urge", explains=True)])


def test_generic_contract_validates_and_has_no_trip():
    assert validate(C) == []
    assert C.subject.noun == "member" and {f.id for f in C.subject.context} == {"tax_deadline", "household", "age"}
    assert "trip" not in C.personas[0].model_dump()


def test_context_drives_the_exception_and_its_explanation():
    near, far = household("ana"), household("ben")       # deadline in 2 days vs in 60 days
    assert near.context["tax_deadline"] == D0 + timedelta(days=2, hours=23, minutes=59)
    assert near.context["household"] == 1 and far.context["household"] == 3      # default vs set
    results = {s.persona: (s, evaluate(s, C, stub_always("compatible"))) for s in (near, far)}
    status = {p: [e.status for e in es if e.rule == "N1"] for p, (_, es) in results.items()}
    assert status == {"ana": ["excepted"], "ben": ["violated"]}
    (issue,) = [i for i in build_issues("1.1", results, C) if i.rule == "N1"]
    assert "member" in issue.why or "N1-E1" in issue.why
    s, es = results["ben"]
    e = next(x for x in es if x.rule == "N1")
    (a,) = [d for d in condition_details(C.rule("N1"), e, s.events[0], s) if d["id"] == "a"]
    assert a["value"] == "not_met" and a["text"].startswith("tax deadline ") and "> 72 h" in a["text"]
