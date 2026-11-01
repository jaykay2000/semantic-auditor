"""The v9 video frames read every number from their data files, and those files hold together (no browser, no model).

Checked without the source folders (the Finablo and Spree harness runs are not in this repository):
  * scenes-data/v9.json: the figures each frame prints agree with each other and with the committed gate record;
  * the m9 frames carry none of those figures as literals outside comments, so a frame cannot drift from its data;
  * scenes-data/close.json: the end card's commands are copied from README.md;
  * docs/sample-review/: the hosted sample review passes demo/build_sample_review.py's own publish checks.
"""
import hashlib
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "demo" / "video-assets"
SLIDES = ASSETS / "slides-src"
V9 = json.loads((ASSETS / "scenes-data" / "v9.json").read_text())
CLOSE = json.loads((ASSETS / "scenes-data" / "close.json").read_text())
FRAMES = sorted(SLIDES.glob("m9-*.html"))


def _money(s):
    return Decimal(s.replace("$", "").replace(",", ""))


def _visible(path):
    """The frame's source with HTML comments removed (comments may cite the numbers they source)."""
    return re.sub(r"<!--.*?-->", "", path.read_text(), flags=re.S)


def test_there_are_v9_frames():
    names = {p.stem for p in FRAMES}
    assert {"m9-b1-hook", "m9-b2-what-sra-does", "m9-b3-spree", "m9-b4-1-discovery-to-check", "m9-b4-2-fail-pass-reload",
            "m9-b5-intent", "m9-b6-your-app", "m9-b7-finablo", "m9-b8-close", "m9-b8-end-card"} <= names


def test_beat1_gate_matches_the_committed_record():
    g = V9["gate"]
    rec = ROOT / g["source"]
    assert hashlib.sha256(rec.read_bytes()).hexdigest() == g["sha256"]
    text = rec.read_text()
    assert f'{g["ok"]} OK' in text and f'{g["fail"]} FAIL' in text and g["summary_line"] in text and g["date"] in text


def test_beat1_and_beat7_finablo_figures_hold_together():
    f = V9["finablo"]
    ok = f["correct_limit"]
    assert sum(_money(x) for x in re.findall(r"\$[\d,]+", f["correct_limit_basis"])) == _money(ok)
    assert f["shown"]["report"] != f["shown"]["copied"] and ok not in (f["shown"]["report"], f["shown"]["copied"])
    places = f["limits"]["places"]
    assert len(places) == f["limits"]["v707_steps_stating_a_limit"] == f["limits"]["v707"][ok] > 0
    assert all(p["v707"] == ok for p in places) and not any(p["v706"] == ok for p in places)
    assert {p["v706"] for p in places} == {f["shown"]["report"], f["shown"]["copied"]}


def test_beat3_the_order_page_contradicts_itself():
    s = V9["spree"]
    m = {k: _money(r["text"]) for k, r in s["rows"].items()}
    assert m["subtotal"] + m["shipping"] + m["tax"] == m["total"]          # the page's total excludes the line's tax
    assert m["line"] + m["shipping"] + m["tax"] != m["total"]              # its line amount does not
    assert m["line"] > m["subtotal"] and s["rows"]["subtotal"]["text"] == s["record_item_total"]
    assert s["delta"] == "pre_existing" and 0 < s["shoppers_shown_it"] <= s["shoppers"]


def test_beat5_maya_flagged_lena_cleared_on_the_same_offers():
    n = V9["northbound"]
    assert [o["text"] for o in n["maya"]["offers"]] == [o["text"] for o in n["lena"]["offers"]]
    assert n["maya"]["verdict"] == "flagged" and n["lena"]["verdict"] == "cleared"
    assert n["rule"]["key_phrase"] in n["rule"]["text"] and n["key_words_in_lena_message"] == []
    lena = n["lena"]["explains"]["text"].lower()
    assert "explain" not in lena and "tradeoff" not in lena and "material" not in lena   # the frame says so on screen
    rules = ROOT / n["rules"]
    assert hashlib.sha256(rules.read_bytes()).hexdigest() == n["rules_sha256"]


# Figures a frame must take from its data, never type. (The beat 4 figures live in beat4.json, checked by its own
# extractor; beat 6's in brightdesk.json, checked by tests/test_demo_brightdesk_evidence.py.)
LITERALS = ["$24,500", "$32,500", "$35,750", "354", "$43.19", "$39.99", "$3.60", "$48.59", "15,805", "15805", "$0.13",
            "0.1323", "49", "179.38", "194.38", "$12", "$15", "jaykay2000", "--max-usd"]


def test_the_frames_type_no_figure_they_show():
    hits = []
    for p in FRAMES:
        src = _visible(p)
        for lit in LITERALS:
            for m in re.finditer(re.escape(lit), src):
                if lit.isdigit() and (src[m.start() - 1:m.start()].isalnum() or src[m.end():m.end() + 1].isalnum()):
                    continue                                              # part of a longer token (e.g. 1.49, s04)
                hits.append(f"{p.name}: {lit}")
        for word in ("HOLD", "SHIP", "FAIL", "PASS"):
            if re.search(rf">\s*{word}\s*<", src):
                hits.append(f"{p.name}: >{word}<")
    assert not hits, "figures typed into v9 frames instead of read from data:\n" + "\n".join(hits)


def test_the_guard_bites():
    probe = SLIDES / "m9-zz-probe.html"
    try:
        probe.write_text('<div class="v">$35,750</div><!-- $24,500 in a comment is fine --><b>HOLD</b>')
        global FRAMES
        saved, FRAMES = FRAMES, [probe]
        try:
            test_the_frames_type_no_figure_they_show()
        except AssertionError as e:
            assert "$35,750" in str(e) and ">HOLD<" in str(e) and "$24,500" not in str(e)
        else:
            raise AssertionError("the literal guard did not fire")
        finally:
            FRAMES = saved
    finally:
        probe.unlink()


def test_the_end_card_commands_are_the_readme_s():
    readme = (ROOT / "README.md").read_text()
    for cmd in CLOSE["run"]:
        assert cmd in readme, cmd
    assert CLOSE["sample_url"].startswith("https://jaykay2000.github.io/semantic-auditor/")
    assert CLOSE["repo_url"] == "https://github.com/jaykay2000/semantic-auditor"


def test_beat2_makes_no_vision_claim():
    src = _visible(SLIDES / "m9-b2-what-sra-does.html").lower()
    for phrase in ("sees", "screenshot", "image", "vision", "the way a user would", "looks at"):
        assert phrase not in src, phrase


def test_the_sample_review_is_safe_to_publish():
    sys.path.insert(0, str(ROOT / "demo"))
    from build_sample_review import problems
    folder = ROOT / "docs" / "sample-review"
    page = (folder / "index.html").read_text()
    assert len(re.findall(r'"screenshot":\s*"[^"]+\.png"', page)) > 10          # the capture check is not vacuous
    assert problems(folder) == []


def test_the_sample_review_check_bites(tmp_path):
    sys.path.insert(0, str(ROOT / "demo"))
    from build_sample_review import problems
    (tmp_path / "index.html").write_text('<div style="cursor:pointer">x</div>\n"dir": "/Users/someone/src"\n'
                                         'drafted by gpt-4o\n<script src="https://cdn.example/x.js"></script>\n'
                                         '"screenshot": "captures/a.png"')
    found = "\n".join(problems(tmp_path))
    for what in ("local path", "model name: gpt-4o", "https://cdn.example", "external script", "missing capture captures/a.png"):
        assert what in found, what
    assert "cursor" not in found
