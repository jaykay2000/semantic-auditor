"""W3b: the full contract loads, validates, evaluates its policy, derives state and tracks approval."""

import shutil
import sys
from datetime import datetime, timedelta, timezone
from itertools import product
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.contract.approve import approve, items, load_approvals, status_of  # noqa: E402
from semaudit.contract.review import render  # noqa: E402
from semaudit.contract.schema import (CONFIDENCE, SEVERITY, VERIFICATION, ReleasePolicy,  # noqa: E402
                                      load_contract, resolve_time)
from semaudit.contract.validate import policy_coverage, validate  # noqa: E402
from semaudit.story.model import Event, Story  # noqa: E402

NB = ROOT / "examples" / "northbound" / "contract"
C = load_contract(NB)
D0 = datetime(2026, 11, 2, tzinfo=timezone.utc)


@pytest.fixture
def copy(tmp_path):
    d = tmp_path / "contract"
    shutil.copytree(NB, d)
    (d / "approvals.yaml").unlink(missing_ok=True)
    return d


def edit(d: Path, name: str, fn):
    data = yaml.safe_load((d / name).read_text())
    fn(data)
    (d / name).write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


# ---------- the Northbound contract ----------

def test_northbound_contract_is_complete_and_valid():
    assert validate(C) == []
    assert {p.id for p in C.personas} >= {"maya", "maya_r", "lena", "raj", "raj_x", "raj_72h", "raj_72h_30s",
                                          "raj_72h_1m", "kai", "hana", "omar", "sam_alex", "theo", "rina"}
    assert all(C.scenario_for(p.id) for p in C.personas)
    assert C.app and C.app.fictional and C.policy


def test_boundary_departures_are_exact():
    banner = resolve_time("D0 10:03", D0)
    gap = {p: resolve_time(C.persona(p).context["departure_at"], D0) - banner for p in ("raj_72h", "raj_72h_30s", "raj_72h_1m")}
    assert gap == {"raj_72h": timedelta(hours=72), "raj_72h_30s": timedelta(hours=72, seconds=30),
                   "raj_72h_1m": timedelta(hours=72, minutes=1)}


# ---------- validation bites ----------

@pytest.mark.parametrize("name,mutate,expect", [
    ("principles.yaml", lambda r: r[4]["exceptions"][0]["scope"].update(features=["fare_lok"]), "unknown feature 'fare_lok'"),
    ("principles.yaml", lambda r: r[4]["exceptions"][0]["approved"].pop("expires"), "no expiry"),
    ("principles.yaml", lambda r: r[4]["exceptions"][0]["conditions"][0].update(test="close_enough"), "unknown data test"),
    ("decisions.yaml", lambda d: d[0]["preconditions"]["*"].update(bookng_status="x"), "unknown state variable 'bookng_status'"),
    ("decisions.yaml", lambda d: d[0].update(decided_by=["teleport"]), "unknown action 'teleport'"),
    ("scenarios.yaml", lambda s: s[0]["personas"].append("ghost"), "unknown persona 'ghost'"),
    ("scenarios.yaml", lambda s: s[0]["steps"].reverse(), "not in time order"),
    ("personas.yaml", lambda p: p.append({**p[0], "id": "orphan"}), "persona orphan: in no scenario"),
    ("facts.yaml", lambda f: f[0]["sources"][0].update(oracle="crystal_ball"), "unknown oracle 'crystal_ball'"),
])
def test_validation_catches(copy, name, mutate, expect):
    edit(copy, name, mutate)
    problems = validate(load_contract(copy))
    assert any(expect in p for p in problems), problems


# ---------- release policy ----------

def issue(s, c, v):
    return {"severity": s, "confidence": c, "verification": v}


@pytest.mark.parametrize("issues,expected", [
    ([], "ship"),
    ([issue("critical", "high", "verified")], "hold"),
    ([issue("critical", "medium", "verified")], "hold"),
    ([issue("critical", "low", "verified")], "needs_owner_review"),
    ([issue("critical", "high", "partially_verified")], "needs_owner_review"),
    ([issue("major", "high", "partially_verified")], "needs_owner_review"),
    ([issue("major", "high", "verified"), issue("minor", "low", "verified")], "ship_with_notes"),
    ([issue("minor", "low", "verified"), issue("critical", "high", "verified")], "hold"),
])
def test_policy_recommendations(issues, expected):
    assert C.policy.evaluate(issues)[0].recommendation == expected


def test_policy_is_exhaustive_and_every_row_reachable():
    exhaustive, fired = policy_coverage(C.policy)
    assert exhaustive and fired == set(range(len(C.policy.rows)))


def test_policy_without_catch_all_is_reported_not_exhaustive():
    rows = [r.model_dump() for r in C.policy.rows if not r.otherwise]
    exhaustive, _ = policy_coverage(ReleasePolicy(rows=rows))
    assert not exhaustive


def test_every_single_issue_lands_in_exactly_one_recommendation():
    for s, c, v in product(SEVERITY, CONFIDENCE, VERIFICATION):
        row, _ = C.policy.evaluate([issue(s, c, v)])
        assert row.recommendation != "ship"


# ---------- derived state comes from the contract ----------

def story_booked_at(t):
    return Story(id="s", release="2.4", persona="p", context={"departure_at": D0},
                 events=[Event(id="b", at=t, kind="user_action", action="book")])


def test_state_model_drives_booking_and_change_window():
    booked = D0 + timedelta(hours=10, minutes=6)
    s = story_booked_at(booked)
    assert s.state_at(booked, C.state)["booking_status"] == "not_booked"        # strictly before
    after = s.state_at(booked + timedelta(seconds=1), C.state)
    assert after["booking_status"] == "booked" and after["within_change_window"]
    assert s.state_at(booked + timedelta(hours=24), C.state)["within_change_window"]
    assert not s.state_at(booked + timedelta(hours=24, seconds=1), C.state)["within_change_window"]


# ---------- approval is of exact content ----------

def test_approval_is_pinned_to_content(copy):
    c = load_contract(copy)
    approve(copy, c, ["rule:P2", "exception:P1-E1"], by="owner", on="2026-10-26")
    st = {i.key: status_of(i, load_approvals(copy)) for i in items(c)}
    assert st["rule:P2"] == "approved" and st["exception:P1-E1"] == "approved" and st["rule:U1"] == "unapproved"
    edit(copy, "principles.yaml", lambda r: r[5].update(text=r[5]["text"].replace(" and before", ", before")))
    c2 = load_contract(copy)
    st2 = {i.key: status_of(i, load_approvals(copy)) for i in items(c2)}
    assert st2["rule:P2"] == "changed" and st2["exception:P1-E1"] == "approved"


def test_source_edits_do_not_invalidate_approval(copy):
    approve(copy, load_contract(copy), ["rule:U1"], by="owner")
    edit(copy, "principles.yaml", lambda r: r[0].update(source={"kind": "doc", "file": "rules.md", "at": "U1"}))
    c = load_contract(copy)
    assert status_of(next(i for i in items(c) if i.key == "rule:U1"), load_approvals(copy)) == "approved"


def test_unknown_item_cannot_be_approved(copy):
    with pytest.raises(KeyError):
        approve(copy, load_contract(copy), ["rule:P9"], by="owner")


# ---------- review page ----------

def test_review_page_shows_every_rule_and_exception_condition():
    page = render(C, {}, interactive=False)
    for r in C.rules:
        assert f'id="rule-{r.id}"' in page
    assert "between 0 and 72 h, on exact timestamps" in page and "explains own tradeoff" in page
    assert "fare_lock" in page and "expires 2027-01-31" in page
    assert 'action="/approve"' not in page                      # static page is read-only


def test_interactive_review_page_has_approve_forms():
    page = render(C, {}, interactive=True)
    assert page.count('action="/approve"') == len(items(C)) + 1  # one per item + approve all
