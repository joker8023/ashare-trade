#!/usr/bin/env python3
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'research'))
import family_k11 as K
import sweep_beat_h1_v4 as V4
ktext = (ROOT / 'research' / 'family_k11.py').read_text()
v4src = (ROOT / 'research' / 'sweep_beat_h1_v4.py').read_text()
BS = chr(92)
NL = chr(10)
QT = chr(34)
def seg(src, start, endmark):
    a = src.find(start)
    b = src.find(endmark)
    return src[a:b] if a > 0 and b > a else ''
mk = NL + '    src = _once(CC'
sv = seg(v4src, 'brake_eval = ', mk)
sk = seg(ktext, 'brake_eval = ', mk)
print('RAWLEN v4=%d k11=%d' % (len(sv), len(sk)))
dv = sv.replace(BS + 'n', NL).replace(BS + QT, QT)
dk = sk.replace(BS + 'n', NL).replace(BS + QT, QT)
def norm2(s):
    out = ''
    for ch in s:
        if ch in (' ', chr(9), NL, chr(13), chr(39), QT):
            continue
        out = out + ch
    return out
nv = norm2(dv)
nk = norm2(dk)
print('NORMLEN v4=%d k11=%d equal=%s' % (len(nv), len(nk), nv == nk))
if nv != nk:
    n = min(len(nv), len(nk))
    i = 0
    while i < n and nv[i] == nk[i]:
        i = i + 1
    print('FIRSTDIFF at %d' % i)
    print('V4 :' + nv[max(0, i-80):i+120])
    print('K11:' + nk[max(0, i-80):i+120])
parts = ktext.split(chr(34) * 3)
code = parts[2] if len(parts) > 2 else ktext
print('DATES_COUNT in code=%d' % code.count('dates['))
k9 = json.load(open(ROOT / 'results' / 'r30_bt' / 'sweep_beat_m07_k9.json'))
print('K9 tags:')
for r in k9:
    print(' ' + r['tag'] + ' sw=' + str(r.get('switches')) + ' nbeat=' + str(r.get('nbeat_m07')) + ' total=' + str(r.get('total')) + ' mdd=' + str(r.get('mdd')))
k11 = json.load(open(ROOT / 'results' / 'r30_bt' / 'sweep_beat_m07_k11.json'))
m07 = json.load(open(ROOT / 'results' / 'r30_bt' / 'M07_final.json'))
base = [r for r in k11 if r['tag'] == 'base_M07'][0]
keys = ['total', 'mdd', 'trades', 'cost', 'mode', 'switches', '1m', '3m', '6m', '1y', '2y', '3y']
mis = {}
for k in keys:
    if base.get(k) != m07.get(k):
        mis[k] = (base.get(k), m07.get(k))
print('BASE_MISMATCH=' + json.dumps(mis, ensure_ascii=False))
print('BASE_SWITCHLOG_EQ=' + str(base.get('switch_log') == [list(x) for x in m07.get('switch_log', [])]))
print('BASE_BRAKELOG_EQ=' + str(base.get('brake_log') == [list(x) for x in m07.get('brake_log', [])]))
W = ['1m', '3m', '6m', '1y', '2y', '3y']
for r in k11:
    if r['tag'] == 'base_M07':
        continue
    nb = sum(1 for w in W if r[w] > m07[w])
    ba = all(r[w] > m07[w] for w in W)
    mb = r['mdd'] > m07['mdd']
    wa = bool(ba and mb)
    ok = (nb == r['nbeat_m07']) and (ba == r['beat_all']) and (mb == r['mdd_better']) and (wa == r['win_all'])
    print('RECOMP ' + r['tag'] + ' nbeat=' + str(nb) + ' beat_all=' + str(ba) + ' mdd_better=' + str(mb) + ' win_all=' + str(wa) + ' match=' + str(ok))
print('DONE')


