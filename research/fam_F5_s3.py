import sys, json
sys.path.insert(0, '.')
sys.path.insert(0, 'team/audit')
sys.path.insert(0, 'research')
import fam_F5 as F
BASE = dict(sel='c_a60_turn', b_n=4, b_rebal=15, b_take=0.45, b_cut=0.70, b_win=20)
CFGS = []
for rs in (40, 42, 45, 48, 50):
    for hyst in (0.04, 0.05, 0.06, 0.07):
        CFGS.append(dict(tag='F5s3_rs%d_h%s_dg' % (rs, str(hyst).replace('.', '')), rs=rs, hyst=hyst, mh=0, evalfreq='daily', brake_daily=False, bx=0.18, by_=0.08, bf=0.6))
for by_ in (0.06, 0.10):
    CFGS.append(dict(tag='F5s3_rs45_h005_by%s' % str(by_).replace('.', ''), rs=45, hyst=0.05, mh=0, evalfreq='daily', brake_daily=False, bx=0.18, by_=by_, bf=0.6))
CFGS.append(dict(tag='F5s3_rs45_h005_mh5', rs=45, hyst=0.05, mh=5, evalfreq='daily', brake_daily=False, bx=0.18, by_=0.08, bf=0.6))
CFGS.append(dict(tag='F5s3_rs45_h005_bd', rs=45, hyst=0.05, mh=0, evalfreq='daily', brake_daily=True, bx=0.18, by_=0.08, bf=0.6))
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
best = sorted(rows, key=lambda r: (r.get('pass_all', False), r.get('margin', -999), r.get('total', 0)), reverse=True)[:14]
print('=== F5s3 TOP ===', flush=True)
for b in best:
    print(json.dumps({k: b.get(k) for k in ('tag', 'rs', 'hyst', 'bx', 'by_', 'bf', 'total', 'mdd', 'y2024_slice', 'y2024_yoy', 'y2024_mdd', 'y2025_yoy', 'y2025_mdd', 'y2026_slice', 'y2026_yoy', 'y2026_mdd', 'trades', 'switches', 'brakes', 'mode', 'pass_all', 'margin')}, ensure_ascii=False), flush=True)
open(F.ROOT / 'results' / 'r30_bt' / 'fam_F5_s3.json', 'w').write(json.dumps(rows, ensure_ascii=False, indent=1))
print('saved ' + str(len(rows)) + ' rows', flush=True)
