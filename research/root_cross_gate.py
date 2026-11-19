import json
F1=json.load(open('results/r30_bt/verify_C5.json'))['rows'][0]
F1v=F1['verify']
print('F1 filed==verify max_abs_diff:', F1.get('max_abs_diff', 'n/a'), F1v['tag'], F1v['total'], F1v['mdd'])
import pandas as pd
def cmp(fv, filed_fp, frag, keymap):
    v=json.load(open(fv))
    d=json.load(open(filed_fp))
    rows=d if isinstance(d,list) else d.get('rows', d.get('grid',[]))
    f=next(r for r in rows if frag in r['tag'])
    print(f"== {v['tag']} vs {f['tag']}")
    diffs={}
    for vk,fk in keymap:
        a=v.get(vk); b=f.get(fk)
        dd=None if a is None or b is None else round(abs(a-b),4)
        diffs[vk]=dd
        flag='' if dd==0 else '  <-- MISMATCH'
        print(f"  {vk}={a} vs {fk}={b} diff={dd}{flag}")
    sl = v.get('switch_log')==f.get('switch_log')
    print('  switch_log identical:', sl, 'switches', v.get('switches'), f.get('switches'))
    strict = (v.get('y2024_slice',v.get('2024'))>60 and v.get('y2024_yoy',v.get('2024_yoy'))>60 and v.get('y2025_yoy',v.get('2025_yoy'))>60 and v.get('y2026_slice',v.get('2026'))>60 and v.get('y2026_yoy',v.get('2026_yoy'))>60 and v.get('mdd')>-30)
    print('  STRICT:', strict)
    return {"tag": f['tag'], "diffs": diffs, "switch_log_identical": sl, "strict": strict,
            "filed": {k: f.get(k) for k in ['total','mdd','trades','cost','mode','switches']},
            "verify": {k: v.get(k) for k in ['total','mdd','trades','cost','mode','switches']}}
res=[]
res.append(cmp('results/r30_bt/verify_F2.json','results/r30_bt/fam_F2_stage.json','bx012_by005_bf04', [('total','total'),('mdd','mdd'),('trades','trades'),('cost','cost'),('switches','switches'),('y2024_slice','y2024_slice'),('y2024_yoy','y2024_yoy'),('y2024_mdd','y2024_mdd'),('y2025_yoy','y2025_yoy'),('y2026_slice','y2026_slice'),('y2026_yoy','y2026_yoy')]))
res.append(cmp('results/r30_bt/verify_F4.json','results/r30_bt/fam_F4_stage.json','rs13_b01200605', [('total','total'),('mdd','mdd'),('trades','trades'),('cost','cost'),('switches','switches'),('2024','2024'),('2024_yoy','2024_yoy'),('2024_mdd','2024_mdd'),('2025_yoy','2025_yoy'),('2026','2026'),('2026_yoy','2026_yoy')]))
res.append(cmp('results/r30_bt/verify_F5.json','results/r30_bt/fam_F5_stage.json','rs42_h004', [('total','total'),('mdd','mdd'),('trades','trades'),('cost','cost'),('switches','switches'),('y2024_slice','y2024_slice'),('y2024_yoy','y2024_yoy'),('y2024_mdd','y2024_mdd'),('y2025_yoy','y2025_yoy'),('y2026_slice','y2026_slice'),('y2026_yoy','y2026_yoy')]))
res.append(cmp('results/r30_bt/verify_F7.json','results/r30_bt/fam_F7_stage.json','rs47_h0035_exp078', [('total','total'),('mdd','mdd'),('trades','trades'),('cost','cost'),('switches','switches'),('y2024_slice','y2024_slice'),('y2024_yoy','y2024_yoy'),('y2024_mdd','y2024_mdd'),('y2025_yoy','y2025_yoy'),('y2026_slice','y2026_slice'),('y2026_yoy','y2026_yoy')]))
json.dump(res, open('results/r30_bt/verify_CROSS.json','w'), ensure_ascii=False, indent=1)
print('saved verify_CROSS.json; all strict:', all(r['strict'] for r in res))
