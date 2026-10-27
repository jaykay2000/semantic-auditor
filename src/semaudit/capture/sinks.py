"""Read the file sinks (email, push) and PDF documents into elements. Structural only.

A sink holds one JSON document per message: {message_id, sent_at, headers, text, ...}. The text is the marked text; every other field and header is kept in `attrs`.
"""

from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..story.episode import BBox, Element


def read_message(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def message_attrs(doc: dict[str, Any]) -> dict[str, str]:
    attrs = {k: str(v) for k, v in (doc.get("headers") or {}).items()}
    for k, v in doc.items():
        if k not in ("headers", "text", "html") and isinstance(v, (str, int, float)):
            attrs[k] = str(v)
    return attrs


def sink_element(kind: str, doc: dict[str, Any], stem: str) -> Element:
    text = str(doc.get("text", ""))
    mid = str(doc.get("message_id", stem))
    if kind == "email":
        loc = {"kind": "message_id", "message_id": mid, "part": "text", "span": [0, len(text)]}
    else:
        loc = {"kind": "notification_id", "notification_id": mid, "field": "text", "span": [0, len(text)]}
    return Element(locator=loc, text=text, attrs=message_attrs(doc))


def sent_at(doc: dict[str, Any]) -> datetime | None:
    try:
        return datetime.fromisoformat(str(doc["sent_at"]))
    except (KeyError, ValueError):
        return None


def pdf_elements(data: bytes) -> tuple[list[Element], dict[str, Any]]:
    """One element per text line of the text layer: page number, span into that page's text, box."""
    import pdfplumber

    els: list[Element] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        meta = {k: str(v) for k, v in (pdf.metadata or {}).items() if k in ("Keywords", "Subject", "Title")}
        meta["pages"] = len(pdf.pages)
        for n, page in enumerate(pdf.pages, 1):
            pos = 0
            for line in page.extract_text_lines(return_chars=False):
                text = line["text"]
                els.append(Element(
                    locator={"kind": "pdf_page", "page": n, "span": [pos, pos + len(text)]}, text=text, attrs={},
                    bbox=BBox(x=round(float(line["x0"]), 2), y=round(float(line["top"]), 2),
                              width=round(float(line["x1"] - line["x0"]), 2),
                              height=round(float(line["bottom"] - line["top"]), 2))))
                pos += len(text) + 1
    return els, meta
