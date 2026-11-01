"""The release page's <title> is built from the app name and release ids in review.json: it is HTML-escaped
(audit P1-03), so a name carrying markup is shown as text, never parsed as HTML."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.report.page import render  # noqa: E402


def _title(tmp_path, name, base="a", head="b"):
    review = {"app": {"name": name}, "release": {"base": base, "head": head}, "issues": [], "personas": []}
    p = tmp_path / "review.json"
    p.write_text(json.dumps(review))
    return re.search(r"<title>(.*?)</title>", render(p), re.S).group(1)


def test_markup_in_the_app_name_is_escaped(tmp_path):
    t = _title(tmp_path, '<img src=x onerror="alert(1)">Shop', base="1<2", head="&")
    assert "<img" not in t and "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;Shop" in t
    assert "1&lt;2" in t and t.endswith("&amp;")


def test_a_plain_title_is_unchanged(tmp_path):
    assert _title(tmp_path, "Spree", "v6.0.0.beta2", "v6.0.0.beta3") == "Release review · Spree v6.0.0.beta2 → v6.0.0.beta3"
