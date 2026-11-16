# batch_018 sleeve cross-check (task2)
import json
import pandas as pd
R = '.'
d = json.load(open(R + '/results/r30_bt/dual_phase.json'))
def s(p):
    e = pd.read_pickle(p)
    return e.iloc[:, 0] if isinstance(e, pd.DataFrame) else e
e0 = s(R + '/results/r30_bt/dual_ph0_equity.pkl').dropna()
e15 = s(R + '/results/r30_bt/dual_ph15_equity.pkl').dropna()
sl = s(R + '/results/r30_bt/dual_sleeve_equity.pkl').dropna()
man = ((e0 + e15) / 2).dropna()
def stats(eq):
    t = round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2)
    m = round(float((eq / eq.cummax() - 1).min()) * 100, 2)
    return [t, m]
out = {}
out['lens'] = [len(e0), len(e15), len(sl), len(man)]
out['starts'] = [str(e0.index[0].date()), str(e15.index[0].date()), str(sl.index[0].date()), str(man.index[0].date())]
out['firsts'] = [round(float(e0.iloc[0]),2), round(float(e15.iloc[0]),2), round(float(sl.iloc[0]),2), round(float(man.iloc[0]),2)]
out['maxdiff'] = round(float((sl - man).abs().max()), 6)
out['recomputed'] = [stats(e0), stats(e15), stats(sl)]
out['file_totals'] = [d['ph0']['total'], d['ph15']['total'], d['sleeve']['total']]
out['file_mdds'] = [d['ph0']['mdd'], d['ph15']['mdd'], d['sleeve']['mdd']]
out['naive_avg'] = round((d['ph0']['total'] + d['ph15']['total']) / 2, 2)
out['e15_at_e0start'] = round(float(e15.loc[e0.index[0]]), 2)
out['trades'] = [d['trades_ph0'], d['trades_ph15']]
json.dump(out, open(R + '/team/audit/batch_018/part_sleeve.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
