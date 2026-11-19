import json
d=json.load(open('results/r30_bt/verify_C5.json'))
rows=d if isinstance(d,list) else d.get('rows', d.get('results',[]))
print(f"n={len(rows)}")
for r in rows:
    print(json.dumps({k:r.get(k) for k in ['tag','total','mdd','2024','2024_yoy','2024_mdd','2025_yoy','2025_mdd','2026','2026_yoy','2026_mdd','trades','cost','switches','pass','margin','max_abs_dev'] if k in r}, ensure_ascii=False))
try:
    print(open('team/audit/batch_06x_C5/README.md').read()[:2000])
except Exception as e:
    print('README err', e)
