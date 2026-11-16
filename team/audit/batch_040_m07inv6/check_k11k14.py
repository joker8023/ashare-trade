import json
for k in (11, 14):
    d = json.load(open('results/r30_bt/sweep_beat_m07_k%d.json' % k, encoding='utf-8'))
    new = [r for r in d if not r['tag'].startswith('base_')]
    mx = max(r['nbeat_m07'] for r in new)
    print('K%d new-only maxn=%d' % (k, mx))
    for r in sorted(new, key=lambda x: (-x['nbeat_m07'], -(x['total'] or 0))):
        print('  ', r['tag'], 'nbeat=', r['nbeat_m07'], 'total=', r['total'], 'beat_all=', r['beat_all'])