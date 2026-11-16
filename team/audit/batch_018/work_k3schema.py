import json
d = json.load(open('results/r30_bt/sweep_beat_m07_k3.json'))
rows = d if isinstance(d, list) else d.get('rows', d)
print(type(d).__name__, len(rows))
print(sorted(rows[0].keys()))
nb = [(r.get('name', r.get('id', '?')), r.get('nbeat'), r.get('beat_all'), r.get('total'), r.get('mdd')) for r in rows]
nb.sort(key=lambda x: (x[1] is None, -(x[1] or -1)))
print(nb[:8])
