"""Capture the page shots the v8 clips are built from, at 2x (3840x2160), into slides-src/img/v8/ (untracked).

    python3 slides-src/shoot_v8.py            # local review pages only (file://, network blocked)
    python3 slides-src/shoot_v8.py --github   # also the public GitHub issue and pull request (network)

Local pages come from SRA/runs/recording-2026-11-01/pages/ (built with semaudit.report.page.build; see
docs/11-recording-runsheet.md and docs/12-demo-script-v8.md). Every probe text must be on the page before a shot is
written: if any is missing, that shot is skipped (the previous image stays as it was) and the script exits 1.
tests/test_shoot_v8_probes.py checks this with a fake page, no browser needed.
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRA = HERE.parents[2]
PAGES = SRA / 'runs' / 'recording-2026-11-01' / 'pages'
OUT = HERE / 'img' / 'v8'
LOCAL = [
    ('spree-tax-line', 'spree/index.html', 'persona=ana&mode=head&issue=R-v6.0.0.beta3-U1-line-amount-core-4f237b451a-ab6a0c63', ('43.19', '39.99')),
    ('spree-overview', 'spree/index.html', '', ('Resolved', 'Pre-existing')),
    ('northbound-maya', 'northbound/index.html', 'persona=maya&mode=head&issue=I-2.4-P2-fare-lock-price-watch-unexplained-tradeoff', ('next two weeks', 'Lock it for 48')),
    ('northbound-lena', 'northbound/index.html', 'persona=lena&mode=head&issue=', ('Cleared',)),
    ('brightdesk-hold', 'brightdesk-hold/index.html', '', ('Hold',)),
    ('brightdesk-ship', 'brightdesk-ship/index.html', '', ('Ship',)),
]
# Public pages, captured as tight crops (CSS px, measured from the live DOM on 2026-11-01). The PR's crops stop
# before its source-branch name and skip its description footer: both name a coding agent, which no frame may show.
GITHUB = [
    ('gh-issue-283', 'https://github.com/spree/storefront/issues/283', ('Closed', '#289'),
     {'gh-issue-head': (334, 180, 920, 144)}),
    ('gh-pr-289', 'https://github.com/spree/storefront/pull/289', ('Merged', 'Fixes #283'),
     {'gh-pr-title': (342, 184, 1014, 54), 'gh-pr-merged': (342, 236, 414, 44), 'gh-pr-fixes': (415, 394, 140, 36)}),
]


def missing_probes(text, probes):
    """The probes not on the page. A shot is written only when this is empty."""
    return [p for p in probes if p not in text]


def shoot(b, name, url, probes, block_network, clips=None):
    """Write the shot(s) for one page and return [], or write nothing and return the missing probes."""
    pg = b.new_page(viewport={'width': 1920, 'height': 1080}, device_scale_factor=2, color_scheme='light')
    try:
        if block_network:
            pg.route('**/*', lambda r: r.continue_() if r.request.url.startswith('file://') else r.abort())
        pg.goto(url, timeout=120000, wait_until='load')
        pg.wait_for_timeout(1800)
        missing = missing_probes(pg.inner_text('body'), probes)
        if missing:
            print(f'{name}: REFUSED, missing {missing}; nothing written')
            return missing
        if clips:
            for cname, (x, y, w, h) in clips.items():
                pg.screenshot(path=str(OUT / f'{cname}.png'), clip={'x': x, 'y': y, 'width': w, 'height': h})
        else:
            pg.screenshot(path=str(OUT / f'{name}.png'))
        print(f'{name}: all {len(probes)} probes found')
        return []
    finally:
        pg.close()


def shoot_all(b, github):
    """Every shot; returns the names of the pages that were refused."""
    refused = [name for name, page, h, probes in LOCAL
               if shoot(b, name, (PAGES / page).as_uri() + ('#' + h if h else ''), probes, True)]
    if github:
        refused += [name for name, url, probes, clips in GITHUB if shoot(b, name, url, probes, False, clips)]
    return refused


def main():
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        refused = shoot_all(b, '--github' in sys.argv)
        b.close()
    if refused:
        sys.exit(f'wrong page state, not written: {refused}')


if __name__ == '__main__':
    main()
