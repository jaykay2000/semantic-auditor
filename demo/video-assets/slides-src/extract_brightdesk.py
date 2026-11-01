"""Write the Brightdesk evidence record and the beat-6 frame data, from the new-user test's own run files.

    python3 slides-src/extract_brightdesk.py                      # default: ~/Documents/src/sra-newuser-test/work/runs
    python3 slides-src/extract_brightdesk.py --runs <work/runs>   # any other copy
    python3 slides-src/extract_brightdesk.py --app <my-app>       # the agent's app folder (default: ~/Documents/src/sra-newuser-test/my-app)

Read-only on the source. Writes:
  demo/evidence/newuser-brightdesk-2026-11-01/record.json         the two reviews' outcomes and counts, the ledger
                                                                   totals, and the sha256 of each source file
  demo/evidence/newuser-brightdesk-2026-11-01/ledger-billed.jsonl  the billed (uncached) ledger rows, keys dropped
  demo/video-assets/scenes-data/brightdesk.json                    what the m8-b6 frame shows, derived from the record

Refuses to write if the broken release's review is not "hold", the fixed release's review is not "ship", the issues
new in one are not the issues resolved in the other, or the review's own cost disagrees with its ledger rows.
tests/test_demo_brightdesk_evidence.py re-derives the frame data from the committed record, so the frame cannot drift.
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ASSETS = HERE.parent
DEMO = ASSETS.parent
EVIDENCE = DEMO / 'evidence' / 'newuser-brightdesk-2026-11-01'
FRAME_DATA = ASSETS / 'scenes-data' / 'brightdesk.json'
DEFAULT_RUNS = pathlib.Path.home() / 'Documents/src/sra-newuser-test/work/runs'
DEFAULT_APP = pathlib.Path.home() / 'Documents/src/sra-newuser-test/my-app'
ADAPTER = 'adapter.py'
HOLD, SHIP, LEDGER = 't3/review-1.1-1.0.json', 't3/review-1.0-1.1.json', 'ledger.jsonl'
LEDGER_KEEP = ('ts', 'tag', 'role', 'model', 'priced', 'cached', 'cost_usd')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review_summary(rel, d):
    def issue(i):
        return {k: i[k] for k in ('id', 'rule', 'delta', 'delta_basis', 'rule_text', 'why')}
    return {'file': rel, 'app': d['app']['name'], 'release': d['release'],
            'recommendation': d['outcome']['recommendation'], 'rule_fired': d['policy']['rule_fired'],
            'cost_usd': d['cost_usd'], 'code_git': d['manifest']['code']['git'],
            'issues': [issue(i) for i in d['issues']], 'resolved': [issue(i) for i in d['resolved']]}


def ledger_summary(rows):
    billed = [r for r in rows if not r['cached']]
    tags = {}
    for r in rows:
        t = tags.setdefault(r.get('tag') or '(untagged)', {'billed_calls': 0, 'billed_usd': 0.0, 'cached_calls': 0})
        if r['cached']:
            t['cached_calls'] += 1
        else:
            t['billed_calls'] += 1
            t['billed_usd'] = round(t['billed_usd'] + r['cost_usd'], 8)
    return {'file': LEDGER, 'rows': len(rows), 'billed_calls': len(billed),
            'billed_usd': round(sum(r['cost_usd'] for r in billed), 6),
            'models': sorted({r['model'] for r in rows}), 'by_tag': tags}


def adapter_summary(path):
    """The agent's adapter: its size and its verbs (the scenario steps it can drive). Read-only."""
    text = path.read_text()
    return {'file': 'my-app/' + ADAPTER, 'sha256': sha256(path), 'lines': len(text.splitlines()),
            'verbs': re.findall(r'^    def verb_(\w+)\(', text, re.M)}


def prices(hold):
    """Each surface's Pro price on the broken release, as the hold review's issues report it ("plan_price 12 on
    pricing; 15 on checkout; ...")."""
    out = {}
    for i in hold['issues']:
        for value, surface in re.findall(r'(\d+) on (\w+)', i['why']):
            if out.setdefault(surface, value) != value:
                raise ValueError(f'{surface}: {out[surface]} and {value} in the same review')
    return out


def frame_data(record):
    """What m8-b6 shows. Called by this script and by the test, so the two cannot disagree."""
    hold, ship = record['reviews']['hold'], record['reviews']['ship']
    led = record['ledger']
    return {'_README': 'Derived from demo/evidence/newuser-brightdesk-2026-11-01/record.json by '
                       'slides-src/extract_brightdesk.py; tests/test_demo_brightdesk_evidence.py checks it.',
            'app': hold['app'],
            'hold': {'label': hold['recommendation'].upper(), 'new': sum(i['delta'] == 'new' for i in hold['issues'])},
            'ship': {'label': ship['recommendation'].upper(), 'resolved': len(ship['resolved'])},
            'billed_calls': led['billed_calls'],
            'cost_shown': f"${led['billed_usd']:.2f}",
            'rule': hold['issues'][0]['rule_text'],
            'prices_broken': {k: '$' + v for k, v in prices(hold).items()},
            'adapter_lines': record['adapter']['lines'], 'adapter_verbs': record['adapter']['verbs'],
            'model': led['models'][0] if len(led['models']) == 1 else None}


def check(record, billed_rows):
    hold, ship = record['reviews']['hold'], record['reviews']['ship']
    errors = []
    if hold['recommendation'] != 'hold':
        errors.append(f"{HOLD}: recommendation {hold['recommendation']!r}, expected 'hold'")
    if ship['recommendation'] != 'ship':
        errors.append(f"{SHIP}: recommendation {ship['recommendation']!r}, expected 'ship'")
    new = sorted(i['id'] for i in hold['issues'] if i['delta'] == 'new')
    resolved = sorted(i['id'] for i in ship['resolved'])
    if len({i['rule_text'] for i in hold['issues']}) != 1:
        errors.append(f'{HOLD}: the new issues are not all one rule')
    if len(set(prices(hold).values())) < 2:
        errors.append(f'{HOLD}: the broken release shows one price everywhere')
    if not new or new != resolved:
        errors.append(f'new in the broken release {new} != resolved in the fixed one {resolved}')
    led = record['ledger']
    if led['billed_calls'] != len(billed_rows) or abs(led['billed_usd'] - sum(r['cost_usd'] for r in billed_rows)) > 1e-6:
        errors.append('ledger totals disagree with the billed rows')
    for key, rel in (('hold', HOLD), ('ship', SHIP)):
        rv = record['reviews'][key]
        tag = f"semaudit-full:{rv['release']['base']}-{rv['release']['head']}:t3"
        got = led['by_tag'].get(tag, {'billed_usd': 0.0})['billed_usd']
        if abs(got - rv['cost_usd']) > 0.0005:
            errors.append(f'{rel}: cost_usd {rv["cost_usd"]} but its ledger rows ({tag}) bill {got}')
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runs', type=pathlib.Path, default=DEFAULT_RUNS)
    ap.add_argument('--app', type=pathlib.Path, default=DEFAULT_APP)
    args = ap.parse_args()
    runs = args.runs
    rows = [json.loads(line) for line in (runs / LEDGER).read_text().splitlines() if line.strip()]
    billed_rows = [{k: r[k] for k in LEDGER_KEEP if k in r} for r in rows if not r['cached']]
    record = {
        '_README': 'See README.md in this folder. Paths are relative to sra-newuser-test/work/runs.',
        'sources': {rel: sha256(runs / rel) for rel in (HOLD, SHIP, LEDGER)},
        'reviews': {'hold': review_summary(HOLD, json.loads((runs / HOLD).read_text())),
                    'ship': review_summary(SHIP, json.loads((runs / SHIP).read_text()))},
        'ledger': ledger_summary(rows),
        'adapter': adapter_summary(args.app / ADAPTER),
    }
    errors = check(record, billed_rows)
    if errors:
        sys.exit('refusing to write:\n  ' + '\n  '.join(errors))
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / 'record.json').write_text(json.dumps(record, indent=1) + '\n')
    (EVIDENCE / 'ledger-billed.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in billed_rows))
    FRAME_DATA.write_text(json.dumps(frame_data(record), indent=1) + '\n')
    print(json.dumps(frame_data(record)))


if __name__ == '__main__':
    main()
