"""行业反转BOTTOM5: 每20交易日按过去60日行业收益选最弱5个行业,
持有其中最超跌的30只(过去60日个股收益最低), R20调仓.
择时: 中证500 < MA15 -> 空仓 (净值overlay实现, 与risk_control同口径).
成本: 现实费率+滑点0.002+整手, 5万本金. 对照: J04 / 行业等权.
""";
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'team' / 'audit'))
import pandas as pd, numpy as np
import prior_check as pc
import risk_control as R
from sweep_beat_h1_v4 import WINDOWS

piv = pd.read_pickle(ROOT / 'data' / 'pivots_2020_clean.pkl')
c = piv['close'].astype('float64')
dates = c.index
ind_map = pd.read_pickle(ROOT / 'data' / 'industry_map.pkl')
print('ind_map type:', type(ind_map), flush=True)
print(ind_map.head(3).to_string(), flush=True)
print(ind_map['industry'].nunique(), 'industries:', ind_map['industry'].value_counts().head(8).to_dict(), flush=True)
codes6 = ind_map['code'].astype(str).str.zfill(6)
ind_of = pd.Series(ind_map['industry'].values, index=codes6)
# codes in both
codes = [s for s in c.columns if s in ind_of.index]
print('covered stocks:', len(codes), flush=True)
ind_of = ind_of.loc[codes]
ret = c.pct_change(fill_method=None)
# 行业日收益: 成分等权
ind_ret = ret[codes].T.groupby(ind_of.values).mean().T
print('industries:', ind_ret.shape[1], flush=True)
import sys as _sys
BOTK = int(_sys.argv[1]) if len(_sys.argv) > 1 else 5
MOMW = int(_sys.argv[2]) if len(_sys.argv) > 2 else 60
MAN = int(_sys.argv[3]) if len(_sys.argv) > 3 else 15  # 0 = no timing
ind_mom60 = (1 + ind_ret).rolling(MOMW).apply(np.prod, raw=True) - 1
stk_mom60 = c / c.shift(MOMW) - 1

class IndRevInputs(pc.Inputs):
    def picks(self, t, n=30, size_range=(0.05, 0.30), min_adv=5e6, exclude=(), factor='x'):
        if t not in dates:
            return []
        m = ind_mom60.loc[t].dropna()
        if len(m) < 5:
            return []
        bot5 = list(m.nsmallest(BOTK).index)
        members = [s for s in codes if ind_of.get(s) in bot5]
        ok = (self.seasoned.loc[t, members] & (self.adv20.loc[t, members] > min_adv)
              & c.loc[t, members].notna() & stk_mom60.loc[t, members].notna())
        pool = ok[ok].index.tolist()
        if not pool:
            return []
        return list(stk_mom60.loc[t, pool].nsmallest(n).index)

RUN_START = '2023-01-03'
EVAL_END = pd.Timestamp('2026-11-12')
grids = [dates[i] for i in range(300, len(dates) - 1, 20)]
first_sig = next(d for d in grids if d >= pd.Timestamp(RUN_START))
inp = IndRevInputs(piv)
res = pc.run_strategy(inp, n=30, rebal=20, stop=None, take=None, capital=50000.0,
                      lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
                      eval_start=first_sig, eval_end=EVAL_END, phase=0,
                      legacy_grid=False, full_liquidate=True, exposure=1.0)
eq = res.eq.dropna()
eq.to_pickle(ROOT / 'results' / 'r30_bt' / 'indrev_equity.pkl')

def stats(e):
    e = e.dropna()
    out = {'total': round(float(e.iloc[-1] / e.iloc[0] - 1) * 100, 2),
           'mdd': round(float((e / e.cummax() - 1).min()) * 100, 2)}
    for w, d in WINDOWS.items():
        sub = e.tail(d + 1)
        out[w] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
        out[w + '_mdd'] = round(float((sub / sub.cummax() - 1).min()) * 100, 2)
    return out

out = {'no_timing': {**stats(eq), 'trades': len(res.trades),
                     'cost': round(float(res.meta['total_cost']), 0)}}
# 择时overlay: 500<MA15 -> cash
m500 = R._index_series('000905').loc[:EVAL_END].reindex(eq.index).ffill()
pos = (m500 > m500.rolling(MAN).mean()).astype(float).shift(1).fillna(0) if MAN > 0 else pd.Series(1.0, index=eq.index)
r = eq.pct_change().fillna(0)
teq = (50000 * (1 + r * pos).cumprod())
tag = f'indrev_K{BOTK}_W{MOMW}_MA{MAN}'
out['timed'] = stats(teq)
teq.to_pickle(ROOT / f'results/r30_bt/{tag}_equity.pkl')
open(ROOT / f'results/r30_bt/{tag}.json', 'w').write(json.dumps({tag: out}, ensure_ascii=False, indent=1))
print(json.dumps({tag: out}, ensure_ascii=False))
print('saved ' + tag, flush=True)
