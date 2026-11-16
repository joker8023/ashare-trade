#!/usr/bin/env python3
import sys, json, glob
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
BS = chr(92)
NL = chr(10)
QT = chr(34)
ktext = (ROOT / 'research' / 'family_k11.py').read_text()
v4src = (ROOT / 'research' / 'sweep_beat_h1_v4.py').read_text()
mk = NL + '    src = _once(CC'
def seg(src, start):
    return src[src.find(start):src.find(mk)]
skipset = set([' ', chr(9), NL, chr(13), chr(39), QT, '(', ')'])
def norm3(s):
    s = s.replace(BS + 'n', '').replace(BS + QT, '')
    return ''.join(ch for ch in s if ch not in skipset)
a = norm3(seg(v4src, 'brake_eval = '))
b = norm3(seg(ktext, 'brake_eval = '))
print('BRAKE_NORM_EQUAL=' + str(a == b) + ' len=' + str(len(a)) + '/' + str(len(b)))
seen = {}
dup = []
for f in sorted(glob.glob(str(ROOT / 'results' / 'r30_bt' / 'sweep_beat_m07_k*.json'))):
    for r in json.load(open(f)):
        t = r['tag']
        if t in seen:
            dup.append((t, seen[t], f))
        seen[t] = f
k11tags = [r['tag'] for r in json.load(open(ROOT / 'results' / 'r30_bt' / 'sweep_beat_m07_k11.json'))]
print('K11TAGS=' + json.dumps(k11tags))
print('DUP_TAGS=' + json.dumps(dup))
print('DONE')
