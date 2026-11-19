import json
d=json.load(open('results/r30_bt/verify_C5.json'))
rows=d['rows']
print(f"candidates: {len(rows)}")
ok=0
for r in rows:
    v=r['verify']
    c=(v['2024']>60 and v['2024_yoy']>60 and v['2025_yoy']>60 and v['2026']>60 and v['2026_yoy']>60 and v['mdd']>-30 and r.get('ref',{}).get('2024_mdd',v.get('2024_mdd',0)) is not None)
    # yearly mdds from ref
    ref=r.get('ref', {})
    m24=ref.get('2024_mdd', v.get('2024_mdd')); m25=ref.get('2025_mdd'); m26=ref.get('2026_mdd')
    strict = v['2024']>60 and v['2024_yoy']>60 and v['2025_yoy']>60 and v['2026']>60 and v['2026_yoy']>60 and v['mdd']>-30 and (m24>-30) and (m25>-30) and (m26>-30)
    print(f"{v['tag']}: 24 {v['2024']}/{v['2024_yoy']}/{m24} 25 {v['2025_yoy']}/{m25} 26 {v['2026']}/{v['2026_yoy']}/{m26} mdd {v['mdd']} -> {'PASS' if strict else 'FAIL'}")
    ok+=strict
print(f"STRICT PASS: {ok}/5")
w=json.load(open('results/r30_bt/C5_windows.json'))
print(f"windows rows: {len(w)}, tags: {[x['tag'][:20] for x in w]}")
