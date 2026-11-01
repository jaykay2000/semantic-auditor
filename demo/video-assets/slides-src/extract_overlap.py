"""Derive the beat-3 overlap numbers from the agent experiments' grading (read-only).

    python3 slides-src/extract_overlap.py   # writes scenes-data/overlap.json

Source: spree-plain-agent-protocol (a separate, private repo; point PROTOCOL_DIR at it, default: a sibling of this
repo), results-v4/grading/scores/scores.json: `per_trial` C1 and C2 `families_found`, and `repeatability_jaccard`
"C1/C2". Refuses to write if the two disagree.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROTOCOL = os.environ.get('PROTOCOL_DIR', os.path.join(HERE, '..', '..', '..', '..', 'spree-plain-agent-protocol'))
REL = 'results-v4/grading/scores/scores.json'
d = json.load(open(os.path.join(PROTOCOL, REL)))
a = set(json.loads(d['per_trial']['C1'])['families_found'] if isinstance(d['per_trial']['C1'], str)
        else d['per_trial']['C1']['families_found'])
b = set(json.loads(d['per_trial']['C2'])['families_found'] if isinstance(d['per_trial']['C2'], str)
        else d['per_trial']['C2']['families_found'])
both, union = len(a & b), len(a | b)
stated = d['repeatability_jaccard']['C1/C2'][0]
if stated != f'{both}/{union}':
    raise SystemExit(f'per_trial gives {both}/{union} but repeatability_jaccard says {stated}: refusing to write')
out = {'source': f'spree-plain-agent-protocol:{REL} (per_trial C1, C2; repeatability_jaccard C1/C2 = {stated})',
       'run_1_only': len(a - b), 'both': both, 'run_2_only': len(b - a), 'groups': union}
json.dump(out, open(os.path.join(HERE, '..', 'scenes-data', 'overlap.json'), 'w'), indent=1)
print(json.dumps(out, indent=1))
