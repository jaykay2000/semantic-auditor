"""Visual confirmation (opt-in): offline, against a mocked httpx.

Pins: the image request's shape (an image_url part holding a base64 PNG data URL, the quote in the text, the strict
schema, the seed); which issues qualify and the basis recorded (verifier vs evidence_linked; a failed one is never
sent); that every uncertain outcome is `unreadable` (a malformed reply, a refused image, a provider or model without
vision, no screenshot, a box off the image, a path outside the review's folder, a reply whose fields disagree); and
that `visual` is the only thing added: verdicts, verification, confidence, policy and outcome are untouched, the
review file itself is never rewritten, and the review command does not run it.
"""

import base64
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.models.router import Router  # noqa: E402
from semaudit.verify import visual as V  # noqa: E402

KEY = "test-baseten-key-not-real-0123456789"
TOML = '[roles.vision]\nprovider = "baseten"\nmodel = "meta-models/muse-spark-open-1026"\nreasoning_effort = "low"\n'
BOX = {"x": 600.0, "y": 400.0, "width": 60.0, "height": 20.0}


def _steps(status, evidence="pass"):
    return {"status": status, "reason": "", "steps": {"evidence_linked": {"result": evidence},
                                                       "reproduced": {"result": "not_run"}}}


def _issue(iid, status, evidence="pass", event="e1", quote=None):
    return {"id": iid, "rule": "U1", "delta": "pre_existing", "severity": {"level": "major"},
            "confidence": {"level": "medium"}, "verification": _steps(status, evidence),
            "occurrences": [{"persona": "ana", "events": [event], "quotes": [quote or "$43.19"]}]}


def _review(tmp_path, issues, capture=None):
    run = tmp_path / "run"
    (run / "captures").mkdir(parents=True)
    Image.new("RGB", (1280, 900), "white").save(run / "captures" / "page.png")
    cap = capture if capture is not None else {"kind": "web", "surface": "order", "screenshot": "captures/page.png",
                                               "bbox": BOX}
    review = {"release": {"base": "a", "head": "b"}, "issues": issues,
              "policy": {"row": 3, "recommendation": "hold"}, "outcome": {"status": "decided"},
              "personas": [{"id": "ana", "events": [{"id": "e1", "text": "$43.19", "capture": cap}]}]}
    p = run / "review.json"
    p.write_text(json.dumps(review))
    return p


class _Post:
    """httpx.post stand-in: records each call; answers with a reply dict (as JSON content), a raw string, or an
    (http status, body) pair."""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        a = self.answers.pop(0)
        if isinstance(a, tuple):
            return SimpleNamespace(status_code=a[0], text=a[1], json=lambda: {})
        content = a if isinstance(a, str) else json_dumps(a)
        return SimpleNamespace(status_code=200, json=lambda: {
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 400, "completion_tokens": 200}})


json_dumps = json.dumps
GOOD = {"readable": True, "visible": True, "reads": "$43.19", "same_as_text": True}


@pytest.fixture
def router(tmp_path, monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", KEY)
    root = tmp_path / "root"
    root.mkdir()
    (root / "semaudit.toml").write_text(TOML)
    return Router(root=root, max_usd=0.10)


def _run(tmp_path, router, monkeypatch, issues, *answers, capture=None):
    post = _Post(*answers)
    monkeypatch.setattr(httpx, "post", post)
    rp = _review(tmp_path, issues, capture)
    out = tmp_path / "out" / "review.visual.json"
    counts = V.visual_confirm(rp, out, router, crops_dir=tmp_path / "out" / "crops")
    return rp, json.loads(out.read_text()), counts, post


def test_the_image_request_shape(tmp_path, router, monkeypatch):
    rp, out, counts, post = _run(tmp_path, router, monkeypatch, [_issue("I1", "unverified")], GOOD)
    assert counts["confirmed"] == 1 and len(post.calls) == 1
    call = post.calls[0]
    assert call["url"] == "https://inference.baseten.co/v1/chat/completions"
    body = call["json"]
    assert body["model"] == "meta-models/muse-spark-open-1026" and body["seed"] == 1
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["response_format"]["json_schema"]["schema"] == V.SCHEMA
    (msg,) = body["messages"]
    text, image = msg["content"]
    assert text["type"] == "text" and '"$43.19"' in text["text"]
    assert image["type"] == "image_url"
    head, b64 = image["image_url"]["url"].split(",", 1)
    assert head == "data:image/png;base64"
    img = Image.open(io.BytesIO(base64.b64decode(b64)))
    assert img.format == "PNG" and max(img.size) <= V.MAX_SIDE
    assert KEY not in json.dumps(body)                       # the key travels only in the header
    assert call["headers"] == {"Authorization": f"Bearer {KEY}"}
    v = out["issues"][0]["visual"]
    assert v["result"] == "confirmed" and v["basis"] == "evidence_linked" and v["event"] == "e1"
    assert v["crop_box"] == [120, 250, 821, 571]
    assert (tmp_path / "out" / "crops" / v["crop"]).read_bytes() == base64.b64decode(b64)


def test_basis_names_what_qualified_the_issue_and_a_failed_issue_is_never_sent(tmp_path, router, monkeypatch):
    issues = [_issue("VER", "verified", quote="$48.59"), _issue("READER", "unverified"), _issue("FAILED", "failed"),
              _issue("NOEV", "unverified", evidence="fail")]
    _, out, counts, post = _run(tmp_path, router, monkeypatch, issues, {**GOOD, "reads": "$48.59"}, GOOD)
    by = {i["id"]: i for i in out["issues"]}
    assert by["VER"]["visual"]["basis"] == "verifier"
    assert by["READER"]["visual"]["basis"] == "evidence_linked"
    assert "visual" not in by["FAILED"] and "visual" not in by["NOEV"]
    assert counts == {"confirmed": 2, "contradicted": 0, "unreadable": 0, "not_eligible": 2}
    assert len(post.calls) == 2


def test_visual_is_the_only_change_and_never_upgrades_unverified(tmp_path, router, monkeypatch):
    issues = [_issue("I1", "unverified"), _issue("I2", "verified", quote="$48.59")]
    rp, out, _, _ = _run(tmp_path, router, monkeypatch, issues, GOOD,
                         {"readable": True, "visible": True, "reads": "$39.99", "same_as_text": False})
    before = json.loads(rp.read_text())
    stripped = json.loads(json.dumps(out))
    for i in stripped["issues"]:
        i.pop("visual")
    assert stripped == before                                 # nothing else moved: verdicts, status, policy, outcome
    assert out["issues"][0]["verification"]["status"] == "unverified"
    assert out["issues"][1]["visual"]["result"] == "contradicted"
    assert out["issues"][1]["verification"]["status"] == "verified"


def test_the_review_file_itself_is_never_rewritten(tmp_path, router, monkeypatch):
    rp = _review(tmp_path, [_issue("I1", "unverified")])
    raw = rp.read_bytes()
    with pytest.raises(ValueError, match="new file"):
        V.visual_confirm(rp, rp, router)
    assert rp.read_bytes() == raw


@pytest.mark.parametrize("reply", ["not json at all", '{"readable": true}', "[1, 2]"])
def test_a_malformed_reply_is_unreadable(tmp_path, router, monkeypatch, reply):
    _, out, counts, post = _run(tmp_path, router, monkeypatch, [_issue("I1", "unverified")], reply, reply)
    v = out["issues"][0]["visual"]
    assert v["result"] == "unreadable" and counts["unreadable"] == 1


def test_a_refused_image_is_unreadable_and_names_no_key(tmp_path, router, monkeypatch):
    refusal = (400, json.dumps({"error": f"image input is not supported for this model (key {KEY})"}))
    _, out, _, _ = _run(tmp_path, router, monkeypatch, [_issue("I1", "unverified")], refusal)
    v = out["issues"][0]["visual"]
    assert v["result"] == "unreadable" and "HTTP 400" in v["reason"]
    assert KEY not in json.dumps(out)


def test_a_model_without_vision_is_unreadable(tmp_path, router, monkeypatch):
    blind = {"readable": False, "visible": False, "reads": "", "same_as_text": False}
    _, out, _, _ = _run(tmp_path, router, monkeypatch, [_issue("I1", "unverified")], blind)
    assert out["issues"][0]["visual"]["result"] == "unreadable"


def test_the_same_crop_and_quote_is_answered_from_the_cache(tmp_path, router, monkeypatch):
    _, out, _, post = _run(tmp_path, router, monkeypatch, [_issue("I1", "unverified"), _issue("I2", "verified")], GOOD)
    assert len(post.calls) == 1 and [i["visual"]["cached"] for i in out["issues"]] == [False, True]


def test_no_vision_role_refuses_to_run(tmp_path, monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", KEY)
    rp = _review(tmp_path, [_issue("I1", "unverified")])
    with pytest.raises(Exception, match=r"roles\.vision"):
        V.visual_confirm(rp, tmp_path / "o.json", Router(root=tmp_path / "empty"))
    assert not (tmp_path / "o.json").exists()


def test_fields_that_disagree_fail_closed(tmp_path, router, monkeypatch):
    says_same_but_differs = {"readable": True, "visible": True, "reads": "$39.99", "same_as_text": True}
    says_differs_but_same = {"readable": True, "visible": True, "reads": "$43.19", "same_as_text": False}
    _, out, _, _ = _run(tmp_path, router, monkeypatch,
                        [_issue("I1", "unverified"), _issue("I2", "verified", quote="$43.19 ")],
                        says_same_but_differs, says_differs_but_same)
    assert [i["visual"]["result"] for i in out["issues"]] == ["unreadable", "unreadable"]


def test_not_visible_is_contradicted(tmp_path, router, monkeypatch):
    hidden = {"readable": True, "visible": False, "reads": "", "same_as_text": False}
    _, out, _, _ = _run(tmp_path, router, monkeypatch, [_issue("I1", "unverified")], hidden)
    assert out["issues"][0]["visual"]["result"] == "contradicted"


@pytest.mark.parametrize("capture", [
    {"kind": "web", "screenshot": None, "bbox": BOX},
    {"kind": "web", "screenshot": "captures/page.png", "bbox": None},
    {"kind": "web", "screenshot": "captures/page.png", "bbox": {"x": 1270.0, "y": 10.0, "width": 60.0, "height": 9.0}},
    {"kind": "web", "screenshot": "../outside.png", "bbox": BOX},
    {"kind": "web", "screenshot": "captures/missing.png", "bbox": BOX},
    {"kind": "email", "screenshot": None, "bbox": None},
])
def test_an_unusable_capture_is_unreadable_without_a_model_call(tmp_path, router, monkeypatch, capture):
    Image.new("RGB", (10, 10)).save(tmp_path / "outside.png")
    _, out, _, post = _run(tmp_path, router, monkeypatch, [_issue("I1", "unverified")], capture=capture)
    assert out["issues"][0]["visual"]["result"] == "unreadable" and post.calls == []


def test_the_review_command_does_not_run_it():
    for f in ("decide/run.py", "decide/pipeline.py", "report/review.py", "verify/steps.py", "verify/report.py"):
        assert "visual" not in (ROOT / "src" / "semaudit" / f).read_text(), f
