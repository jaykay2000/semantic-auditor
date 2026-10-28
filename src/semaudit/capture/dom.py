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


# For a product that marks none of its text: every visible text block under each section root, with the index of
# the innermost section root it sits in, and why the user could not read it if they could not.
#
# A block is a block-level element (display other than inline*, contents, none) whose text is not inside a
# block-level descendant that has text of its own; inline-level children (spans, pills, inline-block buttons)
# stay part of their block. A block that has block children AND text of its own also yields that own text.
# Obscured: the element or an ancestor is blurred (filter: blur >= 1.5px), nearly transparent (opacity product
# < 0.15), visibility: hidden, its text colour is fully transparent, it is not rendered (inside a collapsed section
# or a closed <details>: 'collapsed'), it is visually hidden (<= 2px box), or the
# point at its centre is covered by another element with a backdrop blur. The page is scrolled to test cover;
# the screenshot is taken before this runs.
BLOCKS_JS = r"""
(sels) => {
  const css = (el) => {
    const part = (e) => {
      if (e.id && document.querySelectorAll('#' + CSS.escape(e.id)).length === 1) return '#' + CSS.escape(e.id);
      let n = 1, s = e.previousElementSibling;
      while (s) { if (s.tagName === e.tagName) n++; s = s.previousElementSibling; }
      return e.tagName.toLowerCase() + ':nth-of-type(' + n + ')';
    };
    const chain = [];
    for (let e = el; e && e.nodeType === 1 && e !== document.documentElement; e = e.parentElement) chain.unshift(part(e));
    for (let k = 1; k <= chain.length; k++) {
      const c = chain.slice(chain.length - k).join(' > ');
      const m = document.querySelectorAll(c);
      if (m.length === 1 && m[0] === el) return c;
    }
    return chain.join(' > ');
  };
  const INLINE = new Set(['inline', 'inline-block', 'inline-flex', 'inline-grid', 'inline-table', 'contents', 'ruby']);
  const blockish = (el) => { const d = getComputedStyle(el).display; return d !== 'none' && !INLINE.has(d); };
  const norm = (t) => (t || '').replace(/\s+/g, ' ').trim();
  // An element that is not rendered (collapsed section, closed <details>) can have empty innerText: use textContent
  const textOf = (el) => norm(el.innerText) || norm(el.textContent);
  const roots = new Map();
  sels.forEach((sel, i) => { for (const r of document.querySelectorAll(sel)) roots.set(r, i); });
  const sectionOf = (el) => { for (let e = el; e; e = e.parentElement) if (roots.has(e)) return roots.get(e); return -1; };
  const blurPx = (f) => { const m = /blur\(\s*([\d.]+)px/.exec(f || ''); return m ? parseFloat(m[1]) : 0; };
  const obscured = (el) => {
    let op = 1;
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const s = getComputedStyle(e);
      if (blurPx(s.filter) >= 1.5) return 'blur';
      if (s.visibility === 'hidden' || s.visibility === 'collapse') return 'hidden';
      op *= parseFloat(s.opacity || '1');
    }
    if (op < 0.15) return 'transparent';
    const c = getComputedStyle(el).color;
    if (c === 'transparent' || /rgba\([^)]*,\s*0\)$/.test(c)) return 'transparent';
    if (el.getClientRects().length === 0 || !norm(el.innerText)) return 'collapsed';   // a closed section or <details>
    const b = el.getBoundingClientRect();
    if (b.width <= 2 || b.height <= 2) return 'visually_hidden';
    window.scrollTo(0, Math.max(0, b.top + window.scrollY - window.innerHeight / 2));
    const bb = el.getBoundingClientRect();
    const x = bb.left + Math.min(bb.width / 2, 8), y = bb.top + bb.height / 2;
    if (x < 0 || y < 0 || x >= window.innerWidth || y >= window.innerHeight) return null;
    for (const top of document.elementsFromPoint(x, y)) {
      if (top === el || el.contains(top) || top.contains(el)) break;
      if (blurPx(getComputedStyle(top).backdropFilter || getComputedStyle(top).webkitBackdropFilter) >= 1.5) return 'covered';
    }
    return null;
  };
  const out = [];
  const visit = (el) => {           // returns true if el's subtree has a block-level element with text
    let childBlockText = false;
    for (const ch of el.children) if (visit(ch)) childBlockText = true;
    if (!blockish(el) || sectionOf(el) < 0) return childBlockText || (blockish(el) && textOf(el) !== '');
    const text = textOf(el);
    if (!text) return childBlockText;
    let own = text;
    if (childBlockText) {
      own = '';
      for (const n of el.childNodes) {
        if (n.nodeType === 3) own += ' ' + n.textContent;
        else if (n.nodeType === 1 && !blockish(n) && getComputedStyle(n).display !== 'none') own += ' ' + n.innerText;
      }
      own = norm(own);
    }
    if (own) out.push({el, text: own, own: childBlockText});
    return true;
  };
  visit(document.body);
  const sx = window.scrollX, sy = window.scrollY;
  const res = out.map(({el, text, own}) => {
    const b = el.getBoundingClientRect();
    const attrs = {};
    for (const a of el.attributes) attrs[a.name] = a.value;
    const box = {x: Math.round((b.x + window.scrollX) * 100) / 100, y: Math.round((b.y + window.scrollY) * 100) / 100,
                 width: Math.round(b.width * 100) / 100, height: Math.round(b.height * 100) / 100};
    return {css: css(el), text, attrs, own, section: sectionOf(el), bbox: box, obscured: obscured(el)};
  });
  window.scrollTo(sx, sy);
  return res;
}
"""


def find_blocks(page: Any, section_selectors: list[str]) -> list[dict[str, Any]]:
    """Visible text blocks under the given section roots, in document order, each with its innermost section index
    and an `obscured` reason (or None). Raises (Playwright Error) on an invalid selector."""
    return page.evaluate(BLOCKS_JS, section_selectors)
