"""Write the v9 frame data (beats 1, 3, 5 and 7) and the page crops those frames show, from the runs' own files.

    python3 slides-src/extract_v9.py
    FINABLO_HARNESS_DIR=<finablo-semaudit> SPREE_HARNESS_DIR=<spree-semaudit> python3 slides-src/extract_v9.py

Read-only on every source. Writes:
  demo/video-assets/scenes-data/v9.json   every number, quote and label the m9 frames print for these beats, with
                                          the sha256 of each file it came from
  demo/video-assets/slides-src/img/v9/    two crops (untracked, like every PNG here):
      finablo-freedom-v706.png   the report's "Your freedom" card, v706, the beat-1 test user (61)
      spree-order-page.png       Ana's order-placed page, Spree v6.0.0.beta3 (the page the review cites)

Refuses to write when a value the frames rely on is not what the source says:
  beat 1  the v706 gate record must say "354 OK", "0 FAIL" and the gate's own "All checks passed" line
  beat 3  the Spree issue must be pre-existing (both releases), cite $43.19 for Ana, and her order page must show a
          $43.19 line beside a $39.99 subtotal, a $3.60 tax row and a $48.59 total, where 39.99 + 5.00 + 3.60 = 48.59
          but 43.19 + 5.00 + 3.60 does not
  beat 5  Maya must be flagged under P2, Lena cleared under P2, both shown the same two offers, and Lena's
          explaining message must share no word with the rule's key phrase ("explain the material tradeoffs")
  beat 7  on v706 no capture states $35,750; on v707 every step that states a limit states $35,750 and only that
Beats 2, 4, 6 and 8 read beat4.json, brightdesk.json and close.json, which have their own extractors.
tests/test_demo_v9.py checks this file against the frames without the source folders.
"""
import hashlib
import json
import os
import pathlib
import re
import sys
from decimal import Decimal

import yaml
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ASSETS = HERE.parent
SRA = ASSETS.parents[1]
OUT = ASSETS / 'scenes-data' / 'v9.json'
IMG = HERE / 'img' / 'v9'
SRC = pathlib.Path(os.environ.get('FINLEARN_SRC', SRA.parent))
FINABLO = pathlib.Path(os.environ.get('FINABLO_HARNESS_DIR', SRC / 'finablo-semaudit')) / 'runs'
SPREE = pathlib.Path(os.environ.get('SPREE_HARNESS_DIR', SRC / 'spree-semaudit')) / 'runs' / 'spree-scale-2t'
GATE = SRA / 'demo' / 'evidence' / 'finablo-gate-v706' / 'README.md'
NB_REVIEW = SRA / 'runs' / 'e2e-2' / 'review-2.3-2.4.json'
NB_RULES = SRA / 'examples' / 'northbound' / 'contract' / 'principles.yaml'

# Finablo: the beat-1 user (wide-run-3k, target_61, S-R1, v706) and the beat-7 limit check (f73-limit-check)
FREEDOM_SHOT = 'wide-run-3k/captures/10ff1e3/target_61__S-R1/10ff1e3.target_61.S-R1.s03.c01.screenshot.png'
FREEDOM_BOX = (290, 262, 1212, 688)          # page px (1x, 1280 wide): the "Your freedom" card, nothing else
LIMITS = ('$24,500', '$32,500', '$35,750')
# The right 2026 limit for a 61-year-old with catch-up: IRS 2026 elective deferral + the ages 60-63 catch-up (as in
# demo/video-assets/scenes/README.md and docs/evidence/imported-checks/finablo/README.md)
CORRECT, CORRECT_BASIS = '$35,750', '$24,500 + the $11,250 catch-up for ages 60–63 (IRS 2026)'
TREES = {'v706': '10ff1e3', 'v707': 'a183626'}
# The f73 journey's steps, named as docs/evidence/imported-checks/finablo/README.md names them ("Captures" table)
STEP_NAMES = {'s02': 'Guest report, plan pending', 's03': 'Guest report, plan ready', 's05': 'Report after sign-up',
              's06': 'Signed-in report', 's07': 'Signed-in report, 2nd view', 's08': 'Copy for your AI',
              's09': 'Welcome email PDF', 's10': 'Dashboard'}
# Spree: the issue, the shopper and the step the review cites
SPREE_REVIEW = 'review-v6.0.0.beta2-v6.0.0.beta3.reader.json'
SPREE_ISSUE = 'R-v6.0.0.beta3-U1-line-amount-core-4f237b451a-ab6a0c63'
ORDER_BOX = (140, 380, 692, 690)             # page px (1x): the "Order Items" card of the order-placed page
ORDER_ROWS = {'line': '2-Slice Toaster', 'subtotal': 'Subtotal', 'shipping': 'Shipping', 'tax': 'Tax', 'total': 'Total'}
# Northbound
NB_ISSUE = 'I-2.4-P2-fare-lock-price-watch-unexplained-tradeoff'
NB_OFFERS = ('pw.email.forecast', 'fl.banner')
NB_EXPLAINS = 'cg.reconcile'
KEY_PHRASE = 'explain the material tradeoffs'


def sha256(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def money(s):
    return Decimal(s.replace('$', '').replace(',', ''))


def gate(errors):
    t = GATE.read_text()
    need = {'ok': '354 OK', 'fail': '0 FAIL', 'line': '✓ All checks passed. Safe to deploy.', 'date': '2026-09-30'}
    for s in need.values():
        if s not in t:
            errors.append(f'{GATE.name}: "{s}" not found')
    return {'source': str(GATE.relative_to(SRA)), 'sha256': sha256(GATE), 'release': 'v706', 'date': need['date'],
            'ok': 354, 'fail': 0, 'summary_line': need['line']}


def finablo(errors):
    shot = FINABLO / FREEDOM_SHOT
    IMG.mkdir(parents=True, exist_ok=True)
    Image.open(shot).crop(FREEDOM_BOX).save(IMG / 'finablo-freedom-v706.png')
    dom = shot.with_name(shot.name.replace('screenshot.png', 'dom.html'))
    copied = shot.with_name(shot.name.replace('s03.c01.screenshot.png', 's04.c01.raw.txt'))
    headline = 'Work could be optional at'
    if headline not in dom.read_text(errors='replace'):
        errors.append(f'{dom.name}: "{headline}" not on the page the crop is cut from')
    def lim(f):
        return sorted(set(re.findall(r'IRS max \((\$[\d,]+)/yr\)', f.read_text(errors='replace'))))
    shown = {'report': lim(dom), 'copied': lim(copied)}
    if shown != {'report': ['$24,500'], 'copied': ['$32,500']}:
        errors.append(f'the beat-1 user was not shown $24,500 on the report and $32,500 in the copied text: {shown}')
    counts = {}
    for rel, t in TREES.items():
        d = FINABLO / 'f73-limit-check' / 'captures' / t
        files = [f for f in d.rglob('*') if f.suffix in ('.txt', '.html', '.json')]
        per = {}
        for lim in LIMITS:
            steps = {re.search(r'\.(s\d+)\.', f.name).group(1) for f in files if lim in f.read_text(errors='replace')}
            per[lim] = sorted(steps)
        counts[rel] = per
    v6, v7 = counts['v706'], counts['v707']
    stating7 = sorted(set().union(*v7.values()))
    if v6['$35,750']:
        errors.append(f'v706 states $35,750 at {v6["$35,750"]}')
    if v7['$24,500'] or v7['$32,500'] or v7['$35,750'] != stating7 or not stating7:
        errors.append(f'v707 does not state $35,750 alone at every step that states a limit: {v7}')
    stating6 = sorted(set().union(*v6.values()))
    if stating6 != stating7 or set(stating7) - set(STEP_NAMES):
        errors.append(f'the two releases state the limit at different steps: {stating6} vs {stating7}')
    basis = [money(x) for x in re.findall(r'\$[\d,]+', CORRECT_BASIS)]
    if sum(basis) != money(CORRECT):
        errors.append(f'{CORRECT_BASIS} does not add up to {CORRECT}')
    places = [{'step': st, 'name': STEP_NAMES.get(st, st),
               'v706': next((x for x in LIMITS if st in v6[x]), None), 'v707': next((x for x in LIMITS if st in v7[x]), None)}
              for st in stating7]
    return {'shown': {'report': shown['report'][0] if shown['report'] else None,
                      'copied': shown['copied'][0] if shown['copied'] else None,
                      'sources': {'report': dom.name, 'report_sha256': sha256(dom),
                                  'copied': copied.name, 'copied_sha256': sha256(copied)}},
            'freedom': {'source': FREEDOM_SHOT, 'sha256': sha256(shot), 'box': list(FREEDOM_BOX),
                        'crop': 'img/v9/finablo-freedom-v706.png', 'headline': headline + ' 75.'},
            'limits': {'source': 'f73-limit-check/captures/<tree> (text, DOM and JSON captures, model-free)',
                       'steps': counts, 'v706': {k: len(v) for k, v in v6.items()},
                       'v707': {k: len(v) for k, v in v7.items()}, 'v707_steps_stating_a_limit': len(stating7),
                       'places': places},
            'correct_limit': CORRECT, 'correct_limit_basis': CORRECT_BASIS}


def spree(errors):
    review = SPREE / SPREE_REVIEW
    d = json.loads(review.read_text())
    issue = next((i for i in d['issues'] if i['id'] == SPREE_ISSUE), None)
    if issue is None:
        errors.append(f'{SPREE_ISSUE} not in {SPREE_REVIEW}')
        return {}
    occ = next(o for o in issue['occurrences'] if o['persona'] == 'ana')
    ev_id = occ['events'][0]
    ana = next(p for p in d['personas'] if p['id'] == 'ana')
    ev = next(e for e in ana['events'] if e['id'] == ev_id)
    shot_rel = ev['capture']['screenshot']
    page = [e for e in ana['events'] if (e.get('capture') or {}).get('screenshot') == shot_rel]

    def amount_right_of(label):
        lab = next(e for e in page if e['text'] == label)
        row = [e for e in page if e['text'].startswith('$') and abs(e['capture']['bbox']['y'] - lab['capture']['bbox']['y']) < 2]
        return row[0] if row else None
    rows = {}
    for k, label in ORDER_ROWS.items():
        e = amount_right_of(label)
        rows[k] = {'label': label, 'text': e['text'] if e else None,
                   'bbox': e['capture']['bbox'] if e else None}
    if issue['delta'] != 'pre_existing':
        errors.append(f'{SPREE_ISSUE}: delta {issue["delta"]}, expected pre_existing (in both releases)')
    if occ['quotes'] != ['$43.19'] or rows['line']['text'] != '$43.19':
        errors.append(f'Ana: the review quotes {occ["quotes"]}, the page line reads {rows["line"]["text"]}')
    want = {'subtotal': '$39.99', 'shipping': '$5.00', 'tax': '$3.60', 'total': '$48.59'}
    for k, v in want.items():
        if rows[k]['text'] != v:
            errors.append(f'order page {k}: {rows[k]["text"]}, expected {v}')
    if not errors:
        m = {k: money(r['text']) for k, r in rows.items()}
        if m['subtotal'] + m['shipping'] + m['tax'] != m['total'] or m['line'] + m['shipping'] + m['tax'] == m['total']:
            errors.append('the order page arithmetic is not the contradiction the frame describes')
    shot = SPREE / shot_rel
    IMG.mkdir(parents=True, exist_ok=True)
    Image.open(shot).crop(ORDER_BOX).save(IMG / 'spree-order-page.png')
    return {'review': SPREE_REVIEW, 'review_sha256': sha256(review), 'issue': SPREE_ISSUE,
            'release': d['release'], 'delta': issue['delta'], 'shoppers': len(d['personas']),
            'shoppers_shown_it': len(issue['personas']), 'rule': issue['rule'], 'rule_text': issue['rule_text'],
            'persona': ana['name'] if isinstance(ana.get('name'), str) else 'Ana Rivera', 'at': ev['at'][11:16],
            'shot': shot_rel, 'shot_sha256': sha256(shot), 'box': list(ORDER_BOX), 'crop': 'img/v9/spree-order-page.png',
            'rows': rows, 'record_item_total': '$39.99',
            'upstream': {'issue': 283, 'reported': '2026-10-30', 'pr': 289, 'merged': '2026-11-01',
                         'source': 'demo/evidence/taxline-upstream-2026-10-30/README.md'},
            'stars': {'count': 15805, 'read': '2026-11-01', 'how': 'gh api repos/spree/spree (stargazers_count)'}}


def northbound(errors):
    d = json.loads(NB_REVIEW.read_text())
    rules = yaml.safe_load(NB_RULES.read_text())
    p2 = next(r for r in rules if r['id'] == 'P2')
    P = {p['id']: p for p in d['personas']}

    def msg(pid, mid):
        e = next((e for e in P[pid]['events'] if e.get('id') == mid), None)
        return None if e is None else {'id': mid, 'at': e['at'][11:16], 'feature': e['feature'], 'channel': e['channel'],
                                        'text': e['text']}
    maya = [msg('maya', m) for m in NB_OFFERS]
    lena = [msg('lena', m) for m in NB_OFFERS]
    explains = msg('lena', NB_EXPLAINS)
    issue = next(i for i in d['issues'] if i['id'] == NB_ISSUE)
    cleared = next((n for n in d['not_raised'] if n['persona'] == 'lena' and n['rule'] == 'P2'), None)
    if 'maya' not in issue['personas']:
        errors.append(f'{NB_ISSUE}: Maya is not flagged')
    if not cleared or cleared['status'] != 'passed' or cleared['label'] != 'explained_tradeoff':
        errors.append(f'Lena is not cleared under P2: {cleared}')
    if None in maya or None in lena or explains is None or [m['text'] for m in maya] != [m['text'] for m in lena]:
        errors.append('Maya and Lena were not shown the same two offers')
    if KEY_PHRASE not in p2['text']:
        errors.append(f'P2 no longer says "{KEY_PHRASE}"')
    def stem(w):
        return re.sub(r'(s|ed|ing)$', '', w)
    key = {stem(w) for w in re.findall(r'[a-z]+', KEY_PHRASE) if w != 'the'}
    shared = sorted(key & {stem(w) for w in re.findall(r'[a-z]+', (explains or {}).get('text', '').lower())})
    if shared:
        errors.append(f'Lena\'s explaining message shares {shared} with the rule\'s key phrase')
    return {'review': str(NB_REVIEW.relative_to(SRA)), 'review_sha256': sha256(NB_REVIEW),
            'rules': str(NB_RULES.relative_to(SRA)), 'rules_sha256': sha256(NB_RULES),
            'release': d['release'], 'models': d['manifest']['models'],
            'rule': {'id': 'P2', 'text': p2['text'], 'key_phrase': KEY_PHRASE},
            'maya': {'name': 'Maya', 'offers': maya, 'verdict': 'flagged', 'issue': NB_ISSUE,
                     'severity': issue['severity']['level'], 'delta': issue['delta']},
            'lena': {'name': 'Lena', 'offers': lena, 'explains': explains, 'verdict': 'cleared',
                     'reason': cleared['reason'] if cleared else None},
            'key_words_in_lena_message': shared}


def main():
    errors = []
    data = {'_README': 'Written by slides-src/extract_v9.py from the runs\' own files (see each sha256). '
                       'tests/test_demo_v9.py checks the m9 frames against it.',
            'gate': gate(errors), 'finablo': finablo(errors), 'spree': spree(errors), 'northbound': northbound(errors)}
    if errors:
        sys.exit('refusing to write:\n  ' + '\n  '.join(errors))
    OUT.write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n')
    print(f'wrote {OUT.relative_to(SRA)}; crops in {IMG.relative_to(SRA)}')


if __name__ == '__main__':
    main()
