import sys, json
sys.path.insert(0, '.')
sys.path.insert(0, 'team/audit')
sys.path.insert(0, 'research')
import fam_F5 as F
BASE = dict(sel='c_a60_turn', b_n=4, b_rebal=15, b_take=0.45, b_cut=0.70, b_win=20)
CFGS = []
for rs in (30, 45, 75):
    for hyst, mh in ((0.01, 0), (0.02, 0), (0.05, 0), (0.02, 5)):
        CFGS.append(dict(tag='F5s2_rs%d_h%s_mh%d_dg' % (rs, str(hyst).replace('.', ''), mh), rs=rs, hyst=hyst, mh=mh, evalfreq='daily', brake_daily=False, bx=0.18, by_=0.08, bf=0.6))
for rs in (30, 45):
    CFGS.append(dict(tag='F5s2_grid_rs%d' % rs, rs=rs, hyst=0.0, mh=0, evalfreq='grid', brake_daily=False, bx=0.18, by_=0.08, bf=0.6))
for bx, bf in ((0.25, 0.6), (0.30, 0.6), (0.25, 1.0), (0.18, 0.8)):
    CFGS.append(dict(tag='F5s2_b%s%s_daily_h002' % (str(bx).replace('.', ''), str(bf).replace('.', '')), rs=60, hyst=0.02, mh=0, evalfreq='daily', brake_daily=False, bx=bx, by_=0.08, bf=bf))
for band, gate in (((0.02, 0.30), -1.0), ((0.05, 0.30), -0.15), ((0.02, 0.30), -0.15)):
    CFGS.append(dict(tag='F5s2_band%s_gate%s' % (str(band[0]).replace('.', ''), str(gate).replace('.', '').replace('-', 'm')), band=band, gate=gate, rs=60, hyst=0.02, mh=0, evalfreq='daily', brake_daily=False, bx=0.18, by_=0.08, bf=0.6))
CFGS.append(dict(tag='F5s2_expb10', exp_b=1.0, rs=60, hyst=0.02, mh=0, evalfreq='daily', brake_daily=False, bx=0.18, by_=0.08, bf=0.6))
rows = []
for c in CFGS:
    tag = c.pop('tag')
    try:
        kw = dict(BASE)
        kw.update(c)
        r = F.run_switch(tag, **kw)
        print(json.dumps(r, ensure_ascii=False), flush=True)
        rows.append(r)
    except Exception as e:
        print('FAIL ' + tag + ': ' + str(e), flush=True)
best = sorted(rows, key=lambda r: (r.get('pass_all', False), r.get('margin', -999), r.get('total', 0)), reverse=True)[:12]
print('=== F5s2 TOP ===', flush=True)
for b in best:
    print(json.dumps({k: b.get(k) for k in ('tag', 'rs', 'hyst', 'mh', 'evalfreq', 'bx', 'by_', 'bf', 'b_band', 'b_gate', 'exp_b', 'total', 'mdd', 'y2024_slice', 'y2024_yoy', 'y2024_mdd', 'y2025_yoy', 'y2026_slice', 'y2026_yoy', 'trades', 'switches', 'mode', 'pass_all', 'margin')}, ensure_ascii=False), flush=True)
open(F.ROOT / 'results' / 'r30_bt' / 'fam_F5_s2.json', 'w').write(json.dumps(rows, ensure_ascii=False, indent=1))
print('saved ' + str(len(rows)) + ' rows', flush=True)
