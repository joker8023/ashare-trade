import json
M = {'1m': -4.09, '3m': 17.28, '6m': 39.00, '1y': 164.05, '2y': 1474.08, '3y': 1677.53}
f = json.load(open('results/r30_bt/sweep_beat_m07_k4.json'))
for r in f:
    if r.get('kind', '').startswith('sleeve'):
        legs = [(l.get('phase'), l.get('total'), l.get('mdd')) for l in r.get('legs', [])]
        print(r.get('tag'), 'combo=', r.get('total'), 'spread=', r.get('leg_total_spread'), 'leg_ge4=', r.get('leg_nbeat_ge4'), legs)
for r in f:
    if r.get('tag', '').startswith('r_'):
        d = {w: round(r[w] - M[w], 2) for w in M}
        print(r.get('tag'), 'nbeat=', r.get('nbeat_m07'), 'diff=', d, 'sw=', r.get('switches'), 'same=', r.get('switch_same_m07'), 'cost=', r.get('cost'))
