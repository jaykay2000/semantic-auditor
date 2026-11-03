"""Data for the v10 screens (storyboard v14.1, demo cut 3): every figure, quote and image they show.

    SPREE_HARNESS_DIR=<spree-semaudit> FINABLO_HARNESS_DIR=<finablo-semaudit> python3 slides-src/extract_v10.py

Writes scenes-data/v10.json and img/v10/*.png, recording the sha256 of every source, and REFUSES (exit 1) on any
mismatch:
  V2  the four contributions: each card's one-line Muse Spark job is fixed text here, checked by tests/test_demo_v10.py
  V3  Maya's and Lena's entries in examples/northbound/contract/personas.yaml, verbatim; rule P2 as principles.yaml
      writes it (and it must be the rule beat 5 judged, v9.json)
  V4  the saved check C1-04 as stored (docs/try-it/spree-saved-checks/contract-imported): the agent's report word
      for word, the 9 steps, rule U3; its approval in approvals.yaml must pin the digest the check hashes to today
      (semaudit's own ImportedCheck.digest), so the stamp is what a fresh run would accept; the owner's run
      ic-owner-rec-1 (beat4.json + its committed card) must show the same digest approved by the same name, FAIL on
      the older release, PASS on the newer, fix_confirmed, loaded from storage; "6 of 57" from the imported-checks
      README and its conversions file
  V5  the review page crop with the judge self-check line (docs/evidence/judge-self-check-2026-11-02)
  V6  Spree's rules file and adapter as committed in the spree-semaudit repo (git main, published as
      jaykay2000/spree-semaudit; the blob ids are recorded so they can be compared with GitHub), the adapter
      must be 531 lines, both must pass the demo hygiene patterns; one screenshot per app: Spree's storefront
      home page, a Finablo test user's v707 report, and Maya's Northbound search page
  V7  the results board: Finablo's 8 of 8 (v9.json), the v708 regression (v9.json finablo_fresh, from the committed
      counts.json), Spree's report and merge dates (demo/evidence/taxline-upstream-2026-10-30), the saved check's run
"""
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
ASSETS = HERE.parent
SRA = ASSETS.parents[1]
DATA = ASSETS / 'scenes-data'
IMG = HERE / 'img' / 'v10'
SRC = pathlib.Path(os.environ.get('FINLEARN_SRC', SRA.parent))
SPREE_REPO = pathlib.Path(os.environ.get('SPREE_HARNESS_DIR', SRC / 'spree-semaudit'))
FINABLO = pathlib.Path(os.environ.get('FINABLO_HARNESS_DIR', SRC / 'finablo-semaudit')) / 'runs'
sys.path.insert(0, str(SRA / 'src'))
sys.path.insert(0, str(SRA / 'tests'))

NB = SRA / 'examples' / 'northbound' / 'contract'
CHECKS = SRA / 'docs' / 'try-it' / 'spree-saved-checks' / 'contract-imported'
OWNER_CARD = SRA / 'docs' / 'evidence' / 'imported-checks' / 'acceptance' / 'cards-run-owner-2026-11-01.html'
IMPORTED = SRA / 'docs' / 'evidence' / 'imported-checks'
SELFCHECK = SRA / 'docs' / 'evidence' / 'judge-self-check-2026-11-02'
UPSTREAM = SRA / 'demo' / 'evidence' / 'taxline-upstream-2026-10-30' / 'README.md'
FINABLO_REPO = pathlib.Path(os.environ.get('FINABLO_HARNESS_DIR', SRC / 'finablo-semaudit'))
FIN_RULES = 'contract-wide/principles.yaml'        # committed (a206d42); contract-v707-v731/ is an uncommitted copy
SAMPLE = SRA / 'docs' / 'sample-review' / 'index.html'
RUN3C = SRA / 'docs' / 'evidence' / 'imported-checks' / 'acceptance' / 'run3c-saved-checks.json'
CHECK_ID = 'C1-04'
ADAPTER_LINES = 531
SHOTS = {   # app -> (source, crop box in page px): the top of one real page each, nothing below the fold
    'spree': (SPREE_REPO / 'runs/spree-scale-2t/captures/v6.0.0.beta3/ana__S-buy/v6.0.0.beta3.ana.S-buy.s01.c01.screenshot.png',
              (0, 0, 1280, 800)),
    'finablo': (FINABLO / 'f73-limit-check/captures/a183626/target_61__wide__S-wide-target/'
                          'a183626.target_61__wide.S-wide-target.s03.c01.screenshot.png', (0, 0, 1280, 800)),
    'northbound': (SRA / 'docs/sample-review/captures/2.4/maya__S-book-flexible/2.4.maya.S-book-flexible.s01.c01.screenshot.png',
                   (0, 0, 1280, 800)),
}
# The four contributions and each card's one Muse Spark job (storyboard v14.1). The Northbound/Spree evidence behind
# each is what V3-V6 show; tests/test_demo_v10.py pins the wording (no "every", no model but Muse Spark).
CARD1_TITLE = 'Judges what no test assertion can check'   # pending the owner's choice: "Catches what tests can't"
CONTRIBUTIONS = [
    {'n': 1, 'title': CARD1_TITLE, 'muse': 'Muse Spark reads each message and judges each rule.'},
    {'n': 2, 'title': 'Keeps what agents find', 'muse': 'Muse Spark drafts the steps and the rule from an agent\'s report.'},
    {'n': 3, 'title': 'Checks its own work', 'muse': 'Muse Spark looks at the screenshot, and is tested before it judges.'},
    {'n': 4, 'title': 'Plugs into your app', 'muse': 'It runs on the open-weight Muse Spark Open.'},
]


def sha256(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def rel(p):
    p = pathlib.Path(p)
    try:
        return str(p.relative_to(SRA))
    except ValueError:
        return p.name


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, check=True).stdout


def yaml_entry(text, start):
    """The lines of one top-level list entry, verbatim, from the line starting `start` to the next entry."""
    lines, out = text.splitlines(), None
    for ln in lines:
        if out is None:
            if ln.startswith(start):
                out = [ln]
        elif ln.startswith('- ') or not ln.strip():
            break
        else:
            out.append(ln)
    return out


def personas(errors):
    p = NB / 'personas.yaml'
    t = p.read_text()
    out = {}
    for pid in ('maya', 'lena'):
        lines = yaml_entry(t, f'- {{id: {pid},')
        if not lines:
            errors.append(f'{pid} not in {rel(p)}')
            continue
        out[pid] = lines
        import yaml
        e = yaml.safe_load('\n'.join(lines))[0]
        ctx, world = e['context'], e['world']
        fc = world.get('forecast', {}).get(ctx['route'], {})
        out[pid + '_plain'] = [['Trip', ctx['route'].replace('-', ' → ')],
                               ['Departs', 'day ' + ctx['departure_at'].lstrip('D').replace(' ', ', ')],
                               ['Dates', 'flexible' if ctx.get('flexible') else 'fixed'],
                               *([['Budget', e['axes']['budget']]] if e.get('axes', {}).get('budget') else []),
                               ['Seats left at the fare', str(next(iter(world['seats'].values())))],
                               ['Price forecast', f"drops within {fc['window_days']} days" if fc.get('drop') else 'no drop']]
    rp = NB / 'principles.yaml'
    rule = yaml_entry(rp.read_text(), '- id: P2')
    keep = [ln for ln in rule or [] if re.match(r'\s*(- id|title|text):', ln)]
    v9 = json.loads((DATA / 'v9.json').read_text())['northbound']['rule']
    if not keep or keep[-1].split('text: ', 1)[-1] != v9['text']:
        errors.append('P2 in principles.yaml is not the rule beat 5 judged (v9.json)')
    return {'source': rel(p), 'sha256': sha256(p), 'maya': out.get('maya'), 'lena': out.get('lena'),
            'maya_plain': out.get('maya_plain'), 'lena_plain': out.get('lena_plain'),
            'rule_source': rel(rp), 'rule_sha256': sha256(rp), 'rule_lines': keep, 'key_phrase': v9['key_phrase'],
            'app': 'Northbound · a demo travel app'}


ANA_SHOT = 'wide-run-3k/captures/10ff1e3/ana__S-guest-then-sign-up/10ff1e3.ana.S-guest-then-sign-up.s03.c01.screenshot.png'
ANA_BOX = (290, 238, 1212, 652)     # page px (1x): the report's "Your freedom" card only, measured on her page
ANA_PROBES = ('Work becomes optional at 45', '10 years ahead of your goal of 55')


def ana_report(errors):
    # V1's opening card (owner ruling: Ana's report, 45 and ahead, not the 61-year-old's 75, which reads as bad news
    # about a user and is not the bug). Same release (v706), same run and layout as the beat-1 card it replaces.
    shot = FINABLO / ANA_SHOT
    dom = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', shot.with_name(shot.name.replace('screenshot.png', 'dom.html')).read_text()))
    dom = __import__('html').unescape(dom)
    if not all(p in dom.replace(' .', '.') or p in dom for p in ANA_PROBES):
        errors.append(f'Ana\'s v706 report does not say {ANA_PROBES}')
    IMG.mkdir(parents=True, exist_ok=True)
    Image.open(shot).crop(ANA_BOX).save(IMG / 'ana-freedom-v706.png')
    return {'source': ANA_SHOT, 'sha256': sha256(shot), 'box': list(ANA_BOX), 'crop': 'img/v10/ana-freedom-v706.png',
            'persona': 'ana', 'release': 'v706', 'headline': ANA_PROBES[0], 'note': ANA_PROBES[1]}


def finablo_rules(errors):
    import yaml
    text = git(FINABLO_REPO, 'show', f'HEAD:{FIN_RULES}')
    rules = {r['id']: r for r in yaml.safe_load(text)}
    out = [{'id': k, 'title': rules[k]['title'], 'text': ' '.join(rules[k]['text'].split())} for k in ('H1', 'H2') if k in rules]
    if len(out) != 2:
        errors.append(f'H1/H2 not in finablo-semaudit {FIN_RULES}')
    copy = FINABLO_REPO / 'contract-v707-v731' / 'principles.yaml'
    if copy.exists():
        other = {r['id']: r for r in yaml.safe_load(copy.read_text())}
        if any(' '.join(other[r['id']]['text'].split()) != r['text'] or other[r['id']]['title'] != r['title'] for r in out):
            errors.append('contract-v707-v731 and contract-wide disagree on H1/H2')
    return {'source': f'finablo-semaudit {FIN_RULES}', 'blob': git(FINABLO_REPO, 'rev-parse', f'HEAD:{FIN_RULES}').strip(),
            'commit': git(FINABLO_REPO, 'rev-parse', '--short', 'HEAD').strip(), 'rules': out}


def maya_verdict(errors):
    page = SAMPLE.read_text()
    models = json.loads((DATA / 'v9.json').read_text())['northbound']['models']
    if '"interpreter": "muse-spark-1.3"' not in page or models['interpreter'] != 'muse-spark-1.3':
        errors.append('the sample review does not name muse-spark-1.3 as the model that reads each message')
    return {'source': rel(SAMPLE), 'sha256': sha256(SAMPLE), 'img': 'img/v10/maya-verdict.png',
            'issue': 'Unexplained tradeoff between Fare Lock and Price Watch', 'model': models['interpreter'],
            'model_role': 'interpreter'}


def saved_check(errors):
    import yaml

    from semaudit.imported.record import ImportedCheck
    rec = CHECKS / 'checks' / f'{CHECK_ID}.yaml'
    src = yaml.safe_load(rec.read_text())['source']
    digest = ImportedCheck.load(CHECKS, CHECK_ID).digest()
    ap = yaml.safe_load((CHECKS / 'approvals.yaml').read_text()).get(f'check:{CHECK_ID}', {})
    if ap.get('hash') != digest:
        errors.append(f'approvals.yaml pins {ap.get("hash")} but {CHECK_ID} hashes to {digest} today')
    b4 = json.loads((DATA / 'beat4.json').read_text())
    if (b4['check'], b4['digest'], b4['approved_by']) != (CHECK_ID, digest, ap.get('by')) or not b4['owner_reviewed']:
        errors.append('beat4.json (the owner run) is not this check at this digest, approved by the same name')
    if (b4['base']['assertion'], b4['head']['assertion'], b4['memory']['status']) != ('fail', 'pass', 'fix_confirmed'):
        errors.append('the owner run did not FAIL on the older release, PASS on the newer and confirm the fix')
    card = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', OWNER_CARD.read_text()))
    if f'approved digest {digest} (by {ap.get("by")})' not in card or b4['run']['id'] not in card:
        errors.append(f'{rel(OWNER_CARD)} does not show {digest} approved by {ap.get("by")} in run {b4["run"]["id"]}')
    readme = (IMPORTED / 'README.md').read_text()
    conv = (IMPORTED / 'heldout-conversions.txt').read_text()
    m = re.search(r'converts only\s+(\d+) of (\d+) held-out findings fully', readme)
    rows = re.findall(r'^\s+\S+#\d+\s+(\w+)', conv, re.M)
    if not m or (int(m.group(1)), int(m.group(2))) != (rows.count('converted'), len(rows)):
        errors.append('the README\'s "N of M held-out findings" disagrees with heldout-conversions.txt')
    report = {k: src[k] for k in ('claim', 'where', 'shown', 'should_be', 'reproduce')}
    return {'source': rel(rec), 'sha256': sha256(rec), 'id': CHECK_ID, 'report': report,
            'steps': [{'n': s['n'], 'verb': s['verb'], 'words': s['words']} for s in b4['journey']],
            'rule': b4['rule'], 'gate_problems_per_round': b4['conversion']['gate_problems_per_round'],
            'drafted_by': b4['conversion']['model'],
            'approval': {'by': ap.get('by'), 'date': ap.get('date'), 'fingerprint': ap.get('hash'),
                         'source': rel(CHECKS / 'approvals.yaml'), 'sha256': sha256(CHECKS / 'approvals.yaml')},
            'run': {'id': b4['run']['id'], 'card': rel(OWNER_CARD), 'card_sha256': sha256(OWNER_CARD),
                    'loaded_from_storage': b4['run']['loaded_from_storage']},
            'older': {'name': b4['base']['name'], 'assertion': b4['base']['assertion']},
            'newer': {'name': b4['head']['name'], 'assertion': b4['head']['assertion']},
            'memory': b4['memory']['status'],
            'prototype': {'converted': int(m.group(1)) if m else None, 'held_out': int(m.group(2)) if m else None,
                          'source': rel(IMPORTED / 'README.md'), 'sha256': sha256(IMPORTED / 'README.md'),
                          'conversions': rel(IMPORTED / 'heldout-conversions.txt'),
                          'conversions_sha256': sha256(IMPORTED / 'heldout-conversions.txt')}}


def self_check(errors):
    png, readme = SELFCHECK / 'review-page-verdict.png', (SELFCHECK / 'README.md').read_text()
    if 'passed, 6 of 6' not in readme:
        errors.append('the self-check README does not record "passed, 6 of 6"')
    IMG.mkdir(parents=True, exist_ok=True)
    (IMG / 'self-check.png').write_bytes(png.read_bytes())
    # the green line, in page px of the 1336 x 291 crop (located by eye; tests/test_demo_v10.py checks it is inside)
    return {'source': rel(png), 'sha256': sha256(png), 'img': 'img/v10/self-check.png', 'size': list(Image.open(png).size),
            'line_box': [22, 196, 700, 240], 'line': 'Judge self-check: 6 of 6 planted cases answered correctly'}


def spree_files(errors):
    from test_demo_assets_clean import LOCAL_PATH, NAMES
    out = {}
    for key, path in (('rules', 'contract-spree/principles.yaml'), ('adapter', 'adapter.py')):
        text = git(SPREE_REPO, 'show', f'main:{path}')
        if LOCAL_PATH.search(text) or NAMES.search(text):
            errors.append(f'spree-semaudit {path} fails the demo hygiene patterns')
        out[key] = {'path': path, 'blob': git(SPREE_REPO, 'rev-parse', f'main:{path}').strip(),
                    'lines': len(text.splitlines()), 'text': text}
    if out['adapter']['lines'] != ADAPTER_LINES:  # kept as a record; v15 does not show the count
        errors.append(f'adapter.py is {out["adapter"]["lines"]} lines, not {ADAPTER_LINES}')
    out['rules']['ids'] = re.findall(r'^- id: (\S+)', out['rules']['text'], re.M)
    import yaml
    titles = {}
    for r in yaml.safe_load(out['rules']['text']):
        titles.setdefault(r['title'], []).append(r['id'])
    out['rules']['plain'] = [{'ids': ids, 'title': t} for t, ids in titles.items()]
    del out['adapter']['text']                      # v15: the adapter is named, not scrolled (owner review)
    run = json.loads(RUN3C.read_text())
    judging = sorted({c['results'][r]['models']['judging'] for c in run['checks'] for r in ('current', 'candidate')})
    if judging != ['meta-models/muse-spark-open-1026']:
        errors.append(f'Run 3c judged with {judging}, not Muse Spark Open alone')
    out['spree_checks'] = {'model': judging[0] if judging else None, 'run': run['run'], 'source': rel(RUN3C),
                           'sha256': sha256(RUN3C), 'line': 'Spree checks: Muse Spark Open (open weights)'}
    out['commit'] = git(SPREE_REPO, 'rev-parse', '--short', 'main').strip()
    out['repo'] = 'github.com/jaykay2000/spree-semaudit'
    return out


def app_shots(errors):
    IMG.mkdir(parents=True, exist_ok=True)
    out = {}
    for app, (src, box) in SHOTS.items():
        if not src.exists():
            errors.append(f'missing screenshot for {app}: {rel(src)}')
            continue
        Image.open(src).crop(box).save(IMG / f'app-{app}.png')
        out[app] = {'source': rel(src) if app == 'northbound' else str(src.relative_to(src.parents[4])),
                    'sha256': sha256(src), 'box': list(box), 'img': f'img/v10/app-{app}.png'}
    out['labels'] = {'spree': 'Spree · an open-source store', 'finablo': 'Finablo · my finance app, a test user',
                     'northbound': 'Northbound · a demo travel app'}
    return out


def board(errors, check):
    v9 = json.loads((DATA / 'v9.json').read_text())
    places, ok = v9['finablo']['limits']['places'], v9['finablo']['correct_limit']
    fr = v9['finablo_fresh']
    up = UPSTREAM.read_text()
    rep = re.search(r'posted by the owner (\d{4}-\d\d-\d\d)T', up)
    mer = re.search(r'merged (\d{4}-\d\d-\d\d)T', up)
    if not (rep and mer):
        errors.append('report / merge dates not in the upstream README')
    if not all(p['v707'] == ok for p in places):
        errors.append('v707 does not state the right limit in every place')
    if fr['regressions_confirmed'] != 1:
        errors.append('the fresh review does not record exactly one confirmed regression')
    return {'finablo_fixed': {'places': len(places), 'right': sum(p['v707'] == ok for p in places), 'release': 'v707'},
            'finablo_regression': {'count': fr['regressions_confirmed'], 'introduced': fr['regression_introduced'],
                                   'source': fr['source']},
            'spree': {'reported': fmt(rep.group(1)) if rep else None, 'merged': fmt(mer.group(1)) if mer else None,
                      'repo': re.search(r'https://(github\.com/spree/[\w-]+)/issues/', up).group(1),
                      'source': rel(UPSTREAM), 'sha256': sha256(UPSTREAM),
                      'pr': int(re.search(r'merge of \*\*PR #(\d+)\*\*', up).group(1)),
                      'issue': int(re.search(r'/issues/(\d+)', up).group(1))},
            'saved_check': {'id': check['id'], 'run': check['run']['id'], 'memory': check['memory'],
                            'release': check['newer']['name']}}


def fmt(d):
    import datetime
    return datetime.date.fromisoformat(d).strftime('%b %-d')


def main():
    errors = []
    data = {'contributions': CONTRIBUTIONS, 'v1': {'ana': ana_report(errors)}, 'v3': personas(errors)}
    data['v3']['finablo'] = finablo_rules(errors)
    data['v3']['verdict'] = maya_verdict(errors)
    data['v4'] = saved_check(errors)
    data['v5'] = self_check(errors)
    data['v6'] = {'files': spree_files(errors), 'shots': app_shots(errors)}
    data['v7'] = board(errors, data['v4'])
    if errors:
        sys.exit('extract_v10 refused:\n  ' + '\n  '.join(errors))
    (DATA / 'v10.json').write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n')
    print('wrote', rel(DATA / 'v10.json'), 'and', len(list(IMG.glob('*.png'))), 'images in', rel(IMG))


if __name__ == '__main__':
    main()
