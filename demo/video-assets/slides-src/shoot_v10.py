"""Capture the real check card V4 shows, section by section, and the sample review's verdict for Maya (V3), at 2x,
into slides-src/img/v10/.

    python3 slides-src/shoot_v10.py

The card is the owner's run ic-owner-rec-1 (docs/evidence/imported-checks/acceptance/cards-run-owner-2026-11-01.html),
the run whose approval is the owner's own (approvals.yaml: C1-04 at f0cb1dc9ee14fc8f by Jayant Kumar). Run 3c's card
shows the same check but records its approval as the acceptance run's ("owner has not reviewed this digest"), so it is
not used for a frame that shows the owner's stamp. Opened from disk with the network blocked. Each crop is one of the
C1-04 card's own sections (a) report, (b) steps + rule, (c) the two releases, (d) the memory; every probe text must be
inside its section or nothing is written and the script exits 1.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / 'img' / 'v10'
CARD = HERE.parents[2] / 'docs' / 'evidence' / 'imported-checks' / 'acceptance' / 'cards-run-owner-2026-11-01.html'
SECTIONS = {   # name -> (heading prefix of the section, probe texts that must be inside it)
    'card-a': ("(a) The agent", ('Shown:', 'Should be:', 'Reproduce:', '179.38 ≠ 194.38')),
    'card-b': ("(b) The converted journey", ('open_home', 'read_order_email', 'Rule U3', 'Summary does not add up')),
    'card-c': ("(c) Four separate statuses", ('current (base)', 'candidate (head)', 'fail', 'pass')),
    'card-d': ("(d) Base vs head", ('fix_confirmed', 'loaded from storage', 'approvals.yaml')),
}
SAMPLE = HERE.parents[2] / 'docs' / 'sample-review' / 'index.html'
VERDICT_PROBES = ('Unexplained tradeoff between Fare Lock and Price Watch', 'Why:', 'nothing explained it',
                  'Price Watch', 'Fare Lock')
# the sample review's selected issue, from its title down to the two messages (it stops above "How it changed")
VERDICT_JS = """() => {
  const box = document.querySelector('section.box.detail'), r = box.getBoundingClientRect();
  const stop = [...box.querySelectorAll('*')].find(e => /^how it changed between releases$/i.test(e.innerText.trim()));
  const end = stop ? stop.getBoundingClientRect().top - 14 : r.bottom;
  const range = document.createRange(); range.selectNodeContents(box);
  const text = box.innerText.split(/how it changed between releases/i)[0];
  return {x: r.left, y: r.top + scrollY, w: r.width, h: end - r.top, text};
}"""
JS = """([prefix]) => {
  const card = [...document.querySelectorAll('section.card')].find(s => s.querySelector('h2').innerText.startsWith('C1-04 '));
  const hs = [...card.querySelectorAll('h3')], i = hs.findIndex(h => h.innerText.toLowerCase().startsWith(prefix.toLowerCase()));
  if (i < 0) return null;
  const r = card.getBoundingClientRect(), top = hs[i].getBoundingClientRect().top + scrollY - 8;
  const end = (i + 1 < hs.length ? hs[i + 1].getBoundingClientRect().top : r.bottom) + scrollY - 10;
  const range = document.createRange(); range.setStartBefore(hs[i]);
  i + 1 < hs.length ? range.setEndBefore(hs[i + 1]) : range.setEndAfter(card.lastElementChild);
  return {x: r.left + 2, y: top, w: r.width - 4, h: end - top, text: range.toString()};
}"""


def main():
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    refused = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={'width': 1400, 'height': 1000}, device_scale_factor=2, color_scheme='light')
        pg.route('**/*', lambda r: r.continue_() if r.request.url.startswith('file://') else r.abort())
        pg.goto(CARD.as_uri(), wait_until='load')
        pg.wait_for_timeout(500)
        head = pg.evaluate("[...document.querySelectorAll('section.card h2 + *, section.card h2')].map(e => e.innerText).join(' ')")
        if 'approved digest f0cb1dc9ee14fc8f (by Jayant Kumar)' not in ' '.join(head.split()):
            refused.append('card head: approval stamp not the owner\'s')
        boxes = {}
        for name, (prefix, probes) in SECTIONS.items():
            box = pg.evaluate(JS, [prefix])
            missing = [p for p in probes if not box or p not in box['text']]
            if missing:
                refused.append(f'{name}: missing {missing}')
            boxes[name] = box
        if not refused:
            for name, box in boxes.items():
                pg.screenshot(path=str(OUT / f'{name}.png'), full_page=True,
                              clip={'x': box['x'], 'y': box['y'], 'width': box['w'], 'height': box['h']})
                print(f'{name}: {round(box["w"])} x {round(box["h"])} px, all probes found')
        pg.close()
        pg = b.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=2, color_scheme='light')
        pg.route('**/*', lambda r: r.continue_() if r.request.url.startswith('file://') else r.abort())
        pg.goto(SAMPLE.as_uri(), wait_until='load')
        pg.wait_for_timeout(1500)
        box = pg.evaluate(VERDICT_JS)
        missing = [p for p in VERDICT_PROBES if p not in box['text']]
        if missing or 'Maya' not in pg.inner_text('section.box.detail'):
            refused.append(f'maya-verdict: missing {missing or ["Maya"]}')
        else:
            pg.screenshot(path=str(OUT / 'maya-verdict.png'), full_page=True,
                          clip={'x': box['x'], 'y': box['y'], 'width': box['w'], 'height': box['h']})
            print(f'maya-verdict: {round(box["w"])} x {round(box["h"])} px, all probes found')
        b.close()
    if refused:
        sys.exit('wrong page state, not written:\n  ' + '\n  '.join(refused))


if __name__ == '__main__':
    main()
