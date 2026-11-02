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


def test_beat2_claims_screenshots_only_as_the_opt_in_check():
    src = _visible(SLIDES / "m9-b2-what-sra-does.html")
    low = src.lower()
    for phrase in ("sees the page", "as images", "image", "vision", "the way a user would", "looks at", "every screenshot"):
        assert phrase not in low, phrase
    # the one mention of a screenshot is the opt-in check, said with "can"
    lines = [ln for ln in low.splitlines() if "screenshot" in ln]
    assert len(lines) == 1 and "can check the screenshot" in lines[0] and "opt-in" in lines[0], lines


def test_beat3_visual_confirmation_is_the_committed_run():
    v, s = V9["visual"], V9["spree"]
    ev = ROOT / v["source"]
    assert hashlib.sha256((ev / "visual.json").read_bytes()).hexdigest() == v["visual_sha256"]
    assert hashlib.sha256((ev / "control.json").read_bytes()).hexdigest() == v["control_sha256"]
    assert hashlib.sha256((ev / "crop.png").read_bytes()).hexdigest() == v["crop_sha256"]
    run = json.loads((ev / "visual.json").read_text())
    ctl = json.loads((ev / "control.json").read_text())
    assert run["issue"] == s["issue"] and run["visual"]["event"] == s["event"]
    assert run["visual"]["screenshot"] == s["shot"] and run["visual"]["sent_sha256"] == v["crop_sha256"]
    assert run["visual"]["quote"] == run["visual"]["reads"] == v["reads"] == s["rows"]["line"]["text"]
    assert run["visual"]["result"] == v["result"] == "confirmed"
    assert ctl["visual"]["quote"] == v["control"]["quote"] == s["rows"]["subtotal"]["text"]
    assert ctl["visual"]["result"] == v["control"]["result"] == "contradicted"
    assert ctl["visual"]["sent_sha256"] == v["crop_sha256"]                       # the same image, a different claim
    assert run["verification_status_before_and_after"] == "unverified"             # it never changes a verdict
    src = re.sub(r"<title>.*?</title>", "", _visible(SLIDES / "m9-b3-spree.html"))   # the title says "contradicted itself"
    assert not re.search(r"\b(confirmed|contradicted)\b", src, re.I), "beat 3 types the visual result"


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


# ---- second owner review (2026-11-01) ----

THESIS = "SRA turns discoveries into checks your next release has to pass."


def test_the_thesis_claims_no_every():
    # 6 of 57 held-out findings fully converted, and the Finablo bug was refused: "every discovery" overclaims
    assert CLOSE["thesis"] == THESIS
    for p in FRAMES:
        assert not re.search(r"every discover", _visible(p), re.I), p.name
    for name in ("m9-b2-what-sra-does.html", "m9-b8-close.html"):
        assert "discoveries into" in _visible(SLIDES / name), name


def test_beat6_says_working_from_not_given_only():
    src = _visible(SLIDES / "m9-b6-your-app.html")
    assert "given only" not in src and "working from SRA" in src


def test_beat2_tiles_use_the_review_page_labels():
    page = (ROOT / "src/semaudit/report/templates/release_story.html").read_text()
    labels = re.search(r"const GROUPS = \[(.*?)\];", page, re.S).group(1)
    short = re.findall(r"\['\w+', [^,]+, '([^']+)'\]", labels)
    assert short == ["New", "Resolved", "Pre-existing", "Unconfirmed"]
    src = _visible(SLIDES / "m9-b2-what-sra-does.html")
    tiles = re.findall(r'<span class="(?:nw|fx|pr|ct) pop"[^>]*>([^<]+)<small>', src)
    assert tiles == short


def test_end_card_models_are_the_ones_the_demo_used():
    sample = (ROOT / "docs/sample-review/index.html").read_text()
    spark = sorted(set(re.findall(r'"muse-spark-(\d\.\d)"', sample)), reverse=True)
    assert spark == ["1.3", "1.2"]
    open_model = json.loads((ASSETS / "scenes-data" / "brightdesk.json").read_text())["model"]
    assert open_model == "meta-models/muse-spark-open-1026"
    assert CLOSE["models"] == f"Muse Spark {spark[0]} · {spark[1]} (Meta Model API) · Muse Spark Open (open weights)"


def test_beat6_opening_pages_carry_the_record_prices():
    bp = V9["brightdesk_pages"]
    prices = json.loads((ASSETS / "scenes-data" / "brightdesk.json").read_text())["prices_broken"]
    for k in ("pricing", "checkout"):
        assert bp[k]["price"] == prices[k] and f'{prices[k]} per month' in bp[k]["text"]
    from test_demo_assets_clean import LOCAL_PATH, NAMES
    assert not any(LOCAL_PATH.search(bp[k]["text"]) or NAMES.search(bp[k]["text"]) for k in bp)


def test_beat4b_shows_no_base_or_head():
    src = _visible(SLIDES / "m9-b4-2-fail-pass-reload.html")
    assert "replace(/\\bthe base\\b/, 'the old release')" in src and "replace(/\\bthe head\\b/, 'the new one')" in src


def test_beat4a_gate_line_is_the_gate_s_documented_behaviour():
    src = re.sub(r"\s+", " ", (SLIDES / "m9-b4-1-discovery-to-check.html").read_text())
    assert "A gate refuses drafts that drop or invent an action." in src
    assert "Gate: nothing dropped or invented" in src
    readme = (ROOT / "README.md").read_text()
    assert "no instruction is\n  dropped silently" in readme or "no instruction is dropped" in readme.replace("\n  ", " ")
    assert "every action in the text is carried out by a step" in readme


def test_cue_tables_define_every_cue_they_use():
    for name in ("m9-b2-what-sra-does", "m9-b4-1-discovery-to-check", "m9-b5-intent", "m9-b6-your-app"):
        src = (SLIDES / f"{name}.html").read_text()
        table = re.search(r"const CUES = \{(.*?)\};", src, re.S).group(1)
        keys = set(re.findall(r"(\w+):\s*[\d.]+", table))
        used = {u.split("+")[0] for u in re.findall(r'data-(?:out)?(?:on)?cue="([\w+.-]+)"', src)}
        assert used and used <= keys, (name, used - keys)
        times = [float(t) for t in re.findall(r"\w+:\s*([\d.]+)", table)]
        assert times == sorted(times), name                                     # cues run in spoken order
