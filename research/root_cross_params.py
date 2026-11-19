import json
def show(fp, frag):
    d=json.load(open(fp))
    rows=d if isinstance(d,list) else d.get('rows', d.get('grid', []))
    for r in rows:
        if frag in r.get('tag',''):
            cfg=r.get('cfg', {})
            print('TAG:', r['tag'])
            print('CFG:', json.dumps(cfg, ensure_ascii=False))
            print('KEYS:', sorted(r.keys()))
            return
show('results/r30_bt/fam_F4_stage.json','rs13_b01200605');
show('results/r30_bt/fam_F5_stage.json','rs42_h004');
show('results/r30_bt/fam_F7_stage.json','rs47_h0035_exp078')
