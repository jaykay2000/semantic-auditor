"""`semaudit demo`: rebuilds the committed review page and saved-check cards from committed inputs, byte for byte,
with no model key, every model call made to fail, and no network connection allowed."""

import json
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from test_demo_assets_clean import LOCAL_PATH  # noqa: E402

from semaudit import demo  # noqa: E402
from semaudit.models.router import Router  # noqa: E402

KEYS = ("META_MODEL_API_KEY", "BASETEN_API_KEY", "ANTHROPIC_API_KEY", "MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET")


@pytest.fixture
def no_models_no_network(monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)

    def refuse(*a, **k):
        raise AssertionError("the demo tried to call a model or open a connection")
    monkeypatch.setattr(Router, "__init__", refuse)
    monkeypatch.setattr(Router, "complete", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def test_demo_rebuilds_the_committed_files(tmp_path, no_models_no_network):
    lines = []
    assert demo.run(tmp_path / "out", echo=lines.append) == 0
    text = "\n".join(lines)
    assert text.count("same bytes as the committed") == 2 and "DIFFERS" not in text
    page = tmp_path / "out" / "release-review-northbound-2.3-2.4" / "index.html"
    assert page.read_bytes() == (ROOT / "docs/sample-review/index.html").read_bytes()
    assert (page.parent / "captures").is_dir() and not (page.parent / "MISSING.txt").exists()
    assert not (tmp_path / "out" / "stage").exists()


def test_demo_cli_exit_code(tmp_path, no_models_no_network):
    from typer.testing import CliRunner

    from semaudit.cli import app
    r = CliRunner().invoke(app, ["demo", "--out", str(tmp_path / "out")])
    assert r.exit_code == 0, r.output
    assert "no model was called" in r.output


def test_demo_says_when_a_rebuild_differs(tmp_path, no_models_no_network):
    m = json.loads(demo.MANIFEST.read_text())
    m["cards"][0]["label"] = "a different label"
    bad = tmp_path / "demo.json"
    bad.write_text(json.dumps(m))
    lines = []
    assert demo.run(tmp_path / "out", manifest=bad, echo=lines.append, repo=ROOT) == 1
    assert "DIFFERS from the committed" in "\n".join(lines)


def test_demo_missing_manifest_is_an_error(tmp_path):
    with pytest.raises(demo.DemoError):
        demo.run(tmp_path / "out", manifest=tmp_path / "nope.json")


def test_committed_inputs_carry_no_local_path():
    for f in (ROOT / "docs" / "try-it").rglob("*"):
        if f.is_file() and f.suffix != ".png":
            assert not LOCAL_PATH.search(f.read_text(encoding="utf-8")), f
