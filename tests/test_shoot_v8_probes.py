"""The v8 screenshot script refuses a page in the wrong state (Codex round 3, R3-01).

shoot_v8.py used to write every shot and only print the probes it missed, so a stale or wrong page became a frame
and the script still exited 0. These drive it with a fake browser page: no Chromium, no network.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "demo" / "video-assets" / "slides-src" / "shoot_v8.py"


def _load(tmp_path):
    spec = importlib.util.spec_from_file_location("shoot_v8_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.OUT = tmp_path
    return mod


class FakePage:
    def __init__(self, body):
        self.body, self.closed = body, False

    def route(self, *a, **k):
        pass

    def goto(self, *a, **k):
        pass

    def wait_for_timeout(self, *a):
        pass

    def inner_text(self, sel):
        return self.body

    def screenshot(self, path, clip=None):
        Path(path).write_bytes(b"NEW")

    def close(self):
        self.closed = True


class FakeBrowser:
    def __init__(self, body):
        self.body, self.pages = body, []

    def new_page(self, **k):
        self.pages.append(FakePage(self.body))
        return self.pages[-1]

    def close(self):
        pass


def test_missing_probes_lists_every_absent_probe():
    mod = _load(Path("."))
    assert mod.missing_probes("Total $43.19 vs $39.99", ("43.19", "39.99")) == []
    assert mod.missing_probes("nothing here", ("43.19", "39.99")) == ["43.19", "39.99"]
    assert mod.missing_probes("only 43.19", ("43.19", "39.99")) == ["39.99"]


def test_wrong_page_leaves_the_previous_image_untouched(tmp_path):
    mod = _load(tmp_path)
    old = tmp_path / "spree-tax-line.png"
    old.write_bytes(b"OLD")
    b = FakeBrowser("a page with none of the required text")
    assert mod.shoot(b, "spree-tax-line", "file:///x", ("43.19", "39.99"), True) == ["43.19", "39.99"]
    assert old.read_bytes() == b"OLD"
    assert b.pages[0].closed


def test_a_missing_clip_probe_writes_no_crop(tmp_path):
    mod = _load(tmp_path)
    b = FakeBrowser("Merged but the other text is gone")
    assert mod.shoot(b, "gh-pr-289", "https://x", ("Merged", "Fixes #283"), False,
                     {"gh-pr-title": (0, 0, 10, 10)}) == ["Fixes #283"]
    assert not (tmp_path / "gh-pr-title.png").exists()


def test_right_page_is_written(tmp_path):
    mod = _load(tmp_path)
    assert mod.shoot(FakeBrowser("Hold"), "brightdesk-hold", "file:///x", ("Hold",), True) == []
    assert (tmp_path / "brightdesk-hold.png").read_bytes() == b"NEW"


def test_main_exits_nonzero_when_any_page_is_wrong(tmp_path, monkeypatch):
    mod = _load(tmp_path)

    class PW:
        chromium = types.SimpleNamespace(launch=lambda: FakeBrowser("wrong page"))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    fake = types.ModuleType("playwright.sync_api")
    fake.sync_playwright = PW
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake)
    monkeypatch.setattr(sys, "argv", ["shoot_v8.py"])
    with pytest.raises(SystemExit) as e:
        mod.main()
    assert e.value.code not in (0, None)
    assert not list(tmp_path.glob("*.png"))
