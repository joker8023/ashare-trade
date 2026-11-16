"""VETO30_MAX 上 B 腿，进 J04 切换引擎验证.
 A腿: MaxInputs(band 2-30%, gate60=-0.15, max_cut .8, win40) n5/R20/TP1.2/exp1.0
 B腿: VETO30_MAX picks (MAX80->Amihud顺位->clf否决后30%补足) n5/R30/TP0.8/exp0.9
 切换: 双影子trailing-60, 刹车X0.18/Y0.08/F0.6, stop25 next, 成本同J04.
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'team' / 'audit')); sys.path.insert(0, str(ROOT / 'research'))
import pandas as pd, numpy as np
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import build_ns, WINDOWS, RUN_START, EVAL_END, MB

N, REBAL = 5, 20  # A腿网格 R20, 标签h=20
piv = pd.read_pickle(ROOT / 'data' / 'pivots_2020_clean.pkl')
c = piv['close'].astype('float64')
amt = piv['amount'].astype('float64')
vol = piv['volume'].astype('float64')
dates = c.index
mark = c.ffill()
ret = c.pct_change(fill_method=None)
adv20 = amt.rolling(20, min_periods=10).mean()
seasoned = c.shift(250).notna()
cap = c * piv['shares'].astype('float64')

def feat_all():
    F = {}
    F['amihud20'] = (ret.abs() / (amt.replace(0, np.nan) / 1e8)).rolling(20, min_periods=20).mean()
    F['amihud60'] = (ret.abs() / (amt.replace(0, np.nan) / 1e8)).rolling(60, min_periods=60).mean()
    F['size'] = np.log(cap.replace(0, np.nan))
    F['rev20'] = -(c / c.shift(20) - 1)
    F['rev60'] = -(c / c.shift(60) - 1)
    F['mom60'] = c / c.shift(60) - 1
    F['vol20'] = ret.rolling(20).std()
    F['max20'] = ret.rolling(20, min_periods=10).max()
    F['max40'] = ret.rolling(40, min_periods=20).max()
    F['turn20'] = (amt / cap.replace(0, np.nan)).rolling(20).mean()
    F['bias20'] = c / c.rolling(20).mean() - 1
    d = c.diff()
    up = d.clip(lower=0).rolling(14).mean(); dn = (-d.clip(upper=0)).rolling(14).mean()
    F['rsi14'] = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    F['amount20'] = np.log(amt.rolling(20, min_periods=10).mean().replace(0, np.nan))
    F['high250'] = c / c.rolling(250, min_periods=120).max() - 1
    F['volratio'] = vol.rolling(5).mean() / vol.rolling(60).mean()
    return F
F = feat_all()
FEATS = list(F.keys())
MONO = {'amihud20':1,'amihud60':1,'size':-1,'rev20':1,'rev60':1,'mom60':-1,
        'vol20':-1,'max20':-1,'max40':-1,'turn20':-1,'bias20':-1,'rsi14':-1,
        'amount20':-1,'high250':-1,'volratio':-1}
mono_tpl = tuple(MONO[f] for f in FEATS)

grids = [dates[i] for i in range(300, len(dates) - 1, REBAL)]

GATE60 = -0.15
RET60 = c / c.shift(60) - 1.0
RET10 = c / c.shift(10) - 1.0
def pool_at(t):
    valid = (seasoned.loc[t] & (adv20.loc[t] > 5e6) & c.loc[t].notna()
             & F['amihud60'].loc[t].notna())
    valid &= ~((RET60.loc[t] < GATE60) & (RET10.loc[t] < 0)).fillna(False)
    cap_t = cap.loc[t]
    lo, hi = cap_t.quantile(0.02), cap_t.quantile(0.30)
    valid &= ((cap_t >= lo) & (cap_t <= hi)).fillna(False)
    cols = valid.index.to_series()
    valid &= ~cols.str.startswith(MB).values
    return valid[valid].index

def fwd_ret(t, code, h=20):
    i = dates.get_loc(t)
    j = min(i + 1 + h, len(dates) - 1)
    p0 = mark.iloc[i + 1][code]; p1 = mark.iloc[j][code]
    if pd.isna(p0) or p0 <= 0 or pd.isna(p1):
        return np.nan
    return p1 / p0 - 1

pool_map, cls_label = {}, {}
for t in grids:
    pool = pool_at(t)
    pool_map[t] = pool
    fr = pd.Series({s: fwd_ret(t, s) for s in pool}, dtype='float64').dropna()
    cls_label[t] = (fr >= fr.quantile(0.70)).astype(int) if len(fr) >= 50 else pd.Series(dtype=int)

def zscore(df):
    return (df - df.mean()) / df.std().replace(0, np.nan)

from xgboost import XGBClassifier
test_grids = [t for t in grids if t >= pd.Timestamp(RUN_START)]
years = sorted(set(t.year for t in test_grids))
A_PICKS = {}
for y in years:
    tr = [t for t in grids if t < pd.Timestamp(f'{y}-01-01') and len(cls_label[t]) > 0]
    te = [t for t in test_grids if t.year == y]
    if len(tr) < 12 or not te:
        for t in te:
            mc = F['max40'].loc[t, pool_map[t]].dropna()
            mc = list(mc[mc <= mc.quantile(0.80)].index)
            amih = F['amihud60'].loc[t, mc].sort_values(ascending=False)
            B_PICKS[t] = list(amih.head(N).index)
        continue
    parts, yparts = [], []
    for t in tr:
        d = zscore(pd.DataFrame({f: F[f].loc[t] for f in FEATS}).loc[pool_map[t]])
        parts.append(d); yparts.append(cls_label[t])
    XX = pd.concat(parts); yy = pd.concat(yparts)
    m = (~XX.isna().any(axis=1)) & yy.notna()
    XX, yy = XX[m].fillna(0), yy[m]
    clf = XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05,
                        subsample=0.8, colsample_bytree=0.8, reg_lambda=5.0,
                        monotone_constraints=mono_tpl, n_jobs=4, random_state=7)
    clf.fit(XX.values, yy.values)
    for t in te:
        d = zscore(pd.DataFrame({f: F[f].loc[t] for f in FEATS}).loc[pool_map[t]]).fillna(0)
        proba = pd.Series(clf.predict_proba(d.values)[:, 1], index=d.index)
        mr = F['max40'].loc[t, pool_map[t]].dropna()
        mc = list(mr[mr <= mr.quantile(0.80)].index)
        amih_m = F['amihud60'].loc[t, mc].sort_values(ascending=False)
        thr = proba.quantile(0.30)
        picks, k = [], 0
        while len(picks) < N and k < len(amih_m):
            s = amih_m.index[k]
            if proba.get(s, 1.0) >= thr:
                picks.append(s)
            k += 1
        amih_all = F['amihud60'].loc[t, pool_map[t]].sort_values(ascending=False)
        k = 0
        while len(picks) < N and k < len(amih_all):
            s = amih_all.index[k]
            if s not in picks:
                picks.append(s)
            k += 1
        A_PICKS[t] = picks
    print(f'{y}: trained, predicted {len(te)} grids', flush=True)

class AInputs(pc.Inputs):
    def picks(self, t, n, size_range=(0.05, 0.30), min_adv=5e6, exclude=(), factor='amihud_60'):
        return list(A_PICKS.get(t, [])[:n])

first_sig = next(d for d in grids if d >= pd.Timestamp(RUN_START))
inp_a = AInputs(piv)
inp_b = MaxInputs(piv, band=(0.05, 0.30), gate60=-1.0, max_cut=0.80, max_win=40)
CA = dict(factor='amihud_60', stop=0.25, stop_exec='next', exclude=MB, capital=50000.0,
          lot=100, cost_one_way=None, slip=0.002, run_start=RUN_START,
          eval_start=first_sig, eval_end=EVAL_END, legacy_grid=False, full_liquidate=True)
CFG_B = dict(n=5, rebal=30, take=0.80, exposure=0.9)
ra = pc.run_strategy(inp_a, n=5, rebal=20, take=1.2, exposure=1.0, phase=0, **CA)
rb = pc.run_strategy(inp_b, phase=0, **{**CA, **CFG_B})
KW = dict(n=5, rebal=20, take=1.2, exposure=1.0, phase=0, inp_b=inp_b, cfg_b=CFG_B,
          shadow_a=ra.eq, shadow_b=rb.eq, exclude_a=MB, exclude_b=MB,
          **{k: v for k, v in CA.items() if k != 'exclude'})
ns = build_ns(0.18, 0.08, 0.6)
res = ns['run_strategy_switch'](inp_a, lock_mode=None, **KW)
eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
eq = eq.dropna()
eq.to_pickle(ROOT / 'results' / 'r30_bt' / 'xgb_switch_A_equity.pkl')
out = {'strategy': 'J04-A换VETO30_MAX', 'total': round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
       'mdd': round(float((eq / eq.cummax() - 1).min()) * 100, 2),
       'trades': len(res.trades), 'cost': round(float(res.meta['total_cost']), 0),
       'mode': res.meta['final_mode'], 'switches': len(res.meta['switch_log']),
       'switch_log': [list(x) for x in res.meta['switch_log']],
       'brake_log': [list(x) for x in res.meta.get('brake_log', [])]}
for w, d in WINDOWS.items():
    sub = eq.tail(d + 1)
    out[w] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
    out[w + '_mdd'] = round(float((sub / sub.cummax() - 1).min()) * 100, 2)
print(json.dumps(out, ensure_ascii=False, indent=1))
open(ROOT / 'results' / 'r30_bt' / 'xgb_switch_A.json', 'w').write(json.dumps(out, ensure_ascii=False, indent=1))
print('saved xgb_switch_A', flush=True)
