"""Shared test setup: tests that need a real browser skip, with the reason, when Playwright's Chromium is missing.

A test needs a browser when it is marked `browser` or uses one of the browser fixtures below. Whether Chromium is
usable is checked once, by launching it. Install it with `python -m playwright install chromium` (README, "Run the
tests").
"""

from functools import lru_cache

import pytest

BROWSER_FIXTURES = {"browser", "runner", "run", "blocks", "blocks2"}
INSTALL = "python -m playwright install chromium"


@lru_cache(maxsize=1)
def chromium_missing() -> str | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "needs Playwright (pip install -e '.[test]')"
    try:
        with sync_playwright() as p:
            p.chromium.launch().close()
    except Exception as e:  # any launch failure means no usable browser; the reason is shown
        first = (str(e).strip().splitlines() or ["launch failed"])[0]
        return f"needs Playwright's Chromium, which did not launch ({first[:120]}); run: {INSTALL}"
    return None


def pytest_configure(config):
    config.addinivalue_line("markers", "browser: needs Playwright's Chromium; skipped with the reason when missing")


def pytest_collection_modifyitems(config, items):
    wanted = [i for i in items if i.get_closest_marker("browser") or BROWSER_FIXTURES & set(i.fixturenames)]
    if wanted and (reason := chromium_missing()):
        for item in wanted:
            item.add_marker(pytest.mark.skip(reason=reason))
