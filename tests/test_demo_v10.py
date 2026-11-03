"""The v10 screens (storyboard v14.1, demo cut 3) show only what the committed evidence says (no browser, no model).

Checked without the source folders (the Spree and Finablo harness repos are not in this repository):
  * scenes-data/v10.json against the committed records it was extracted from: personas, rule P2, the saved check and
    its approval, the "6 of 57", the self-check, Spree's two files (by git blob id), the results board;
  * the m10 frames type none of those figures, name no agent or model other than Muse Spark, and keep one cue table.
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "demo" / "video-assets"
SLIDES = ASSETS / "slides-src"
V10 = json.loads((ASSETS / "scenes-data" / "v10.json").read_text())
V9 = json.loads((ASSETS / "scenes-data" / "v9.json").read_text())
FRAMES = sorted(SLIDES.glob("m10-*.html"))
NAMES = ["m10-v1-problem", "m10-v2-contributions", "m10-v3-personas", "m10-v4-keeps", "m10-v5-checks-itself",
         "m10-v6-plugs-in", "m10-v7-results"]
sys.path.insert(0, str(ROOT / "src"))


def _visible(p):
    return re.sub(r"<!--.*?-->", "", p.read_text(), flags=re.S)


def test_there_are_the_v10_screens():
    assert [p.stem for p in FRAMES] == NAMES


def test_cue_tables_define_every_cue_they_use():
    for p in FRAMES:
        src = p.read_text()
        table = re.search(r"const CUES = \{(.*?)\};", src, re.S).group(1)
        keys = set(re.findall(r"(\w+):\s*[\d.]+", table))
        used = {u.split("+")[0] for u in re.findall(r'data-(?:out)?(?:on)?cue="([\w+.-]+)"', src)}
        used |= {u.split("+")[0] for u in re.findall(r"cueAt\(CUES, '([\w+.-]+)'\)", src)}
        assert used and used <= keys, (p.name, used - keys)
        times = [float(t) for t in re.findall(r"\w+:\s*([\d.]+)", table)]
        assert times == sorted(times), p.name


def test_no_other_agent_model_or_app():
    from test_demo_assets_clean import NAMES as BAD
    for p in FRAMES:
        src = _visible(p)
        assert not BAD.search(src), p.name
        for word in ("brightdesk", "531"):
            assert word not in src.lower(), (p.name, word)
        # the only models a frame names are Muse Spark's
        for m in re.findall(r"model: '([^']+)'", src):
            assert m.startswith("Muse Spark"), (p.name, m)
    blob = json.dumps(V10)
    assert not BAD.search(blob) and "rightdesk" not in blob


def test_the_frames_type_no_figure_they_show():
    lits = ["6 of 57", "57", "531", "v708", "Oct 30", "Nov 1", "f0cb1dc9ee14fc8f", "Jayant Kumar", "2026-11-01",
            "beta2", "beta3", "ic-owner-rec-1", "$35,750", "LIS-BER", "283", "289"]
    hits = []
    for p in FRAMES:
        src = re.sub(r"<div class=\"src9.*?</div>", "", _visible(p), flags=re.S)   # the source line may cite them
        for lit in lits:
            for m in re.finditer(re.escape(lit), src):
                if lit.isdigit() and (src[m.start() - 1:m.start()].isalnum() or src[m.end():m.end() + 1].isalnum()):
                    continue
                hits.append(f"{p.name}: {lit}")
        if re.search(r">\s*(FAIL|PASS)\s*<", src):
            hits.append(f"{p.name}: typed FAIL/PASS")
    assert not hits, hits


def test_contributions_are_the_storyboard_s_four():
    c = V10["contributions"]
    assert [x["title"] for x in c] == ["Judges what no test assertion can check", "Keeps what agents find",
                                       "Checks its own work", "Plugs into your app"]
    assert all("Muse Spark" in x["muse"] for x in c) and not any("every" in x["muse"].lower() for x in c)


def test_v1_shows_the_right_limit_beside_the_wrong_ones():
    src = _visible(SLIDES / "m10-v1-problem.html")
    assert "correct for age 61:" in src and "V.finablo.correct_limit" in src
    assert "what users see." in src


def test_v3_finablo_rules_are_h1_and_h2_title_and_text_only():
    f = V10["v3"]["finablo"]
    assert [r["id"] for r in f["rules"]] == ["H1", "H2"] and set(f["rules"][0]) == {"id", "title", "text"}
    assert f["rules"][0]["text"].startswith("Every IRS contribution limit we quote, and the room left under it, is the "
                                            "one for the user's own age")
    assert f["rules"][1]["text"] == ("A tax limit, and the room left under it, reads the same wherever we show it to "
                                     "the same user.")
    assert f["source"].endswith("contract-wide/principles.yaml") and re.fullmatch(r"[0-9a-f]{40}", f["blob"])


def test_v3_maya_verdict_is_the_sample_review_s():
    v = V10["v3"]["verdict"]
    page = (ROOT / v["source"]).read_text()
    # the page builds the title at render time (shoot_v10.py probes the rendered title); its manifest names the model
    assert "unexplained_tradeoff" in page and f'"{v["model_role"]}": "{v["model"]}"' in page
    assert v["model"] == "muse-spark-1.3" == V9["northbound"]["models"][v["model_role"]]
    assert "Muse Spark's verdict for Maya" in _visible(SLIDES / "m10-v3-personas.html")


def test_personas_and_rule_are_the_contract_s_own_lines():
    v = V10["v3"]
    text = (ROOT / v["source"]).read_text()
    assert hashlib.sha256((ROOT / v["source"]).read_bytes()).hexdigest() == v["sha256"]
    for pid in ("maya", "lena"):
        assert "\n".join(v[pid]) in text and v[pid][0].startswith(f"- {{id: {pid},")
    rules = (ROOT / v["rule_source"]).read_text()
    assert all(ln in rules.splitlines() for ln in v["rule_lines"])
    assert v["rule_lines"][-1].endswith(V9["northbound"]["rule"]["text"]) and v["key_phrase"] in v["rule_lines"][-1]
    import yaml
    for pid in ("maya", "lena"):                         # the plain-words card says what the YAML says, nothing more
        e = yaml.safe_load("\n".join(v[pid]))[0]
        plain = dict(v[pid + "_plain"])
        assert plain["Trip"] == e["context"]["route"].replace("-", " → ")
        assert plain["Seats left at the fare"] == str(e["world"]["seats"]["LIS-BER-NR"])
        assert plain.get("Budget") == e.get("axes", {}).get("budget")
        assert plain["Price forecast"] == f"drops within {e['world']['forecast']['LIS-BER']['window_days']} days"
    src = _visible(SLIDES / "m10-v3-personas.html")
    assert "written by the owner" in src and "Northbound · a demo travel app" in src


def test_the_approval_stamp_pins_the_check_as_stored_today():
    import yaml

    from semaudit.imported.record import ImportedCheck
    v = V10["v4"]
    d = ROOT / Path(v["approval"]["source"]).parent
    ap = yaml.safe_load((d / "approvals.yaml").read_text())[f"check:{v['id']}"]
    assert ap == {"hash": v["approval"]["fingerprint"], "by": v["approval"]["by"], "date": v["approval"]["date"]}
    assert ImportedCheck.load(d, v["id"]).digest() == ap["hash"]          # edit the check and this stops holding
    src = yaml.safe_load((d / "checks" / f"{v['id']}.yaml").read_text())["source"]
    assert {k: src[k] for k in v["report"]} == v["report"]               # the agent's report, word for word
    card = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", (ROOT / v["run"]["card"]).read_text()))
    assert f"approved digest {ap['hash']} (by {ap['by']})" in card and v["run"]["id"] in card
    assert (v["older"]["assertion"], v["newer"]["assertion"], v["memory"]) == ("fail", "pass", "fix_confirmed")
    assert len(v["steps"]) == 9 and v["gate_problems_per_round"][-1] == 0 and "muse-spark-open" in v["drafted_by"]


def test_six_of_fifty_seven_is_the_committed_count():
    p = V10["v4"]["prototype"]
    rows = re.findall(r"^\s+\S+#\d+\s+(\w+)", (ROOT / p["conversions"]).read_text(), re.M)
    assert (p["converted"], p["held_out"]) == (rows.count("converted"), len(rows)) == (6, 57)
    src = _visible(SLIDES / "m10-v4-keeps.html")
    assert "prototype: today SRA keeps only reports where it can verify every step (${P.converted} of ${P.held_out})" in src


def test_the_self_check_crop_is_the_committed_one():
    s = V10["v5"]
    assert hashlib.sha256((ROOT / s["source"]).read_bytes()).hexdigest() == s["sha256"]
    readme = (ROOT / s["source"]).with_name("README.md").read_text()
    assert "passed, 6 of 6" in readme and "Muse Spark 1.3" in readme      # the pill names the judge it ran on
    x0, y0, x1, y1 = s["line_box"]
    assert 0 <= x0 < x1 <= s["size"][0] and 0 <= y0 < y1 <= s["size"][1]
    src = _visible(SLIDES / "m10-v5-checks-itself.html")
    assert "Muse Spark 1.3" in src and "a second, real bug" in src
    vz = V9["visual"]
    assert (vz["result"], vz["control"]["result"], vz["control"]["quote"]) == ("confirmed", "contradicted", "$39.99")


def test_spree_files_are_the_committed_text():
    f = V10["v6"]["files"]
    text = f["rules"]["text"].encode()
    blob = subprocess.run(["git", "hash-object", "--stdin"], input=text, capture_output=True, check=True).stdout
    assert blob.decode().strip() == f["rules"]["blob"]                   # the same bytes as spree-semaudit main
    assert f["rules"]["ids"] == re.findall(r"^- id: (\S+)", f["rules"]["text"], re.M) and len(f["rules"]["ids"]) == 13
    assert sum(len(r["ids"]) for r in f["rules"]["plain"]) == 13
    for r in f["rules"]["plain"]:
        for i in r["ids"]:
            assert re.search(rf"^- id: {re.escape(i)}\n  title: {re.escape(r['title'])}$", f["rules"]["text"], re.M)
    assert "text" not in f["adapter"]                                    # v15: no adapter scroll
    run = json.loads((ROOT / f["spree_checks"]["source"]).read_text())
    assert {c["results"][r]["models"]["judging"] for c in run["checks"] for r in ("current", "candidate")} == \
        {"meta-models/muse-spark-open-1026"} and f["spree_checks"]["line"] == "Spree checks: Muse Spark Open (open weights)"
    assert set(V10["v6"]["shots"]["labels"]) == {"spree", "finablo", "northbound"}
    assert "test user" in V10["v6"]["shots"]["labels"]["finablo"]


def test_results_board_is_the_committed_record():
    b = V10["v7"]
    places, ok = V9["finablo"]["limits"]["places"], V9["finablo"]["correct_limit"]
    assert b["finablo_fixed"]["right"] == b["finablo_fixed"]["places"] == len(places) == sum(p["v707"] == ok for p in places)
    rec = json.loads((ROOT / b["finablo_regression"]["source"]).read_text())
    assert (b["finablo_regression"]["count"], b["finablo_regression"]["introduced"]) == \
        (rec["regressions_confirmed"], rec["regression_introduced"]) == (1, "v708")
    up = (ROOT / b["spree"]["source"]).read_text()
    assert "posted by the owner 2026-10-30T" in up and "merged 2026-11-01T" in up
    assert (b["spree"]["reported"], b["spree"]["merged"]) == ("Oct 30", "Nov 1")
    assert f"https://{b['spree']['repo']}/issues/{b['spree']['issue']}" in up and f"PR #{b['spree']['pr']}" in up
    assert b["saved_check"]["memory"] == "fix_confirmed" and b["saved_check"]["release"] == V10["v4"]["newer"]["name"]
    src = _visible(SLIDES / "m10-v7-results.html")
    assert src.index("'Fixed'") < src.index("} regression`") < src.index("'Fix merged'") < src.index("'Kept'")
    assert "test user" in src and "blind" not in src.lower() and "PR #${S.pr}" in src and "${esc(S.repo)}" in src
