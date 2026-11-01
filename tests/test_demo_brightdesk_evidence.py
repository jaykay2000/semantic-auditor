"""The Brightdesk frame's numbers come from a committed evidence record (Codex round 3, R3-02).

Beat 6 of the v8 video (m8-b6-your-app) shows HOLD, SHIP and $0.13 in model calls. These check, without the
new-user test's own folder, that the committed record adds up, that the frame data is exactly what the record
derives, that the frame hardcodes none of it, and that the motion README quotes the same totals.
"""

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "demo" / "evidence" / "newuser-brightdesk-2026-11-01"
ASSETS = ROOT / "demo" / "video-assets"
FRAME = ASSETS / "slides-src" / "m8-b6-your-app.html"
DATA = ASSETS / "scenes-data" / "brightdesk.json"
HYGIENE = ROOT / "tests" / "test_demo_assets_clean.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


EXTRACT = _load(ASSETS / "slides-src" / "extract_brightdesk.py", "extract_brightdesk_under_test")
RECORD = json.loads((EVIDENCE / "record.json").read_text())
BILLED = [json.loads(line) for line in (EVIDENCE / "ledger-billed.jsonl").read_text().splitlines() if line.strip()]


def test_the_billed_rows_add_up_to_the_record():
    assert BILLED and all(r["cached"] is False for r in BILLED)
    assert len(BILLED) == RECORD["ledger"]["billed_calls"] == 15
    assert round(sum(r["cost_usd"] for r in BILLED), 6) == RECORD["ledger"]["billed_usd"] == 0.132284
    by_tag = RECORD["ledger"]["by_tag"]
    assert sum(t["billed_calls"] for t in by_tag.values()) == len(BILLED)
    assert sum(t["billed_calls"] + t["cached_calls"] for t in by_tag.values()) == RECORD["ledger"]["rows"]


def test_the_record_passes_the_extractors_own_checks():
    assert EXTRACT.check(RECORD, BILLED) == []
    assert set(RECORD["sources"]) == {EXTRACT.HOLD, EXTRACT.SHIP, EXTRACT.LEDGER}
    assert all(re.fullmatch(r"[0-9a-f]{64}", h) for h in RECORD["sources"].values())


def test_the_checks_bite():
    bad = json.loads(json.dumps(RECORD))
    bad["reviews"]["ship"]["recommendation"] = "hold"
    bad["reviews"]["hold"]["issues"] = bad["reviews"]["hold"]["issues"][:1]
    bad["reviews"]["hold"]["cost_usd"] = 0.5
    errors = EXTRACT.check(bad, BILLED)
    assert len(errors) == 3, errors
    assert EXTRACT.check(RECORD, BILLED[:-1])          # a dropped billed row is caught


def test_the_frame_data_is_what_the_record_derives():
    data = json.loads(DATA.read_text())
    assert data == EXTRACT.frame_data(RECORD)
    assert (data["hold"], data["ship"], data["cost_shown"]) == ({"label": "HOLD", "new": 3},
                                                                {"label": "SHIP", "resolved": 3}, "$0.13")


def test_the_frame_reads_its_numbers_from_the_data():
    html = re.sub(r"<!--.*?-->", "", FRAME.read_text(), flags=re.S)
    assert "window.DATA.brightdesk" in html
    for literal in ("$0.13", "0.1323", ">HOLD<", ">SHIP<"):
        assert literal not in html, literal


def test_the_motion_readme_quotes_the_record():
    line = next(t for t in (ASSETS / "motion" / "README.md").read_text().splitlines() if "`m8-b6-your-app`" in t)
    assert f"{RECORD['ledger']['billed_calls']} billed calls" in line
    assert f"${RECORD['ledger']['billed_usd']:.4f}" in line


def test_the_evidence_names_no_local_path_agent_or_non_meta_model():
    hygiene = _load(HYGIENE, "hygiene_patterns")
    for p in sorted(EVIDENCE.iterdir()):
        for n, line in enumerate(p.read_text().splitlines(), 1):
            assert not hygiene.LOCAL_PATH.search(line), f"{p.name}:{n}"
            assert not hygiene.NAMES.search(line), f"{p.name}:{n}"
