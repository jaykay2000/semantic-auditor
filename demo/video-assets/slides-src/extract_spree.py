"""Derive the shopper matrix for s03b from the Spree reader review (read-only).

    python3 slides-src/extract_spree.py   # writes scenes-data/spree-shoppers.json
"""
import collections, json, os
SRC = os.path.expanduser('~/Documents/src/spree-semaudit/runs/spree-scale-2t/'
                         'review-v6.0.0.beta2-v6.0.0.beta3.reader.json')
OUT = os.path.join(os.path.dirname(__file__), '..', 'scenes-data', 'spree-shoppers.json')
d = json.load(open(SRC))
cells = collections.defaultdict(lambda: collections.Counter())
states = collections.Counter()
for p in d['personas']:
    cx = p['context']
    taxed = cx['state'] == 'NY'          # features: "Sales tax (NY 8%, harness-added)"
    states[cx['state']] += 1
    units = sum(int(i.split('|')[-1]) for i in cx['items'])
    key = f"{'tax' if taxed else 'notax'}|{'FREESHIP' if cx['promo_code'] else 'none'}|{cx['delivery_method']}"
    cells[key][units] += 1
out = {
    'source': SRC,
    'shoppers': len(d['personas']),
    'states': dict(states),
    'tax_feature': [f['name'] for f in d['features'] if f['id'] == 'tax'][0],
    'payment_methods': sorted({p['context']['payment_method'] for p in d['personas']}),
    'lines': sorted({len(p['context']['items']) for p in d['personas']}),
    'cells': {k: {str(u): n for u, n in sorted(v.items())} for k, v in sorted(cells.items())},
}
json.dump(out, open(OUT, 'w'), indent=1)
print(json.dumps(out, indent=1))
