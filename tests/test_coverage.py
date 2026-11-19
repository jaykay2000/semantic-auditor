"""Coverage map and persona drafting (`semaudit coverage`).

The map is re-derived offline from a review's pinned inputs (the committed Northbound sample here), so these tests
make no model call. Drafting is tested with a fake model reply: what matters is what code accepts or refuses."""
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from semaudit.contract.schema import load_contract  # noqa: E402
from semaudit.decide.pipeline import evaluate_release  # noqa: E402
from semaudit.models.router import Router  # noqa: E402
from semaudit.onboard import coverage as K  # noqa: E402

SAMPLE = ROOT / "docs" / "try-it" / "northbound-2.3-2.4"
CONTRACT = ROOT / "examples" / "northbound" / "contract"


@pytest.fixture(scope="module")
def derived():
    """The sample's head release re-derived offline: (contract, release eval)."""
    c = load_contract(CONTRACT)
    router = Router(root=SAMPLE, offline=True)
    router.cache_dir = SAMPLE / "model-cache"
    return c, evaluate_release(SAMPLE, "2.4", c, router)


def _without(h, keep):
    """The same release eval with only the entries `keep(entry)` accepts."""
    return SimpleNamespace(results={p: (s, [x for x in es if keep(x)]) for p, (s, es) in h.results.items()},
                           episodes=h.episodes)


def test_the_sample_review_has_one_gap_a_screen_its_releases_do_not_offer(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    cov = K.coverage_map(SAMPLE / "review-2.3-2.4.json", root=tmp_path)
    assert [g["id"] for g in cov["gaps"]] == ["surface:hotel_detail"]       # hotels come in 2.4.1, not 2.3 / 2.4
    assert cov["engine_gaps"] == [] and len(cov["personas"]) == 15


def test_a_rule_no_message_was_evaluated_under_is_a_gap(derived):
    c, h = derived
    got = K.gaps_of(c, _without(h, lambda x: x.rule != "U2"), "2.4")
    assert {"id": "U2:rule", "kind": "rule_never_exercised", "rule": "U2"}.items() <= \
        next(g for g in got["gaps"] if g["id"] == "U2:rule").items()


def test_a_fact_a_rule_checks_that_no_message_stated_is_a_gap(derived):
    c, h = derived
    rules = [r.model_copy(update={"check": {**r.check, "claims": [*r.check["claims"], "seats_total"]}})
             if r.id == "U1" else r for r in c.rules]
    got = K.gaps_of(c.model_copy(update={"rules": rules}), h, "2.4")
    assert [g["id"] for g in got["gaps"] if g["kind"] == "fact_never_checked"] == ["U1:fact:seats_total"]


def test_an_exception_that_never_applied_is_a_gap(derived):
    c, h = derived
    got = K.gaps_of(c, _without(h, lambda x: x.status != "excepted"), "2.4")
    assert "P1:exception:P1-E1" in [g["id"] for g in got["gaps"]]
    assert "P1:exception:P1-E1" not in [g["id"] for g in K.gaps_of(c, h, "2.4")["gaps"]]   # it applied in the sample


def test_a_rule_the_engine_cannot_check_is_listed_apart_not_as_a_persona_gap(derived):
    c, h = derived
    rules = [r.model_copy(update={"check": {"must": "oracle_arithmetic", "identities": ["a == b"]}})
             if r.id == "U2" else r for r in c.rules]
    got = K.gaps_of(c.model_copy(update={"rules": rules}), _without(h, lambda x: x.rule != "U2"), "2.4")
    assert "U2" in [x["rule"] for x in got["engine_gaps"]]
    assert not [g for g in got["gaps"] if g.get("rule") == "U2"]


# ---------------------------------------------------------------- drafts

C = load_contract(CONTRACT)
GAPS = {"surface:hotel_detail", "U2:rule"}


def _draft(**over):
    d = {"id": "nina", "name": "Nina", "role": "boundary: opens a hotel",
         "axes_json": json.dumps({"budget": "tight"}),
         "context_json": json.dumps({"route": "LIS-BER", "hotel": "LIS-H1"}),
         "joins_scenario": "S-hotel-imminent", "new_scenario_json": "", "closes": ["surface:hotel_detail"],
         "needs": ["the release offers hotels (2.4.1)"]}
    return {**d, **over}


def test_a_draft_that_fits_the_contract_passes_the_check():
    assert K.check_draft(_draft(), C, GAPS) == []
    new = json.dumps({"id": "S-hotel-only", "day0": "2026-11-02T00:00:00Z",
                      "steps": [{"at": "D0 10:00", "do": "open_hotel", "params": {"hotel": "LIS-H1"}}]})
    assert K.check_draft(_draft(joins_scenario="", new_scenario_json=new), C, GAPS) == []


@pytest.mark.parametrize("over, problem", [
    ({"id": "maya"}, "id maya is an existing persona"),
    ({"context_json": json.dumps({"route": "LIS-BER", "loyalty_tier": "gold"})},
     "context fields the contract does not use: loyalty_tier"),
    ({"axes_json": json.dumps({"mood": "happy"})}, "axes the contract's personas do not use: mood"),
    ({"joins_scenario": "S-nowhere"}, "joins unknown scenario S-nowhere"),
    ({"joins_scenario": "", "new_scenario_json": json.dumps(
        {"id": "S-new", "day0": "2026-11-02T00:00:00Z", "steps": [{"at": "D0 10:00", "do": "teleport"}]})},
     "step verbs the contract does not use: teleport"),
    ({"joins_scenario": "", "new_scenario_json": json.dumps(
        {"id": "S-new", "steps": [{"at": "D0 10:00", "do": "search"}]})}, "not a valid scenario"),
    ({"joins_scenario": "", "new_scenario_json": json.dumps(
        {"id": "S-hotel-imminent", "day0": "2026-11-02T00:00:00Z", "steps": [{"at": "D0 10:00", "do": "search"}]})},
     "new scenario id S-hotel-imminent already exists"),
    ({"joins_scenario": "", "new_scenario_json": ""}, "joins no scenario and proposes none"),
    ({"closes": ["U9:fact:invented"]}, "claims to close gaps that are not in the list: U9:fact:invented"),
    ({"closes": []}, "closes no gap"),
    ({"context_json": "{not json"}, "context or axes is not JSON"),
])
def test_a_draft_the_contract_cannot_express_is_refused(over, problem):
    assert any(p.startswith(problem) for p in K.check_draft(_draft(**over), C, GAPS))


def test_drafting_keeps_only_what_the_check_passes_and_says_what_stays_open():
    class R:
        roles = {"interpreter": {"model": "fake"}}

        def complete(self, role, messages, **kw):
            payload = json.loads(messages[1]["content"])
            assert {g["id"] for g in payload["gaps"]} == GAPS and payload["contract"]["personas"]
            return SimpleNamespace(cached=False, cost=0.01, parsed={
                "personas": [_draft(), _draft(id="maya", closes=["U2:rule"])],
                "not_closable": [{"gap": "U2:rule", "reason": "needs a fee the store does not charge"}]})
    cov = {"release": "2.4", "gaps": [{"id": g} for g in sorted(GAPS)]}
    out = K.draft_personas(C, cov, R())
    assert [(d["id"], d["check"]) for d in out["drafts"]] == [("nina", "ok"), ("maya", "refused")]
    assert out["gaps_left_open"] == ["U2:rule"] and out["status"].startswith("DRAFT")
    assert out["drafts"][0]["context"] == {"route": "LIS-BER", "hotel": "LIS-H1"}


def _drafts_file(tmp_path, **over):
    d = _draft(**over)
    rec = {"id": d["id"], "name": d["name"], "role": d["role"], "axes": json.loads(d["axes_json"]),
           "context": json.loads(d["context_json"]), "joins_scenario": d["joins_scenario"] or None,
           "new_scenario": None, "closes": d["closes"], "needs": d["needs"], "check": "ok", "problems": []}
    f = tmp_path / "coverage-drafts.yaml"
    import yaml
    f.write_text(yaml.safe_dump({"status": "DRAFT", "drafts": [rec]}))
    return f


def test_accepting_a_draft_appends_it_and_keeps_the_owners_files_as_written(tmp_path):
    cdir = tmp_path / "contract"
    shutil.copytree(CONTRACT, cdir)
    (cdir.parent / "adapter.py").symlink_to(CONTRACT.parent / "adapter.py")
    before = {f: (cdir / f).read_text() for f in ("personas.yaml", "scenarios.yaml")}
    changed = K.accept(_drafts_file(tmp_path), "nina", cdir)
    assert changed == ["personas.yaml: + nina", "scenarios.yaml: + S-hotel-imminent.nina"]
    for f, text in before.items():
        assert (cdir / f).read_text().startswith(text)                      # comments and layout untouched
    c = load_contract(cdir)
    assert "nina" in {p.id for p in c.personas}
    sc = next(s for s in c.scenarios if s.id == "S-hotel-imminent.nina")
    base = next(s for s in c.scenarios if s.id == "S-hotel-imminent")
    assert sc.personas == ["nina"] and [s.do for s in sc.steps] == [s.do for s in base.steps]
    assert "nina" not in base.personas                                     # the existing scenario is not edited


def test_a_draft_refused_or_no_longer_fitting_changes_nothing(tmp_path):
    cdir = tmp_path / "contract"
    shutil.copytree(CONTRACT, cdir)
    before = {f: (cdir / f).read_text() for f in ("personas.yaml", "scenarios.yaml")}
    with pytest.raises(ValueError, match="no longer fits"):
        K.accept(_drafts_file(tmp_path, id="maya"), "maya", cdir)
    with pytest.raises(ValueError, match="no draft"):
        K.accept(_drafts_file(tmp_path), "zed", cdir)
    assert {f: (cdir / f).read_text() for f in before} == before


def test_accept_puts_the_files_back_when_the_contract_no_longer_loads(tmp_path, monkeypatch):
    cdir = tmp_path / "contract"
    shutil.copytree(CONTRACT, cdir)
    before = {f: (cdir / f).read_text() for f in ("personas.yaml", "scenarios.yaml")}
    real, calls = K.load_contract, []

    def load(d, *a, **k):
        calls.append(d)
        if len(calls) > 1:                                   # the load after the append
            raise ValueError("the contract no longer loads")
        return real(d, *a, **k)
    monkeypatch.setattr(K, "load_contract", load)
    with pytest.raises(ValueError, match="no longer loads"):
        K.accept(_drafts_file(tmp_path), "nina", cdir)
    assert {f: (cdir / f).read_text() for f in before} == before
