import json
d=json.load(open('results/r30_bt/fam_F2_stage.json'))
print(type(d), list(d.keys()) if isinstance(d,dict) else len(d))
rows=d.get('grid',[]) if isinstance(d,dict) else d
print('grid n=',len(rows))
ok=[r for r in rows if r.get('pass_all') or (r.get('y2024_slice',0)>60 and r.get('y2024_yoy',0)>60 and r.get('y2025_yoy',0)>60 and r.get('y2026_yoy',0)>60 and r.get('mdd',-99)>-30)]
print('pass:',len(ok))
for r in sorted(ok,key=lambda x:x.get('margin',x.get('margin_strict',0)),reverse=True)[:3]:
    print(r.get('tag'), r.get('y2024_slice'), r.get('y2024_yoy'), r.get('y2025_yoy'), r.get('y2026_yoy'), r.get('mdd'), r.get('margin',r.get('margin_strict')))
