#!/usr/bin/env python3
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'team' / 'audit'))
sys.path.insert(0, str(ROOT / 'research'))
out = {}
out['family_py_exists'] = (ROOT / 'research' / 'family_k11.py').exists()
out['sweep_k11_exists'] = (ROOT / 'results' / 'r30_bt' / 'sweep_beat_m07_k11.json').exists()
import family_k11 as K
import sweep_beat_h1_v4 as V4
se = (ROOT / 'research' / 'switch_engine.py').read_text()
anchors = {'AA': K.AA, 'BB': K.BB, 'CC': K.CC, 'DD': K.DD, 'EE': K.EE, 'FF': K.FF, 'GG': K.GG, 'SIG': K.SIG, 'PICKLINE': K.PICKLINE, 'DESIRED': K.DESIRED}
counts = {}
for k, v in anchors.items():
    counts[k] = se.count(v)
out['anchor_counts'] = counts
out['anchors_all_unique'] = all(c == 1 for c in counts.values())
ref = ['AA', 'BB', 'CC', 'DD', 'EE', 'FF', 'GG', 'SIG', 'PICKLINE']
out['anchors_match_v4'] = all(getattr(V4, k) == getattr(K, k) for k in ref)
try:
    ns_k11 = K.build_ns_k11()
    out['build_k11_ok'] = True
    out['has_run_strategy_switch'] = 'run_strategy_switch' in ns_k11
except Exception as e:
    out['build_k11_ok'] = False
    out['build_err'] = type(e).__name__ + ': ' + str(e)
ktext = (ROOT / 'research' / 'family_k11.py').read_text()
parts = ktext.split(chr(34) * 3)
code = parts[2] if len(parts) > 2 else ktext
probes = ['shift(-', 'sig_i +', 'sig_i+', 'searchsorted', 'iloc[', '.loc[', 'exec_map =', '.shift(', 'dates[', 'px_ffill_or_nan']
scan = {}
for p in probes:
    scan[p] = (p in code)
out['code_scan'] = scan
i1 = ktext.find('new_desired')
i2 = ktext.find('src = _once(DESIRED')
blk = ktext[i1:i2]
toks = []
cur = ''
for ch in blk:
    ok = ch.isalnum() or ch == '_'
    if ok:
        cur = cur + ch
    else:
        if cur != '':
            toks.append(cur)
        cur = ''
if cur != '':
    toks.append(cur)
tset = set(toks)
banned = set(['dates', 'mark', 'close', 'ret', 'shift', 'iloc', 'loc', 'searchsorted', 'picks', 'pos', 'cash', 'px_ffill_or_nan', 'exec_map', 'grid', 'sig_i', 'shadow_a', 'shadow_b'])
out['new_desired_banned_tokens'] = sorted(tset & banned)
out['new_desired_has_freeze'] = ('_brake' in tset) and ('_BRAKE_FREEZE' in tset)
out['new_desired_has_hyst'] = '_HYST' in tset
def norm(s):
    skip = set([chr(32), chr(9), chr(10), chr(13), chr(39), chr(34), chr(92)])
    r = ''
    for ch in s:
        if ch not in skip:
            r = r + ch
    return r
v4src = (ROOT / 'research' / 'sweep_beat_h1_v4.py').read_text()
tag = chr(10) + '    src = _once(CC'
j1 = v4src.find('brake_eval = ')
j2 = v4src.find(tag)
k1 = ktext.find('brake_eval = ')
k2 = ktext.find(tag)
okb = j1 > 0 and j2 > j1 and k1 > 0 and k2 > k1 and norm(v4src[j1:j2]) == norm(ktext[k1:k2])
out['brake_eval_identical'] = okb
tag2 = chr(10) + '    src = _once(DD'
m1 = v4src.find('skip_block = ')
m2 = v4src.find(tag2)
n1 = ktext.find('skip_block = ')
n2 = ktext.find(tag2)
oks = m1 > 0 and m2 > m1 and n1 > 0 and n2 > n1 and norm(v4src[m1:m2]) == norm(ktext[n1:n2])
out['skip_block_identical'] = oks
def getrow(f, tagw):
    rows = json.load(open(ROOT / 'results' / 'r30_bt' / f))
    for r in rows:
        if r['tag'] == tagw:
            return r
    return None
m07 = json.load(open(ROOT / 'results' / 'r30_bt' / 'M07_final.json'))
out['m07_switches'] = m07['switches']
out['m07_base'] = {'total': m07['total'], 'mdd': m07['mdd'], '1m': m07['1m'], '3m': m07['3m'], '6m': m07['6m'], '1y': m07['1y'], '2y': m07['2y'], '3y': m07['3y']}
pairs = [('sweep_beat_m07_k9.json', 'k9_amihud_5_both'), ('sweep_beat_m07_k10.json', 'k10_a60_a5_B'), ('sweep_beat_m07_k10.json', 'k10_a60_adv_both')]
for f, tagw in pairs:
    r = getrow(f, tagw)
    if r is None:
        out[tagw] = None
    else:
        out[tagw] = {'switches': r.get('switches'), 'nbeat_m07': r.get('nbeat_m07'), 'total': r.get('total'), 'mdd': r.get('mdd')}
try:
    from inputs_k10 import K10Inputs
    import pandas as pd
    piv = pd.read_pickle(ROOT / 'data' / 'pivots_2020_clean.pkl')
    ki = K10Inputs(piv, sel='a60_a5')
    out['k10inputs_a60_a5_ok'] = True
except Exception as e:
    out['k10inputs_a60_a5_ok'] = False
    out['k10inputs_err'] = type(e).__name__ + ': ' + str(e)
import glob as _glob
n_new = 0
beat = 0
flist = sorted(_glob.glob(str(ROOT / 'results' / 'r30_bt' / 'sweep_beat_m07_k*.json')))
for f in flist:
    for r in json.load(open(f)):
        if r['tag'] == 'base_M07':
            continue
        n_new = n_new + 1
        beat = beat + (1 if r.get('beat_all') else 0)
out['k1k10_new'] = n_new
out['k1k10_beat_all'] = beat
open(ROOT / 'team' / 'audit' / 'batch_033_m07k11' / 'part_033_verify.json', 'w').write(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out, ensure_ascii=False, indent=1))


