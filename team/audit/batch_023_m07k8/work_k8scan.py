"""batch_023 K8 review: independent recompute (read-only, no main-flow changes)."""
import json, os
M07 = json.load(open('results/r30_bt/M07_final.json'))
WINS = ['1m','3m','6m','1y','2y','3y']
def nbeat(r):
    return sum(1 for w in WINS if r.get(w) is not None and M07.get(w) is not None and r[w] > M07[w])
def flags(r):
    nb = nbeat(r); ba = (nb == 6); mb = (r.get('mdd') is not None and r['mdd'] > M07['mdd'])
    return nb, ba, mb, (ba and mb)
out = {'m07': {k: M07.get(k) for k in ['total','mdd']+WINS}}
base = {}
for k in range(1, 8):
    d = json.load(open(f'results/r30_bt/sweep_beat_m07_k{k}.json'))
    base[k] = [r.get('tag') for r in d]
    out[f'k{k}_rows'] = len(d)
new17 = [t for k in range(1,8) for t in base[k] if t != 'base_M07']
out['k17_new'] = len(new17); out['k17_uniq'] = len(set(new17))
mism = 0; fba = 0
for k in range(1, 8):
    d = json.load(open(f'results/r30_bt/sweep_beat_m07_k{k}.json'))
    for r in d:
        nb, ba, mb, wa = flags(r)
        if r.get('beat_all') is True: fba += 1
        if (r.get('beat_all') is True) != ba or (r.get('nbeat_m07') is not None and r.get('nbeat_m07') != nb):
            mism += 1
            out.setdefault('k17_mismatch_tags', []).append(r.get('tag'))
out['k17_file_beat_all'] = fba; out['k17_recompute_mismatch'] = mism
kp = 'results/r30_bt/sweep_beat_m07_k8.json'
d8 = json.load(open(kp))
out['k8_status'] = 'PRESENT'; out['k8_rows'] = len(d8)
new8 = [r.get('tag') for r in d8 if r.get('tag') != 'base_M07']
out['k8_new'] = len(new8); out['k8_tags'] = sorted(new8)
out['k8_overlap_k17'] = sorted(set(new8) & set(new17))
rows = []
fba8 = 0; rba8 = 0; maxnb = -1; best = None
for r in d8:
    nb, ba, mb, wa = flags(r)
    if r.get('beat_all') is True: fba8 += 1
    if ba: rba8 += 1
    if ((r.get('beat_all') is True) != ba) or (r.get('nbeat_m07') is not None and r.get('nbeat_m07') != nb):
        out.setdefault('k8_decl_mismatch', []).append(r.get('tag'))
    if r.get('tag') != 'base_M07':
        if nb > maxnb: maxnb = nb; best = r.get('tag')
        rows.append({'tag': r.get('tag'), 'nbeat_re': nb, 'beat_re': ba,
                     'mdd': r.get('mdd'), 'mdd_better_re': mb, 'win_re': wa,
                     'total': r.get('total'), 'trades': r.get('trades'), 'cost': r.get('cost'),
                     'switch_same_m07': r.get('switch_same_m07'),
                     'diffs': {w: round(r[w]-M07[w],4) if r.get(w) is not None else None for w in WINS}})
out['k8_file_beat_all'] = fba8; out['k8_recompute_beat_all'] = rba8
out['k8_maxnbeat_new'] = maxnb; out['k8_best'] = best; out['k8_rows_detail'] = rows
for r in d8:
    if r.get('tag') == 'base_M07':
        out['k8_base_vs_m07'] = {k: [r.get(k), M07.get(k)] for k in ['total','mdd']+WINS}
json.dump(out, open('team/audit/batch_023_m07k8/part_k8scan.json','w'), ensure_ascii=False, indent=1)
print('K17 new/uniq/file_beat/mismatch =', out['k17_new'], out['k17_uniq'], out['k17_file_beat_all'], out['k17_recompute_mismatch'])
print('K8 rows/new/file_beat/re_beat/maxnbeat/best =', out['k8_rows'], out['k8_new'], out['k8_file_beat_all'], out['k8_recompute_beat_all'], out['k8_maxnbeat_new'], out['k8_best'])
print('K8 tags =', out['k8_tags'])
print('K8 overlap K1-K7 =', out['k8_overlap_k17'])
print('K8 decl mismatch =', out.get('k8_decl_mismatch', []))
print('K8 base vs M07 =', out.get('k8_base_vs_m07'))
for row in rows:
    print(row['tag'], 'nbeat=', row['nbeat_re'], 'beat=', row['beat_re'], 'mdd=', row['mdd'], 'total=', row['total'], 'diffs=', row['diffs'])
