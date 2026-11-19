#!/usr/bin/env python3
"""F3 round2: cut/win灵敏度 + band/gate扩展锚点 + 剩余daily (内存安全, 逐行落盘)."""
import sys, json, gc
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import fam_F3 as F
OUT = ROOT/"results"/"r30_bt"/"fam_F3_stage.json"
prev = json.load(open("/tmp/famF3_partial.json"))
rows = list(prev)
done = set(r["tag"] for r in rows)
def save():
    open(OUT, "w").write(json.dumps(rows, ensure_ascii=False, indent=1))
def do(c):
    if c["tag"] in done: print("SKIP " + c["tag"], flush=True); return
    try:
        kw = dict(c); tag = kw.pop("tag")
        r = F.run_switch(tag=tag, **kw)
        print(json.dumps(r, ensure_ascii=False), flush=True)
        rows.append(r); done.add(tag); save()
    except Exception as e:
        print("FAIL %s: %s" % (c["tag"], e), flush=True)
    finally:
        F._rb_cache.clear(); gc.collect()
A1 = dict(b_n=6, b_rebal=30, b_take=0.45, b_band=(0.05,0.30), b_gate=-1.0, bx=0.15, by_=0.05, bf=0.5)
A2 = dict(b_n=5, b_rebal=30, b_take=0.45, b_band=(0.05,0.30), b_gate=-1.0, bx=0.15, by_=0.05, bf=0.5)
A3 = dict(b_n=6, b_rebal=15, b_take=0.45, b_band=(0.05,0.30), b_gate=-1.0, bx=0.15, by_=0.05, bf=0.5)
cfgs = []
for nm, base in (("a1",A1),("a2",A2),("a3",A3)):
    for cut in (0.6, 0.8):
        for win in (10, 20, 40):
            cfgs.append(dict(base, tag="f3_%s_c%sW%d" % (nm, str(cut).replace(".",""), win), b_cut=cut, b_win=win))
for nm, base in (("a2",A2),("a3",A3)):
    for band, gate in [((0.02,0.30),-1.0),((0.05,0.30),-0.15),((0.02,0.30),-0.15)]:
        cfgs.append(dict(base, tag="f3_%s_bd%sG%s" % (nm, (str(band[0])+str(band[1])).replace(".",""), str(gate).replace(".","").replace("-","m")), b_band=band, b_gate=gate))
Dbase = dict(b_band=(0.05,0.30), b_gate=-1.0, b_cut=0.7, b_win=20, rs=60)
for btag, bn, bt, bx, by_, bf in [("f3_N6_R30_T045_bx015by01b05",6,0.45,0.15,0.10,0.5),("f3_N6_R30_T06_bx015by005b05",6,0.6,0.15,0.05,0.5)]:
    for h in (0.02, 0.03, 0.05):
        for bd in (False, True):
            cfgs.append(dict(Dbase, tag="%s_dH%s%s" % (btag, str(h).replace(".",""), "_bd" if bd else ""), b_n=bn, b_rebal=30, b_take=bt, bx=bx, by_=by_, bf=bf, hyst=h, evalfreq="daily", brake_daily=bd))
print("ROUND2 n=%d" % len(cfgs), flush=True)
for c in cfgs: do(c)
ok=[r for r in rows if r.get("pass_all")]
print("TOTAL=%d PASS=%d" % (len(rows), len(ok)), flush=True)
best=sorted(rows, key=lambda r:(r.get("margin",-999),r.get("total",0)), reverse=True)[:5]
print("BEST5="+json.dumps([{k:r[k] for k in ("tag","total","mdd","y2024_slice","y2024_yoy","y2025_yoy","y2026_slice","y2026_yoy","margin")} for r in best], ensure_ascii=False), flush=True)
