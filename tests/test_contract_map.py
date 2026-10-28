"""Contract-level attribution for a product that marks none of its text (method contract_map), in a real
Chromium: blocks under section roots, the innermost section wins, inline children stay in their block, own text
beside block children is kept, unreadable text is captured and marked obscured (never a message), and a text
surface splits at its headings. Plus oracle variants: the most specific readable variant is used, headers are
filled from params but never recorded, and `root` makes field paths relative."""

import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.adapters.hooks import OracleClient  # noqa: E402
from semaudit.capture.attribution import Keys, signature, text_sections  # noqa: E402
from semaudit.capture.runner import Runner  # noqa: E402
from semaudit.contract.schema import Oracle, Surface  # noqa: E402
from semaudit.story.episode import Capture, Episode, StepRecord  # noqa: E402

PAGE = """<html><body style="margin:0">
<header><p>Site chrome, in no section</p></header>
<section class="hero"><h2>Your freedom age</h2><p>Work becomes optional at <span class="pill" style="display:inline-block">52</span>.</p>
  <div class="card">Ten years sooner than plan <div>nested detail line</div></div>
  <div class="milestone"><p>Coast FI at 44</p></div></section>
<section class="plan"><p>Your first move: ramp to $24,500/yr</p>
  <p style="filter: blur(5px)">Locked move two $32,500</p>
  <div style="opacity:0.1"><p>Faded move three</p></div>
  <p style="visibility:hidden">Hidden move four</p>
  <div style="position:relative"><p>Under the frosted glass</p>
    <div style="position:absolute;inset:0;backdrop-filter:blur(4px)"></div></div>
  <div style="display:none"><p>Inside a collapsed section</p></div>
  <details><summary>More</summary><p>Inside closed details</p></details>
  <p>Same template $1,000</p><p>Same template $2,000</p></section>
</body></html>"""

SURFACE = Surface(id="report", kind="web", locator="css", sections=[
    {"match": ".hero", "feature": "snapshot"}, {"match": ".milestone", "feature": "milestones"},
    {"match": ".plan", "feature": "plan", "component": "advice"}])


@pytest.fixture(scope="module")
def blocks():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1000, "height": 600})
        page.set_content(PAGE)
        cap = Capture(id="c1", kind="web", surface="report", at="2026-10-28T10:00:00")
        Runner._section_blocks(cap, page, SURFACE)
        b.close()
    return cap


def by_text(cap):
    return {e.text: e for e in cap.elements}


def test_blocks_are_attributed_to_the_innermost_section(blocks):
    t = by_text(blocks)
    assert "Site chrome, in no section" not in t
    assert t["Your freedom age"].attribution["feature"] == "snapshot"
    assert t["Work becomes optional at 52."].attribution["feature"] == "snapshot"     # the pill stays in its block
    assert t["Coast FI at 44"].attribution["feature"] == "milestones"
    assert t["Your first move: ramp to $24,500/yr"].attribution["component"] == "advice"
    assert all(e.attribution["method"] == "contract_map" for e in blocks.elements)


def test_own_text_beside_a_block_child_is_kept_separately(blocks):
    t = by_text(blocks)
    assert t["Ten years sooner than plan"].locator.get("own_text") is True
    assert "nested detail line" in t


def test_unreadable_text_is_captured_and_marked(blocks):
    t = by_text(blocks)
    assert t["Locked move two $32,500"].obscured == "blur"
    assert t["Faded move three"].obscured == "transparent"
    assert t["Under the frosted glass"].obscured == "covered"
    assert t["Inside a collapsed section"].obscured == "collapsed"
    assert t["Inside closed details"].obscured == "collapsed" and t["More"].obscured is None
    assert "Hidden move four" not in t or t["Hidden move four"].obscured == "hidden"
    assert t["Your first move: ramp to $24,500/yr"].obscured is None
    assert blocks.meta["obscured"] >= 3


def test_same_template_blocks_get_distinct_keys_and_numbers_do_not_change_a_key(blocks):
    t = by_text(blocks)
    k1, k2 = t["Same template $1,000"].attribution["key"], t["Same template $2,000"].attribution["key"]
    assert k1 != k2 and k2 == k1 + "#2"
    assert signature("ramp to $24,500/yr") == signature("ramp to $32,500/yr")


def test_obscured_text_is_never_a_message(blocks):
    ep = Episode(release="h", persona="p", scenario="s", app_build="h", started_wall="x", day0="2026-10-28T10:00:00",
                 clock_measured=False, steps=[StepRecord(seq=1, at="2026-10-28T10:00:00", do="open", status="done",
                                                         captures=[blocks])])
    texts = {m["text"]: m for m in ep.messages()}
    assert "Locked move two $32,500" not in texts and "Under the frosted glass" not in texts
    m = texts["Your first move: ramp to $24,500/yr"]
    assert m["feature"] == "plan" and m["attribution"] == "contract_map" and m["component"] == "advice"


def test_a_text_surface_splits_at_headings():
    s = Surface(id="export", kind="text", locator="text_section",
                sections=[{"match": "^my numbers$", "feature": "inputs"}, {"match": "first move", "feature": "plan"}])
    text = "Paste this into your AI.\n\n# Report\n\n## My numbers\n- Income: $9,000\n\n## My first move\nRamp it.\n\n## Other\nx"
    parts = text_sections(s, text)
    assert [p["heading"] for p in parts] == [None, "Report", "My numbers", "My first move", "Other"]
    assert [p["section"] for p in parts] == [-1, -1, 0, 1, -1]
    p = parts[2]
    assert text[p["span"][0]:p["span"][1]] == "## My numbers\n- Income: $9,000"


def test_keys_count_occurrences_per_capture():
    k = Keys()
    assert k("f", "a 1") == k("f", "a 2")[:-2] and k("f", "b") != k("f", "a 3")


def test_an_oracle_reads_its_most_specific_variant_with_headers_and_root():
    seen = []

    def handler(req):
        seen.append((req.url.path, req.headers.get("authorization")))
        if req.url.path == "/api/me/report":
            return httpx.Response(200, json={"score": 71})
        return httpx.Response(200, json={"report": {"score": 64}})
    http = httpx.Client(transport=httpx.MockTransport(handler))
    o = Oracle(id="r", endpoint="/api/guest/{gid}", root="$.report", fields={"score": "$.score"},
               variants=[{"endpoint": "/api/me/report", "headers": {"Authorization": "Bearer {token}"}}])
    c = OracleClient("http://x", [o], http)
    assert c.read(o, {"gid": "g1"}).values == {"score": 64}
    r = c.read(o, {"gid": "g1", "token": "t0k"})
    assert r.values == {"score": 71} and r.endpoint == "/api/me/report" and "t0k" not in r.model_dump_json()
    assert seen[-1] == ("/api/me/report", "Bearer t0k")
    assert c.read(o, {}).status == "not_applicable"
