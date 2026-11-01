"""Write scenes-data/beat4.json for the beat-4 motion clips (m7-b4-*), from the saved results of one run-saved run.

    python3 slides-src/extract_beat4.py                     # Run 3c, the committed video run
    python3 slides-src/extract_beat4.py --saved ~/Documents/src/spree-semaudit/runs/ic-owner-rec-1/saved-checks.json \
        --transcript ~/Documents/src/spree-semaudit/runs/ic-owner-rec-1.txt   # the recording-day run

Read-only. Every value on the beat-4 clips comes from here, and every value here is copied from a file, never typed:
  saved-checks JSON   run id, time, files loaded from storage, refusals, approval record, per-release statuses,
                      the email lines the judges cited (each found in the capture), the decisions-memory entry
  HARNESS checks/C1-04.yaml   the agent's finding as written, the journey, the rule, the gate rounds, the model.
                      Refused unless its sha256 matches the hash the run recorded when it loaded the file.
  HARNESS principles.yaml     the rule's title (U3)
  transcript (optional)       the exact run-saved command line
The running sums are plain addition of the cited email lines; the script refuses to write if any line cannot be
parsed, if the cited lines disagree between readings, or if a sum disagrees with the verdict it illustrates.
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys
from decimal import Decimal

import yaml

SRA = pathlib.Path.home() / 'Documents/src/semantic-auditor'
HARNESS = pathlib.Path.home() / 'Documents/src/spree-semaudit'
OUT = pathlib.Path(__file__).resolve().parent.parent / 'scenes-data' / 'beat4.json'
CHECK = 'C1-04'
# Which Spree build each harness slot holds: docs/11-recording-runsheet.md ("storefront 4030 (current/beta2) and
# 4031 (candidate/beta3)") and the Run 3c card title ("saved checks from storage, beta2 -> beta3").
RELEASE_NAME = {'current': 'v6.0.0.beta2', 'candidate': 'v6.0.0.beta3'}
LINES = [('subtotal', r'^Subtotal: \$([\d,]+\.\d\d)$'),
         ('promotion', r'^Promotion: .*-\$([\d,]+\.\d\d)$'),
         ('shipping', r'^Shipping: .*\$([\d,]+\.\d\d)$'),
         ('tax', r'^Tax: \$([\d,]+\.\d\d)$'),
         ('total', r'^Order Total: \$([\d,]+\.\d\d)$')]


def die(msg):
    sys.exit(f'extract_beat4: REFUSED: {msg}')


def email_lines(result):
    """The summary lines the agreeing readings cited, verbatim; every agreeing reading must cite the same values."""
    found = None
    for j in result['judgments']:
        if j.get('outcome') != result['assertion']['outcome'] or j.get('evidence', {}).get('status') != 'verified':
            continue
        quotes = [c['quote'] for c in j['cited']]
        got = {}
        for key, pat in LINES:
            hit = [q for q in quotes if re.match(pat, q)]
            if hit:
                got[key] = {'quote': hit[0], 'amount': re.match(pat, hit[0]).group(1).replace(',', '')}
        if len(got) != len(LINES):
            continue
        if found and {k: v['amount'] for k, v in found.items()} != {k: v['amount'] for k, v in got.items()}:
            die(f"readings cite different email lines on {result['release']}")
        found = found or got
    if not found:
        die(f"no verified, agreeing reading cites all five summary lines on {result['release']}")
    return found


def home(x):
    return str(x).replace(str(pathlib.Path.home()), '~')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--saved', default=str(SRA / 'docs/evidence/imported-checks/acceptance/run3c-saved-checks.json'))
    ap.add_argument('--transcript', default=str(SRA / 'docs/evidence/imported-checks/acceptance/run3c-transcript.txt'))
    ap.add_argument('--contract', default=str(HARNESS / 'contract-imported'))
    a = ap.parse_args()
    saved = json.loads(pathlib.Path(a.saved).read_text())
    contract = pathlib.Path(a.contract)
    chk_path = contract / 'checks' / f'{CHECK}.yaml'
    want = saved['loaded_from_storage'].get(f'checks/{CHECK}.yaml')
    have = hashlib.sha256(chk_path.read_bytes()).hexdigest()[:16]
    if want != have:
        die(f'{chk_path} is {have}, but the run loaded {want}: the check on disk is not the one that ran')
    chk = yaml.safe_load(chk_path.read_text())
    entry = next((c for c in saved['checks'] if c['id'] == CHECK), None) or die(f'{CHECK} not in {a.saved}')
    if entry['digest'] != entry['approved_digest']:
        die('the run replayed a digest other than the approved one')
    principles = yaml.safe_load((contract / 'principles.yaml').read_text())
    rule_id = chk['invariant']['rule']
    rule = next(p for p in principles if p['id'] == rule_id)

    # the agent's finding as written, and which words became which journey steps
    src = chk['source']
    actions = [c for c in chk['clauses'] if c['kind'] == 'action']
    reproduce = [{'text': c['text'].strip().rstrip('→').strip().rstrip('.'), 'steps': [s + 1 for s in c['steps']]} for c in actions]
    words_for = {s: r['text'] for r in reproduce for s in r['steps']}
    implied = set(chk['conversion']['implied_steps'])
    journey = []
    for i, st in enumerate(chk['scenario']['steps'], 1):
        if i in words_for:
            journey.append({'n': i, 'verb': st['do'], 'words': words_for[i]})
        elif st['do'] in implied:
            journey.append({'n': i, 'verb': st['do'], 'words': None})   # card wording: "prerequisite the text leaves unsaid"
        else:
            die(f'step {i} ({st["do"]}) carries no words and is not an implied prerequisite')
    gate_errors = chk['conversion']['gate_errors']

    releases = {}
    for slot in (saved['base'], saved['head']):
        r = entry['results'][slot]
        lines = email_lines(r)
        D = {k: Decimal(v['amount']) for k, v in lines.items()}
        total = D['subtotal'] - D['promotion'] + D['shipping'] + D['tax']
        adds_up = total == D['total']
        if adds_up != (r['assertion']['outcome'] == 'pass'):
            die(f'{slot}: the running sum ({total} vs {D["total"]}) disagrees with the verdict {r["assertion"]["outcome"]}')
        releases[slot] = {
            'slot': slot, 'name': RELEASE_NAME[slot],
            'replay': r['replay']['status'], 'assertion': r['assertion']['outcome'], 'votes': r['assertion']['votes'],
            'readings': r['semantic_confidence']['judgments'], 'agreement': r['semantic_confidence']['agreement'],
            'evidence': r['evidence']['status'], 'judged_by': r['models']['judging'],
            'lines': lines, 'sum': f'{total:.2f}', 'adds_up': adds_up}
    if (releases[saved['base']]['assertion'], releases[saved['head']]['assertion']) != ('fail', 'pass'):
        die('this clip shows an older-release FAIL and a next-release PASS; the run says otherwise')

    mem = entry['memory']
    cmd, out_lines = None, []
    t = pathlib.Path(a.transcript)
    if t.exists():
        tl = t.read_text().splitlines()
        cmd = next((line[2:].strip() for line in tl if line.startswith('$ ') and 'run-saved' in line), None)
        out_lines = [line for line in tl if line.startswith(f'{CHECK} ')]   # this check's own result lines, verbatim
        if cmd and f"--run {saved['run']}" not in cmd:
            die(f'the transcript {t} is not of run {saved["run"]}')
    by = entry['approved_by']
    out = {
        '_source': {'saved': home(a.saved), 'check': home(chk_path), 'check_sha256_16': have, 'transcript': home(t) if cmd else None},
        'check': CHECK, 'digest': entry['digest'], 'approved_by': by,
        'owner_reviewed': 'owner has not reviewed' not in by,
        'finding': {'ref': src['ref'], 'trial': src['trial'], 'claim': src['claim'], 'reproduce': reproduce},
        'journey': journey,
        'rule': {'id': rule_id, 'title': rule['title'], 'surface': chk['invariant']['surface'],
                 'statement': chk['invariant']['statement']},
        'conversion': {'status': chk['conversion']['status'], 'model': chk['conversion']['model'],
                       'gate_rounds': chk['conversion']['gate_rounds'],
                       'gate_problems_per_round': [len(e) for e in gate_errors]},
        'run': {'id': saved['run'], 'at': saved['at'], 'command': cmd, 'output': out_lines, 'loaded_from_storage': saved['loaded_from_storage'],
                'refused': saved['refused']},
        'base': releases[saved['base']], 'head': releases[saved['head']],
        'memory': {'status': mem['status'], 'why': mem['why'], 'run': mem['run']},
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n')
    print(f'wrote {OUT}: run {saved["run"]}, {CHECK} {out["base"]["assertion"]} -> {out["head"]["assertion"]}, memory {mem["status"]}')
    if not out['owner_reviewed']:
        print(f'WARNING: the approval on this run reads "{by}". The clip shows it verbatim, so the voice-over '
              f'"The owner approves it" does not match it. Approve the digest yourself, re-run run-saved, and re-extract.')


if __name__ == '__main__':
    main()
