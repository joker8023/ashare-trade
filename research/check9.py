import json
d=json.load(open('results/r30_bt/search_D_stage3.json'))
rows=d if isinstance(d,list) else d.get('rows',[])
for r in sorted(rows, key=lambda x: x.get('2024_yoy', x.get('y2024_yoy',-999)), reverse=True)[:5]:
    print(json.dumps({k:r.get(k) for k in list(r.keys()) if '202' in k or k in ['tag','mdd','total','margin']}, ensure_ascii=False, indent=1))
    print('---')
