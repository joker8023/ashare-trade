import json
d = json.load(open('results/r30_bt/sweep_beat_m07_k4.json'))
rows = d if isinstance(d, list) else d.get('rows', d)
print('N=', len(rows))
print(sorted(rows[0].keys()))
for r in rows:
    print(r.get('tag'), '| nbeat=', r.get('nbeat_m07'), '| beat_all=', r.get('beat_all'), '| win_all=', r.get('win_all'), '| total=', r.get('total'), '| mdd=', r.get('mdd'), '| mdd_better=', r.get('mdd_better'), '| sw=', r.get('switches'), '| same=', r.get('switch_same_m07'), '| trades=', r.get('trades'), '| cost=', r.get('cost'))
