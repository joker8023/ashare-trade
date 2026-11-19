import json
def show(fp, frag):
    d=json.load(open(fp))
    rows=d if isinstance(d,list) else d.get('rows', d.get('grid', []))
    for r in rows:
        if frag in r.get('tag',''):
            p={k:r.get(k) for k in ['tag','fam','b_sel','b_band','b_gate','b_cut','b_win','b_n','b_rebal','b_take','stop','exp_b','rs','bx','by_','bf','hyst','mh','confirm','evalfreq','brake_daily','lock','sw_stop'] if k in r}
            print(json.dumps(p, ensure_ascii=False))
            return
show('results/r30_bt/fam_F5_stage.json','rs42_h004');
show('results/r30_bt/fam_F7_stage.json','rs47_h0035_exp078')
