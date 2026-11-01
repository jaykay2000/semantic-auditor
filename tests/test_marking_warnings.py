"""Marked messages that would be lost silently are reported (new-user test findings 1 and 2).

1. A marked element whose rendered text is not in the stored page (nested tags) can never be quoted as evidence;
   the warning uses the evidence check itself, so it fires exactly when evidence would fail.
2. An email or push with no X-Message-Key header is not read as a message; it is counted.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semaudit.capture import marking  # noqa: E402
from semaudit.verify.evidence import _quoted_in  # noqa: E402

NESTED = "Pro\n\nPro costs $12 per month."


def el(text, key="pricing.pro", **attrs):
    return SimpleNamespace(text=text, attrs={**({"data-message-key": key} if key else {}), **attrs})


def web(tmp_path, dom, *elements, cid="c01"):
    (tmp_path / f"{cid}.dom.html").write_text(dom)
    return SimpleNamespace(id=cid, kind="web", surface="pricing", url="/pricing", status="captured",
                           files={"dom": f"{cid}.dom.html"}, elements=list(elements))


def sink(tmp_path, doc, cid="c02", kind="email"):
    (tmp_path / f"{cid}.raw.json").write_text(json.dumps(doc))
    headers = doc.get("headers", {})
    return SimpleNamespace(id=cid, kind=kind, surface="inbox", url=None, status="captured",
                           files={"raw": f"{cid}.raw.json"}, elements=[el(doc["text"], key=None, **headers)])


def episode(*caps):
    return SimpleNamespace(id="1.0/ana/S", captures=lambda: list(caps))


def test_nested_tags_are_reported_with_the_key_and_the_page(tmp_path):
    cap = web(tmp_path, '<div data-message-key="pricing.pro"><h2>Pro</h2><p>Pro costs $12 per month.</p></div>',
              el(NESTED))
    (w,) = marking.unquotable(episode(cap), tmp_path)
    assert "'pricing.pro'" in w and "/pricing" in w and "not in the stored dom" in w
    assert not _quoted_in(NESTED, tmp_path / "c01.dom.html")              # evidence would refuse it too


def test_an_inline_tag_inside_the_marked_element_is_reported_too(tmp_path):
    cap = web(tmp_path, '<p data-message-key="k">Pay <b>$12</b> today</p>', el("Pay $12 today", key="k"))
    assert len(marking.unquotable(episode(cap), tmp_path)) == 1


def test_flat_text_and_entities_are_fine(tmp_path):
    cap = web(tmp_path, '<p data-message-key="a">Pro costs $12 per month.</p><p data-message-key="b">Tom &amp; Ana</p>',
              el("Pro costs $12 per month.", key="a"), el("Tom & Ana", key="b"))
    assert marking.unquotable(episode(cap), tmp_path) == []


def test_unmarked_elements_and_unmeasured_captures_are_not_checked(tmp_path):
    cap = web(tmp_path, "<div><h2>Pro</h2></div>", el(NESTED, key=None))
    bad = web(tmp_path, "<div></div>", el(NESTED), cid="c03")
    bad.status = "not_measured"
    assert marking.unquotable(episode(cap, bad), tmp_path) == []


def test_sink_messages_without_a_key_are_counted(tmp_path):
    keyed = sink(tmp_path, {"text": "Welcome", "headers": {"X-Message-Key": "welcome"}}, cid="c04")
    bare = sink(tmp_path, {"text": "Receipt"}, cid="c05")
    push = sink(tmp_path, {"text": "Ping", "headers": {"X-Feature": "f"}}, cid="c06", kind="push")
    ep = episode(keyed, bare, push)
    assert marking.keyless(ep) == {("email", "inbox"): 1, ("push", "inbox"): 1}
    lines = marking.warnings([ep], tmp_path)
    assert lines == ["1.0/ana/S: 1 email message on 'inbox' with no X-Message-Key header, not read as messages "
                     "(see docs/10-add-your-app.md, 'Email and push sinks')",
                     "1.0/ana/S: 1 push message on 'inbox' with no X-Message-Key header, not read as messages "
                     "(see docs/10-add-your-app.md, 'Email and push sinks')"]


def test_the_doc_sections_the_warnings_name_exist():
    doc = (ROOT / "docs" / "10-add-your-app.md").read_text()
    assert "### Marking messages" in doc and "### Email and push sinks" in doc
