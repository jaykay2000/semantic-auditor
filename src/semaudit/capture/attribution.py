"""Contract-level attribution for products that do not mark their own text (method `contract_map`).

The surface's `sections` say which feature owns which part of a page or a text. A message key is then a
text-template signature: the block's text with every run of digits replaced by '#', hashed, plus the section and
an occurrence index within the capture. The same block with a different number keeps its key (so a base and a
head release pair it as `changed`); two different blocks never collide. Nothing here reads meaning.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any

from ..contract.schema import SectionMap, Surface

DEFAULT_HEADING = r"^#{1,6}\s+(.*\S)\s*$"


def signature(text: str) -> str:
    t = re.sub(r"\d[\d,.]*", "#", re.sub(r"\s+", " ", text).strip().lower())
    return hashlib.sha1(t.encode("utf-8")).hexdigest()[:10]


class Keys:
    """Message keys for one capture: `<feature>.<signature>` plus `#n` from the second occurrence on."""

    def __init__(self) -> None:
        self.seen: Counter = Counter()

    def __call__(self, feature: str, text: str) -> str:
        base = f"{feature}.{signature(text)}"
        self.seen[base] += 1
        return base if self.seen[base] == 1 else f"{base}#{self.seen[base]}"


def mapped(section: SectionMap, key: str, index: int) -> dict[str, Any]:
    return {"method": "contract_map", "feature": section.feature, "component": section.component,
            "key": key, "section": index}


def text_sections(surface: Surface, text: str) -> list[dict[str, Any]]:
    """Split a captured text at its heading lines. Each headed section (heading line included) is one block:
    {heading, span, text, section} where `section` is the index of the first `sections` entry whose regex matches
    the heading, or -1. Text before the first heading is a block with heading None. Empty blocks are dropped."""
    heading = re.compile(surface.heading or DEFAULT_HEADING, re.MULTILINE)
    cuts = [(m.start(), m.group(1)) for m in heading.finditer(text)]
    starts = ([(0, None)] if not cuts or cuts[0][0] > 0 else []) + cuts
    out = []
    for i, (start, head) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        body = text[start:end].strip()
        if not body:
            continue
        lead = len(text[start:end]) - len(text[start:end].lstrip())
        idx = next((j for j, s in enumerate(surface.sections) if head is not None and re.search(s.match, head, re.I)), -1)
        out.append({"heading": head, "span": [start + lead, start + lead + len(body)], "text": body, "section": idx})
    return out
