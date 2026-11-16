import json, glob, collections
rows_by_k = {}
for k in range(1, 15):
    p = 'results/r30_bt/sweep_beat_m07_k%d.json' % k
    d = json.load(open(p, encoding='utf-8'))
    assert isinstance(d, list), p
    rows_by_k[k] = d
m07 = json.load(open('results/r30_bt/M07_final.json', encoding='utf-8'))
inv = json.load(open('results/r30_bt/inventory_k28.json', encoding='utf-8'))
print('M07_final keys:', sorted(m07.keys()))
print('M07 total/mdd:', m07.get('total'), m07.get('mdd'))
print('inventory_k28:', json.dumps(inv, ensure_ascii=False))
print()
exp_rows = {1:30,2:9,3:29,4:18,5:20,6:8,7:6,8:8,9:13,10:7,11:7,12:7,13:7,14:6}
exp_maxn = {1:4,2:4,3:5,4:2,5:4,6:2,7:4,8:4,9:3,10:1,11:0,12:2,13:3,14:3}
exp_new  = {1:29,2:8,3:28,4:17,5:19,6:7,7:5,8:7,9:12,10:6,11:6,12:6,13:6,14:4}
all_new_tags = []
tot_rows = 0
tot_beat = 0
tot_win = 0
for k in range(1, 15):
    d = rows_by_k[k]
    n = len(d)
    tot_rows += n
    tags = [r.get('tag') for r in d]
    base = [r for r in d if str(r.get('tag','')).startswith('base_')]
    new = [r for r in d if not str(r.get('tag','')).startswith('base_')]
    all_new_tags += [r.get('tag') for r in new]
    nb = sum(1 for r in d if r.get('beat_all'))
    nw = sum(1 for r in d if r.get('win_all'))
    tot_beat += nb; tot_win += nw
    mx = max(r.get('nbeat_m07', -1) for r in d)
    top = sorted(d, key=lambda r: (r.get('nbeat_m07',-1), r.get('total',-1e18)), reverse=True)[0]
    dup_in = [t for t,c in collections.Counter(tags).items() if c > 1]
    print('K%d rows=%d(exp %s) new=%d(exp %s) base=%s beat=%d win=%d maxn=%d(exp %s) top=%s nbeat=%s total=%s dup_in=%s' % (k, n, exp_rows[k], len(new), exp_new[k], [r.get('tag') for r in base], nb, nw, mx, exp_maxn[k], top.get('tag'), top.get('nbeat_m07'), top.get('total'), dup_in))
print()
print('TOTAL rows:', tot_rows, '(exp 175)')
print('TOTAL new:', len(all_new_tags), '(exp 160); K1-K13:', len([t for t in all_new_tags]))
c = collections.Counter(all_new_tags)
dups = {t: n for t, n in c.items() if n > 1}
print('distinct new:', len(c), '(exp 160)')
print('dup new tags across K1-K14:', json.dumps(dups, ensure_ascii=False) if dups else 'NONE')
print('TOTAL beat_all:', tot_beat, '(exp 0)')
print('TOTAL win_all:', tot_win, '(exp 0)')
print()
k8top = sorted(rows_by_k[8], key=lambda r: (r.get('nbeat_m07',-1), r.get('total',-1e18)), reverse=True)[0]
print('K8 strongest:', k8top.get('tag'), 'total=', k8top.get('total'), 'nbeat=', k8top.get('nbeat_m07'), '(exp g_bf07_winA30/2400.29)')
k14tags = [r.get('tag') for r in rows_by_k[14]]
print('K14 tags:', json.dumps(k14tags, ensure_ascii=False))
bg = [r for r in rows_by_k[14] if r.get('tag') == 'base_gbf07']
print('K14 base_gbf07 rows:', len(bg))
if bg:
    print(' base_gbf07:', json.dumps({kk: bg[0].get(kk) for kk in ['tag','total','mdd','1m','3m','6m','1y','2y','3y','nbeat_m07','beat_all']}, ensure_ascii=False))
    gk3 = [r for r in rows_by_k[3] if r.get('tag') == 'g_bf07']
    print(' K3 g_bf07 rows:', len(gk3))
    if gk3:
        keys = ['total','mdd','1m','3m','6m','1y','2y','3y','trades','cost','mode','switches','brakes']
        same = {kk: (bg[0].get(kk) == gk3[0].get(kk)) for kk in keys}
        print(' base_gbf07==K3 g_bf07 per-key:', json.dumps(same, ensure_ascii=False))
print()
print('base_M07 calibration check vs M07_final:')
for k in range(1, 15):
    b = [r for r in rows_by_k[k] if r.get('tag') == 'base_M07']
    if not b:
        print(' K%d: NO base_M07 row!' % k); continue
    r0 = b[0]
    keys = ['total','mdd','1m','3m','6m','1y','2y','3y','trades','cost','mode','switches','brakes']
    bad = {kk: (r0.get(kk), m07.get(kk)) for kk in keys if r0.get(kk) != m07.get(kk)}
    print(' K%d base_M07 rows=%d mismatch=%s' % (k, len(b), json.dumps(bad, ensure_ascii=False) if bad else 'NONE'))