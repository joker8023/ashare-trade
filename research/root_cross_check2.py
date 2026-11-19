import json
def find(fp, keys):
    d=json.load(open(fp))
    rows=d if isinstance(d,list) else d.get('rows', d.get('grid', []))
    print(f"== {fp} n={len(rows)}")
    for r in rows:
        tag=r.get('tag','')
        if any(k in tag for k in keys):
            print(json.dumps({k:r.get(k) for k in ['tag','b_sel','sel','b_n','n','b_rebal','rebal','b_take','take','b_cut','b_win','bx','by_','bf','rs','stop','exp_b','exposure','evalfreq','hyst','min_hold','mh','brake_daily','total','mdd','trades','cost','mode','switches'] if k in r}, ensure_ascii=False))
            print('  annual:', json.dumps({k:r.get(k) for k in list(r.keys()) if '2024' in k or '2025' in k or '2026' in k}, ensure_ascii=False))
find('results/r30_bt/fam_F4_stage.json', ['rs13']);
find('results/r30_bt/fam_F5_stage.json', ['rs42_h004']);
find('results/r30_bt/fam_F7_stage.json', ['rs47_h0035_exp078'])
