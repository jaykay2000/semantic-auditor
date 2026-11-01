"""Capture the one page shot v9 adds: the hosted sample review (docs/sample-review/), at 2x, into slides-src/img/v9/.

    python3 demo/build_sample_review.py && python3 slides-src/shoot_v9.py

Same refusal as shoot_v8.py (it reuses its shoot()): every probe text must be on the page, or nothing is written and
the script exits 1. The page is opened from disk with the network blocked, exactly as GitHub Pages will serve it.
"""
import pathlib
import sys

import shoot_v8

HERE = pathlib.Path(__file__).resolve().parent
PAGE = HERE.parents[2] / 'docs' / 'sample-review' / 'index.html'
SHOTS = [('sample-review', ('Northbound', 'Unexplained tradeoff between Fare Lock and Price Watch', 'Hold'))]


def main():
    from playwright.sync_api import sync_playwright
    shoot_v8.OUT = HERE / 'img' / 'v9'
    shoot_v8.OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        refused = [n for n, probes in SHOTS if shoot_v8.shoot(b, n, PAGE.as_uri(), probes, True)]
        b.close()
    if refused:
        sys.exit(f'wrong page state, not written: {refused}')


if __name__ == '__main__':
    main()
