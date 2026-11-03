"""A contact sheet of the v10 screens: each clip seeked to its key moments, at 1x, labelled, in one PNG.

    python3 slides-src/contact_v10.py      # -> scenes/m10-contact-sheet.png (plus each frame in .motion-build/contact/)

Also runs render_motion.py's layout check at every frame and prints any page error, so the sheet doubles as a check.
"""
import json
import sys

import render_motion as rm
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

FRAMES = {   # clip -> the moments worth a look (clip seconds; provisional until the V1-V7 takes)
    'm10-v1-problem': [(2.0, 'the product card'), (8.0, '354 checks passed, then the two limits'),
                       (13.2, 'both struck, the correct one'), (18.6, 'the close')],
    'm10-v2-contributions': [(3.0, 'intro'), (11.0, 'the four contributions'), (13.4, 'shrunk to the corner marker')],
    'm10-v3-personas': [(7.0, "Finablo's rules H1, H2"), (11.5, 'v707: 8 of 8'), (15.8, 'Maya and Lena'),
                        (20.8, "Maya's verdict, muse-spark-1.3")],
    'm10-v4-keeps': [(12.0, "the agent's report"), (24.0, 'steps + rule, the gate'), (27.0, 'the approval stamp'),
                     (31.5, 'FAIL / PASS'), (36.8, 'reloaded, fix confirmed')],
    'm10-v5-checks-itself': [(10.5, 'a second, real bug'), (18.0, 'the screenshot: confirmed'),
                             (21.9, 'planted $39.99: contradicted'), (27.5, 'self-check 6 of 6')],
    'm10-v6-plugs-in': [(9.5, "Spree's rules, plain words"), (20.8, 'the three apps')],
    'm10-v7-results': [(29.3, 'the results board')],
}
W, H, COLS = 640, 360, 3


def main():
    data = {p.stem: json.loads(p.read_text()) for p in sorted(rm.DATA_DIR.glob('*.json'))}
    out = rm.BUILD / 'contact'
    out.mkdir(parents=True, exist_ok=True)
    cells, bad = [], []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for name, moments in FRAMES.items():
            pg, errs = rm.open_page(b, rm.HERE / f'{name}.html', data, 1)
            for t, label in moments:
                pg.evaluate(f'window.__seek({t})')
                problems = pg.evaluate(rm.CHECK)
                f = out / f'{name}@{t:g}.png'
                pg.screenshot(path=str(f))
                cells.append((f, f'{name} · {t:g} s · {label}'))
                if problems:
                    bad.append(f'{name}@{t:g}: {problems}')
            if errs:
                bad.append(f'{name}: {errs}')
            pg.close()
        b.close()
    rows = (len(cells) + COLS - 1) // COLS
    sheet = Image.new('RGB', (COLS * W + (COLS + 1) * 16, rows * (H + 44) + 16), '#E9E9E4')
    font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 18)
    for i, (f, label) in enumerate(cells):
        x, y = 16 + (i % COLS) * (W + 16), 16 + (i // COLS) * (H + 44)
        sheet.paste(Image.open(f).convert('RGB').resize((W, H), Image.LANCZOS), (x, y))
        ImageDraw.Draw(sheet).text((x, y + H + 8), label, fill='#30333A', font=font)
    dest = rm.STILLS / 'm10-contact-sheet.png'
    sheet.save(dest)
    print('wrote', dest, f'({len(cells)} frames)')
    for p in bad:
        print('PROBLEM', p)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
