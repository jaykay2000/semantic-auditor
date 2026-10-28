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
# the innermost section root it sits in, in document order, and why the user could not read it if they could not.
#
# A block is a block-level element (display other than inline*, contents, none) whose text is not inside a
# block-level descendant that has text of its own; inline-level children (spans, pills, inline-block buttons)
# stay part of their block. A block that has block children AND text of its own yields that own text (inline
# wrappers are followed, so a block nested inside a span is never counted twice).
#
# What the user can read is measured, not assumed:
#   * clipped text: only the characters whose boxes lie inside the element's own clip box, every clipping ancestor
#     and the page are kept (text cut by an ellipsis, a line clamp or an overflow:hidden ancestor, or placed off the
#     page). A block with some characters cut is kept as the visible part and marked `truncated`; one with none
#     left is obscured 'clipped'.
#   * obscured: blurred (filter blur >= 1.5px on it or an ancestor), nearly transparent (opacity product < 0.15),
#     visibility hidden (its own computed value, so a visible child of a hidden parent counts as visible), text the
#     same colour as its background, not rendered ('collapsed': a closed section or <details>), a box of 2px or less
#     ('visually_hidden'), or covered at its centre by an unrelated element that is opaque or has a backdrop blur.
# Not seen: shadow DOM, iframes and clip-path (none of the captured products uses them). The page is scrolled to
# test cover; the screenshot is taken before this runs.
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
  const isSvg = (el) => el instanceof SVGElement;
  const blockish = (el) => { if (isSvg(el)) return false; const d = getComputedStyle(el).display; return d !== 'none' && !INLINE.has(d); };
  const hidden = (el) => getComputedStyle(el).display === 'none';
  const norm = (t) => (t || '').replace(/\s+/g, ' ').trim();
  const rendered = (el) => isSvg(el) ? el.textContent : el.innerText;
  // An element that is not rendered (collapsed section, closed <details>) can have empty innerText: use textContent
  const textOf = (el) => norm(rendered(el)) || norm(el.textContent);
  const ownText = (el) => {          // text nodes plus inline descendants, never a block descendant's text
    let t = '';
    for (const n of el.childNodes) {
      if (n.nodeType === 3) t += ' ' + n.textContent;
      else if (n.nodeType === 1 && !hidden(n) && !blockish(n)) t += ' ' + ownText(n);
    }
    return norm(t);
  };
  const roots = new Map();
  sels.forEach((sel, i) => { for (const r of document.querySelectorAll(sel)) roots.set(r, i); });
  const sectionOf = (el) => { for (let e = el; e; e = e.parentElement) if (roots.has(e)) return roots.get(e); return -1; };
  const blurPx = (f) => { const m = /blur\(\s*([\d.]+)px/.exec(f || ''); return m ? parseFloat(m[1]) : 0; };
  const rgba = (c) => { const m = /rgba?\(([^)]+)\)/.exec(c || ''); if (!m) return null; const v = m[1].split(',').map(x => parseFloat(x));
                        return {r: v[0], g: v[1], b: v[2], a: v.length > 3 ? v[3] : 1}; };
  const background = (el) => {      // the first non-transparent background colour behind el
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const c = rgba(getComputedStyle(e).backgroundColor);
      if (c && c.a > 0.95) return c;
      if (getComputedStyle(e).backgroundImage !== 'none') return null;   // an image: cannot tell
    }
    return {r: 255, g: 255, b: 255, a: 1};
  };
  // the box text must lie in to be seen: the element's own clip box, every clipping ancestor, and the page
  const clipBox = (el) => {
    let box = {l: 0, t: -window.scrollY, r: document.documentElement.scrollWidth - window.scrollX,
               b: document.documentElement.scrollHeight - window.scrollY};
    box.l -= window.scrollX;
    for (let e = el; e && e.nodeType === 1 && e !== document.body; e = e.parentElement) {
      const s = getComputedStyle(e);
      if (s.overflowX !== 'visible' || s.overflowY !== 'visible' || (s.webkitLineClamp && s.webkitLineClamp !== 'none')) {
        const r = e.getBoundingClientRect();
        if (s.overflowX !== 'visible') { box.l = Math.max(box.l, r.left); box.r = Math.min(box.r, r.right); }
        if (s.overflowY !== 'visible' || (s.webkitLineClamp && s.webkitLineClamp !== 'none')) { box.t = Math.max(box.t, r.top); box.b = Math.min(box.b, r.bottom); }
      }
    }
    return box;
  };
  const inside = (r, box) => r.width > 0 && r.left >= box.l - 1 && r.right <= box.r + 1 && r.top >= box.t - 1 && r.bottom <= box.b + 1;
  // the characters of el's own text that lie inside the clip box: {text, cut}
  const visiblePart = (el, own) => {
    const box = clipBox(el), r = el.getBoundingClientRect();
    if (inside(r, box) && !(el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1)) return {text: null, cut: false};
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let seen = '', kept = '', n;
    const range = document.createRange();
    while ((n = walker.nextNode())) {
      if (own) { let p = n.parentElement, blocked = false; for (; p && p !== el; p = p.parentElement) if (blockish(p)) { blocked = true; break; } if (blocked) continue; }
      for (let i = 0; i < n.textContent.length; i++) {
        const ch = n.textContent[i];
        seen += ch;
        if (/\s/.test(ch)) { kept += ch; continue; }
        range.setStart(n, i); range.setEnd(n, i + 1);
        const rr = [...range.getClientRects()];
        if (rr.some(q => inside(q, box))) kept += ch; else kept += '\u0000';
      }
    }
    const shown = norm(kept.replace(/\u0000+/g, ' … ').replace(/(\s*…\s*)+/g, ' … '));
    const cut = kept.includes('\u0000');
    return {text: cut ? shown : null, cut,
            none: cut && !/[^\s…]/.test(shown)};
  };
  const obscured = (el) => {
    let op = 1;
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const s = getComputedStyle(e);
      if (blurPx(s.filter) >= 1.5) return 'blur';
      op *= parseFloat(s.opacity || '1');
    }
    const own = getComputedStyle(el);
    if (own.visibility === 'hidden' || own.visibility === 'collapse') return 'hidden';
    if (op < 0.15) return 'transparent';
    const c = rgba(own.color);
    if (own.color === 'transparent' || (c && c.a === 0)) return 'transparent';
    if (el.getClientRects().length === 0 || !norm(rendered(el))) return 'collapsed';   // a closed section or <details>
    const b = el.getBoundingClientRect();
    if (b.width <= 2 || b.height <= 2) return 'visually_hidden';
    const bg = background(el);
    if (c && bg && own.textShadow === 'none' && Math.abs(c.r - bg.r) + Math.abs(c.g - bg.g) + Math.abs(c.b - bg.b) < 6)
      return 'same_colour';
    window.scrollTo(0, Math.max(0, b.top + window.scrollY - window.innerHeight / 2));
    const bb = el.getBoundingClientRect();
    const x = bb.left + Math.min(bb.width / 2, 8), y = bb.top + bb.height / 2;
    if (x < 0 || y < 0 || x >= window.innerWidth || y >= window.innerHeight) return null;
    for (const top of document.elementsFromPoint(x, y)) {
      if (top === el || el.contains(top) || top.contains(el)) break;
      const ts = getComputedStyle(top);
      if (blurPx(ts.backdropFilter || ts.webkitBackdropFilter) >= 1.5) return 'covered';
      const tb = rgba(ts.backgroundColor);
      if ((tb && tb.a > 0.95) || ts.backgroundImage !== 'none') return 'covered';
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
    const own = childBlockText ? ownText(el) : text;
    if (own) out.push({el, text: own, own: childBlockText});
    return true;
  };
  visit(document.body);
  out.sort((a, b) => a.el === b.el ? 0 : (a.el.compareDocumentPosition(b.el) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1));
  const sx = window.scrollX, sy = window.scrollY;
  const res = out.map(({el, text, own}) => {
    const b = el.getBoundingClientRect();
    const attrs = {};
    for (const a of el.attributes) attrs[a.name] = a.value;
    const box = {x: Math.round((b.x + window.scrollX) * 100) / 100, y: Math.round((b.y + window.scrollY) * 100) / 100,
                 width: Math.round(b.width * 100) / 100, height: Math.round(b.height * 100) / 100};
    let ob = obscured(el), truncated = false, full = null;
    if (!ob) {
      const v = visiblePart(el, own);
      if (v.none) ob = 'clipped';
      else if (v.cut) { truncated = true; full = text; text = v.text; }
    }
    return {css: css(el), text, attrs, own, section: sectionOf(el), bbox: box, obscured: ob, truncated, full_text: full};
  });
  window.scrollTo(sx, sy);
  return res;
}
"""


def find_blocks(page: Any, section_selectors: list[str]) -> list[dict[str, Any]]:
    """Visible text blocks under the given section roots, in document order, each with its innermost section index
    and an `obscured` reason (or None). Raises (Playwright Error) on an invalid selector."""
    return page.evaluate(BLOCKS_JS, section_selectors)
