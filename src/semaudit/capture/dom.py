"""Structural element finding on a rendered web page. Locates marked text; extracts no meaning."""

from __future__ import annotations

from typing import Any

# One evaluate() call: for every element matching the contract surface's message_selector, its text, every
# attribute, its page-coordinate box and a CSS selector that is unique in this DOM (shortest unique suffix of a
# nth-of-type chain, or an #id).
ELEMENTS_JS = r"""
(sel) => {
  const part = (el) => {
    if (el.id && document.querySelectorAll('#' + CSS.escape(el.id)).length === 1) return '#' + CSS.escape(el.id);
    const tag = el.tagName.toLowerCase();
    let n = 1, s = el.previousElementSibling;
    while (s) { if (s.tagName === el.tagName) n++; s = s.previousElementSibling; }
    return tag + ':nth-of-type(' + n + ')';
  };
  const unique = (el) => {
    const chain = [];
    for (let e = el; e && e.nodeType === 1 && e !== document.documentElement; e = e.parentElement) chain.unshift(part(e));
    for (let k = 1; k <= chain.length; k++) {
      const css = chain.slice(chain.length - k).join(' > ');
      const m = document.querySelectorAll(css);
      if (m.length === 1 && m[0] === el) return css;
    }
    return chain.join(' > ');
  };
  const r2 = (v) => Math.round(v * 100) / 100;
  return Array.from(document.querySelectorAll(sel)).map((el) => {
    const b = el.getBoundingClientRect();
    const attrs = {};
    for (const a of el.attributes) attrs[a.name] = a.value;
    const text = (el.innerText !== undefined ? el.innerText : el.textContent).trim();
    return {css: unique(el), text, attrs,
            bbox: {x: r2(b.x + window.scrollX), y: r2(b.y + window.scrollY), width: r2(b.width), height: r2(b.height)}};
  });
}
"""


def find_elements(page: Any, selector: str) -> list[dict[str, Any]]:
    """Raises (Playwright Error) if the selector is invalid; the caller records the capture as not_measured."""
    return page.evaluate(ELEMENTS_JS, selector)
