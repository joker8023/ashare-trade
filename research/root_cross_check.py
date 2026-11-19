import json
def show(fp, key):
    d=json.load(open(fp))
    rows=d.get('grid', d.get('rows', d if isinstance(d,list) else []))
    if isinstance(rows,dict): rows=list(rows.values())
    print(f"== {fp} keys={list(d.keys()) if isinstance(d,dict) else 'list'}")
    for r in rows:
        tag=r.get('tag','')
        if key in tag:
            print(json.dumps(r, ensure_ascii=False))
show('results/r30_bt/fam_F2_stage.json','bx012_by005_bf04')
