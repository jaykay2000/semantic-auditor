"""`sections[].each`: every element a section selector matches is its own section for a short block's context.

Found on Medusa (2026-11-04): a totals panel is label/value rows ("Taxes" | "€2.50"). With the whole page one
section, the bare "€2.50" was read with the neighbouring rows' figures; with every row matched by ONE selector,
the context still crossed rows, because the boundary was the selector, not the matched element. Default off, so
every existing contract builds exactly the same context.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from semaudit.contract.schema import SectionMap
from semaudit.story.build import around


def _cap(rows, each):
    els = []
    for root, (label, value) in enumerate(rows):
        for text in (label, value):
            att = {"section": 0, **({"root": root} if each else {})}
            els.append(SimpleNamespace(text=text, obscured=False, attribution=att))
    return SimpleNamespace(kind="web", elements=els)


ROWS = [("Shipping", "€10.00"), ("Taxes", "€2.50"), ("Total", "€22.50")]


def test_with_each_a_figure_is_read_with_its_own_row_only():
    assert around(_cap(ROWS, each=True), 3) == "Taxes | [this] | "


def test_without_each_the_context_is_unchanged():
    assert around(_cap(ROWS, each=False), 3) == "Taxes | [this] | Total"


def test_each_defaults_off():
    assert SectionMap(match="div", feature="core").each is False
