import json, collections
files = [f'results/r30_bt/sweep_beat_m07_k{k}.json' for k in range(1,19)]
M07 = json.load(open('results/r30_bt/M07_final.json'))
inv = json.load(open('results/r30_bt/inventory_k36.json'))
print('INV:', json.dumps(inv, ensure_ascii=False))
tot_rows = 0; all_new = []; rows_list = []; new_list = []; cal_list = []
maxnew_list = []; maxall_list = []
for f in files:
    j = json.load(open(f))
    assert isinstance(j, list), f
    tags = [r['tag'] for r in j]
    cal = [t for t in tags if t.startswith('base_')]
    new = [t for t in tags if not t.startswith('base_')]
    rows_list.append(len(j)); new_list.append(len(new)); cal_list.append(cal)
    tot_rows += len(j); all_new.extend(new)
    b = sum(1 for r in j if r.get('beat_all') is True)
    w = sum(1 for r in j if r.get('win_all') is True)
    mx_new = max([r.get('nbeat_m07',0) for r in j if not r['tag'].startswith('base_')] or [0])
    mx_all = max(r.get('nbeat_m07',0) for r in j)
    maxnew_list.append(mx_new); maxall_list.append(mx_all)
    print(f, 'rows=',len(j), 'cal=',cal, 'new=',len(new), 'beat=',b, 'win=',w, 'maxnew=',mx_new, 'maxall=',mx_all)
print('ROWS:', rows_list, 'sum=', tot_rows)
print('NEW:', new_list, 'sum=', sum(new_list))
print('CAL:', cal_list)
print('DISTINCT new:', len(set(all_new)), 'dups:', [k for k,v in collections.Counter(all_new).items() if v>1])
print('TOTAL beat_all true:', sum(1 for f in files for r in json.load(open(f)) if r.get('beat_all') is True))
print('MAXNEW:', maxnew_list)
print('INV maxnb ordered K1-18:', [inv['maxnb'].get(f'sweep_beat_m07_k{k}.json') for k in range(1,19)])
sigs = set()
for f in files:
    for r in json.load(open(f)):
        if r['tag']=='base_M07':
            sigs.add(json.dumps({k:r.get(k) for k in ['total','mdd','1m','3m','6m','1y','2y','3y','trades','cost','mode','switches']}, sort_keys=True))
print('base_M07 distinct sigs:', len(sigs))
print('base_M07 sig0:', sorted(sigs)[0] if sigs else None)
print('M07 sig:', json.dumps({k:M07.get(k) for k in ['total','mdd','1m','3m','6m','1y','2y','3y','trades','cost','mode','switches']}, sort_keys=True))
k3 = {r['tag']:r for r in json.load(open('results/r30_bt/sweep_beat_m07_k3.json'))}
for k in [14,15,16,18]:
    j = {r['tag']:r for r in json.load(open(f'results/r30_bt/sweep_beat_m07_k{k}.json'))}
    g = j.get('base_gbf07',{})
    o = k3.get('g_bf07',{})
    keys = ['total','mdd','1m','3m','6m','1y','2y','3y','trades','cost','mode','switches','nbeat_m07']
    print(k, 'has base_gbf07:', 'base_gbf07' in j, 'eq K3 g_bf07:', all(g.get(x)==o.get(x) for x in keys), {x:(g.get(x),o.get(x)) for x in keys if g.get(x)!=o.get(x)})
mx = None
for f in files:
    for r in json.load(open(f)):
        if mx is None or r['total']>mx[1]: mx=(f+'/'+r['tag'], r['total'], r.get('mdd'), r.get('nbeat_m07'), r.get('beat_all'))
print('GLOBAL MAX total:', mx)
k8 = {r['tag']:r for r in json.load(open('results/r30_bt/sweep_beat_m07_k8.json'))}
print('K8 winA30:', {x:k8['g_bf07_winA30'].get(x) for x in ['total','mdd','nbeat_m07','beat_all']})
k18 = {r['tag']:r for r in json.load(open('results/r30_bt/sweep_beat_m07_k18.json'))}
print('K18 tags:', sorted(k18.keys()))
for t,r in sorted(k18.items()):
    print('K18', t, {x:r.get(x) for x in ['total','mdd','nbeat_m07','beat_all']})
