"""`semaudit verify-report` on the committed Northbound sample review (docs/try-it/northbound-2.3-2.4): its pinned
inputs (episodes, the cited capture files, the recorded model replies) are committed beside it, so a fresh clone
can check it offline. A missing input means "cannot verify" (exit 2), never "not consistent"."""

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.models.router import Router  # noqa: E402
from semaudit.verify.report import CannotVerify, verify_report  # noqa: E402

SAMPLE = ROOT / "docs" / "try-it" / "northbound-2.3-2.4"
REVIEW = SAMPLE / "review-2.3-2.4.json"


@pytest.fixture
def copy(tmp_path, monkeypatch):
    """The sample folder copied to tmp, run from a folder laid out like a fresh clone: `examples/` (the contract
    path is repository-relative) and nothing else, so no local run folder, model cache or ledger of this checkout
    is used or written."""
    dst = tmp_path / "sample"
    shutil.copytree(SAMPLE, dst)
    work = tmp_path / "clone"
    work.mkdir()
    (work / "examples").symlink_to(ROOT / "examples")
    monkeypatch.chdir(work)

    def refuse(*a, **k):
        raise AssertionError("verify-report tried to call a model")
    monkeypatch.setattr(Router, "_fetch_anthropic", refuse)
    monkeypatch.setattr("httpx.Client.post", refuse, raising=False)
    return dst


def run(folder: Path, tmp_path: Path):
    return verify_report(folder / REVIEW.name, root=tmp_path)


def test_a_missing_episode_is_cannot_verify(copy, tmp_path):
    next((copy / "episodes" / "2.4").glob("*.json")).unlink()
    with pytest.raises(CannotVerify, match=r"^1 pinned input\(s\) missing: episode episodes/2.4/"):
        run(copy, tmp_path)


def test_a_missing_capture_file_is_cannot_verify(copy, tmp_path):
    next(copy.joinpath("captures").rglob("*.dom.html")).unlink()
    with pytest.raises(CannotVerify, match=r"pinned input\(s\) missing: .*artifact dom missing"):
        run(copy, tmp_path)


def test_a_missing_model_reply_is_cannot_verify(copy, tmp_path):
    next((copy / "model-cache").glob("*.json")).unlink()
    with pytest.raises(CannotVerify, match=r"^1 pinned input\(s\) missing: recorded model reply"):
        run(copy, tmp_path)


def test_cli_exit_2_when_inputs_are_missing(copy, tmp_path):
    from typer.testing import CliRunner

    from semaudit.cli import app
    shutil.rmtree(copy / "model-cache")
    r = CliRunner().invoke(app, ["verify-report", str(copy / REVIEW.name)])
    assert r.exit_code == 2, r.output
    assert "cannot verify: 1 pinned input(s) missing" in r.output


def test_the_committed_inputs_are_all_there(copy, tmp_path):
    """Every pinned input is present: the run gets past the missing-input checks (its verdict is asserted
    separately, against the review that is committed)."""
    try:
        run(copy, tmp_path)
    except CannotVerify as e:
        pytest.fail(f"cannot verify: {e}")
