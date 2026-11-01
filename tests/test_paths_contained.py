"""Paths named inside stored files stay inside their folders (audit P0-01, P1-01).

review.json names capture files that `semaudit report` copies; imported checks and approvals name check ids that
become checks/<id>.yaml. Each test plants a hostile path (traversal, absolute, symlink) and asserts nothing outside
the intended folder is read or written.
"""

import json
import os
import sys
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.contract.approve import approve_check  # noqa: E402
from semaudit.imported.record import ImportedCheck, check_path, valid_check_id  # noqa: E402
from semaudit.imported.saved import saved_checks  # noqa: E402
from semaudit.report.page import build  # noqa: E402


def _review(tmp: Path, shots: list[str]) -> Path:
    run = tmp / "run"
    run.mkdir()
    (run / "captures").mkdir()
    (run / "captures" / "ok.png").write_bytes(b"png")
    review = {"app": {"name": "T"}, "release": {"base": "a", "head": "b"}, "issues": [],
              "personas": [{"id": "p", "events": [{"capture": {"screenshot": s}} for s in shots]}]}
    (run / "review.json").write_text(json.dumps(review))
    return run / "review.json"


@pytest.fixture
def secret(tmp_path):
    p = tmp_path / "secret.txt"
    p.write_text("private")
    return p


def test_report_copies_a_plain_capture(tmp_path):
    out = tmp_path / "out"
    build(_review(tmp_path, ["captures/ok.png"]), out)
    assert (out / "captures" / "ok.png").read_bytes() == b"png"
    assert not (out / "MISSING.txt").exists()


def test_report_refuses_traversal_and_writes_nothing_outside(tmp_path, secret):
    out = tmp_path / "deep" / "out"
    build(_review(tmp_path, ["../secret.txt", "captures/../../secret.txt"]), out)
    copied = [p for p in tmp_path.rglob("secret.txt") if p != secret]
    assert copied == []
    assert "refused" in (out / "MISSING.txt").read_text()


def test_report_refuses_an_absolute_path(tmp_path, secret):
    out = tmp_path / "out"
    build(_review(tmp_path, [str(secret)]), out)
    assert [p for p in tmp_path.rglob("secret.txt") if p != secret] == []
    assert "refused" in (out / "MISSING.txt").read_text()


def test_report_refuses_a_symlink_that_leaves_the_review_folder(tmp_path, secret):
    rp = _review(tmp_path, ["captures/link.png"])
    os.symlink(secret, rp.parent / "captures" / "link.png")
    out = tmp_path / "out"
    build(rp, out)
    assert not (out / "captures" / "link.png").exists()
    assert "refused" in (out / "MISSING.txt").read_text()


@pytest.mark.parametrize("bad", ["../x", "a/b", "/etc/passwd", "..", ".hidden", "", "a\\b", "x" * 65, "a..b"])
def test_check_ids_have_one_canonical_shape(bad):
    with pytest.raises(ValueError):
        valid_check_id(bad)


@pytest.mark.parametrize("good", ["C1-04", "C1-04-v1", "F73-D3", "X1_00", "c.v2"])
def test_existing_id_shapes_stay_valid(good):
    assert valid_check_id(good) == good


def _check(cid: str) -> dict:
    return {"id": cid, "source": {"ref": "T#00"}, "conversion": {"status": "converted"}}


def test_a_record_with_a_traversing_id_does_not_load():
    with pytest.raises(ValidationError):
        ImportedCheck(**_check("../evil"))


def test_check_path_refuses_traversal_and_symlinks(tmp_path, secret):
    checks = tmp_path / "checks"
    checks.mkdir()
    with pytest.raises(ValueError):
        check_path(checks, "../secret")
    os.symlink(secret, checks / "C1-01.yaml")
    with pytest.raises(ValueError):
        check_path(checks, "C1-01")
    with pytest.raises(ValueError):
        ImportedCheck.load(tmp_path, "C1-01")


def test_an_approval_key_cannot_reach_outside_checks(tmp_path):
    (tmp_path / "checks").mkdir()
    outside = tmp_path / "evil.yaml"
    outside.write_text(yaml.safe_dump(_check("evil")))
    (tmp_path / "approvals.yaml").write_text(yaml.safe_dump({"check:../evil": {"hash": "x", "by": "o"}}))
    ok, refused = saved_checks(tmp_path)
    assert ok == []
    assert len(refused) == 1 and "not a valid check id" in refused[0]


def test_writing_or_approving_a_bad_id_is_refused(tmp_path):
    c = ImportedCheck(**_check("C1-01"))
    object.__setattr__(c, "id", "../escape")
    with pytest.raises(ValueError):
        c.write(tmp_path / "checks")
    assert not (tmp_path / "escape.yaml").exists()
    with pytest.raises(ValueError):
        approve_check(tmp_path, "../escape", "abc", by="owner")
    assert not (tmp_path / "approvals.yaml").exists()
