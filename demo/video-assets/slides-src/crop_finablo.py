"""Cut the Finablo frames' screenshot crops and text lines from the stored v706/v707 captures (read-only).

    python3 slides-src/crop_finablo.py       # then: python3 slides-src/render.py s7

Writes slides-src/img/finablo-*.png and scenes-data/finablo.json, which the s7-b1 and s7-b7 slides read. Nothing
is retyped: crops are cut from the captured screenshots and text lines are copied from the captured text.

Every source file's sha256 is recorded in scenes-data/finablo.json. Refuses to write when:
  * a crop box overlaps a place where the screenshot shows the "unused 401(k) headroom" sentence. That sentence is
    wrong on both builds (it uses the under-50 limit; fixed in v708), so it must stay out of every frame;
  * a copied text line mentions headroom, or does not carry the release's expected limit figure.

Sources are two runs of the finablo-semaudit harness with the same 61-year-old answers (target_61 and
target_61__wide in contract-wide/personas.yaml have identical context):
  wide-run-3k / target_61 / S-R1: sign up while the plan is still being written, open the Report tab, copy for AI
  f73-limit-check / target_61__wide / S-wide-target: the wide journey, plan finished
"""
import hashlib, json, pathlib, sys
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = pathlib.Path.home() / 'Documents/src/finablo-semaudit/runs'
TREES = {'v706': '10ff1e3', 'v707': 'a183626'}

def sr1(t, step, kind):
    return RUNS / f'wide-run-3k/captures/{t}/target_61__S-R1/{t}.target_61.S-R1.{step}.{kind}'

def f73(t, step, kind):
    return RUNS / f'f73-limit-check/captures/{t}/target_61__wide__S-wide-target/{t}.target_61__wide.S-wide-target.{step}.{kind}'

# Where each screenshot SHOWS the headroom sentence (page px, top..bottom). Measured by re-rendering the stored DOM
# snapshot with that release's own stylesheet at 1280 px (page heights match the screenshots exactly: 4767 and 3151)
# and confirmed by eye on the S-R1 v706 screenshot (the "What this means" line of the "Tax-advantaged space left on
# the table" card). The same sentence also sits inside every collapsed "Why this move?" panel; collapsed panels are
# not painted in these screenshots, so they are not listed.
HEADROOM_SHOWN = {'s03': [(1700, 1739)], 's06': [(1700, 1739)], 's10': []}

# (id, source(tree), step, crop box (left, top, right, bottom) in page px, what it shows)
CROPS = [
    ('report-pending', lambda t: sr1(t, 's03', 'c01.screenshot.png'), 's03', (315, 3058, 1185, 3242),
     'Report tab while the plan is still being written: action 2'),
    ('report-ready', lambda t: f73(t, 's06', 'c01.screenshot.png'), 's06', (315, 3058, 1185, 3242),
     'Report tab, plan finished: action 2'),
    ('report-pending-line', lambda t: sr1(t, 's03', 'c01.screenshot.png'), 's03', (315, 3058, 1185, 3126),
     'Report tab while the plan is still being written: action 2, header and text only'),
    ('report-ready-line', lambda t: f73(t, 's06', 'c01.screenshot.png'), 's06', (315, 3058, 1185, 3126),
     'Report tab, plan finished: action 2, header and text only'),
    ('dashboard', lambda t: f73(t, 's10', 'c01.screenshot.png'), 's10', (310, 2662, 1190, 2728),
     'Dashboard, "More moves": first row'),
]

# (id, source(tree), line number (1-based), what it is)
LINES = [
    ('export-pending', lambda t: sr1(t, 's04', 'c01.raw.txt'), 50, 'Copy for your AI, plan still being written (same user as report-pending)'),
    ('export-ready', lambda t: f73(t, 's08', 'c01.raw.txt'), 48, 'Copy for your AI, signed in, plan finished'),
    ('pdf', lambda t: f73(t, 's09', 'c02.raw.txt'), 50, "Welcome email's PDF report"),
]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    out = {'trees': TREES, 'crops': {}, 'lines': {}, 'sources': {}}
    problems, pending = [], []
    for rel, t in TREES.items():
        for cid, src, step, box, what in CROPS:
            p = src(t)
            im = Image.open(p)
            for top, bottom in HEADROOM_SHOWN[step]:
                if box[1] < bottom and box[3] > top:
                    problems.append(f'{cid} {rel}: crop {box} overlaps the headroom sentence at y {top}-{bottom}')
            name = f'finablo-{cid}-{rel}.png'
            pending.append((im.crop(box), HERE / 'img' / name))
            out['crops'].setdefault(cid, {'what': what})[rel] = name
            out['sources'][name] = {'file': str(p.relative_to(RUNS)), 'sha256': sha(p), 'box': box,
                                    'page_height': im.size[1],
                                    'headroom_shown_at': HEADROOM_SHOWN[step],
                                    'px_below_headroom': [box[1] - b for _, b in HEADROOM_SHOWN[step]]}
        for lid, src, n, what in LINES:
            p = src(t)
            line = p.read_text().splitlines()[n - 1].strip()
            if 'headroom' in line.lower():
                problems.append(f'{lid} {rel}: the copied line mentions headroom')
            want = '$35,750' if rel == 'v707' else '$32,500'
            if want not in line:
                problems.append(f'{lid} {rel}: expected {want} in line {n}, got {line!r}')
            out['lines'].setdefault(lid, {'what': what})[rel] = line
            out['sources'][f'{lid}-{rel}'] = {'file': str(p.relative_to(RUNS)), 'sha256': sha(p), 'line': n}
    # the pending report must carry the figure the frames claim
    if out['crops'] and problems == []:
        dom = sr1('10ff1e3', 's03', 'c01.dom.html').read_text()
        if 'IRS max ($24,500/yr)' not in dom:
            problems.append('report-pending v706: the DOM no longer says "IRS max ($24,500/yr)"')
    if problems:
        sys.exit('refusing to write:\n  ' + '\n  '.join(problems))
    for crop, path in pending:
        crop.save(path)
    (ROOT / 'scenes-data' / 'finablo.json').write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n')
    for name, s in out['sources'].items():
        print(f"{name}: {s['file']} sha256 {s['sha256'][:16]}" + (f" box {s['box']}" if 'box' in s else f" line {s['line']}"))


if __name__ == '__main__':
    main()
