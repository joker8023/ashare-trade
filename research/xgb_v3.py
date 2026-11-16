"""XGBoost v2: 分类目标 + 过滤器模式 + 单调约束 + MAX40.
 变体 (单引擎 R30/N5/TP80/stop25/exp0.9, 同成本):
  P1 clf-filter : Amihud60前30 -> clf概率前5
  P2 P1+MAX80   : MAX40-cut80 -> Amihud60前30 -> clf前5
  P3 ranker     : XGBRanker 全截面打分前5
  P4 P3+MAX80   : MAX40-cut80 后 ranker 前5
 对照: B (Amihud60前5).
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'team' / 'audit'))
import pandas as pd, numpy as np
import prior_check as pc
from xgboost import XGBClassifier, XGBRanker

EVAL_END = pd.Timestamp('2026-11-12')
RUN_START = '2023-01-03'
MB = ('688', '689', '300', '301', '8', '4')
N, REBAL = 5, 30

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
# 单调约束 (A股先验: ammihud+, 反转+, 动量-, 低波-, 去彩票-)
MONO = {'amihud20':1,'amihud60':1,'size':-1,'rev20':1,'rev60':1,'mom60':-1,
        'vol20':-1,'max20':-1,'max40':-1,'turn20':-1,'bias20':-1,'rsi14':-1,
        'amount20':-1,'high250':-1,'volratio':-1}
mono_tpl = tuple(MONO[f] for f in FEATS)

grids = [dates[i] for i in range(300, len(dates) - 1, REBAL)]

def pool_at(t):
    valid = (seasoned.loc[t] & (adv20.loc[t] > 5e6) & c.loc[t].notna()
             & F['amihud60'].loc[t].notna())
    cap_t = cap.loc[t]
    lo, hi = cap_t.quantile(0.05), cap_t.quantile(0.30)
    valid &= ((cap_t >= lo) & (cap_t <= hi)).fillna(False)
    cols = valid.index.to_series()
    valid &= ~cols.str.startswith(MB).values
    return valid[valid].index

def maxcut_pool(t, pool, cut=0.80):
    mr = F['max40'].loc[t, pool].dropna()
    if len(mr) < N:
        return list(mr.index)
    return list(mr[mr <= mr.quantile(cut)].index)

def zscore(df):
    return (df - df.mean()) / df.std().replace(0, np.nan)

def fwd_ret(t, code, h=30):
    i = dates.get_loc(t)
    j = min(i + 1 + h, len(dates) - 1)
    p0 = mark.iloc[i + 1][code]; p1 = mark.iloc[j][code]
    if pd.isna(p0) or p0 <= 0 or pd.isna(p1):
        return np.nan
    return p1 / p0 - 1

pool_map, cls_label, fwd_map = {}, {}, {}
for t in grids:
    pool = pool_at(t)
    pool_map[t] = pool
    fr = pd.Series({s: fwd_ret(t, s) for s in pool}, dtype='float64').dropna()
    fwd_map[t] = fr
    if len(fr) >= 50:
        cls_label[t] = (fr >= fr.quantile(0.70)).astype(int)
    else:
        cls_label[t] = pd.Series(dtype=int)
print('median pool:', float(np.median([len(v) for v in pool_map.values()])), flush=True)

test_grids = [t for t in grids if t >= pd.Timestamp(RUN_START)]
years = sorted(set(t.year for t in test_grids))
P = {k: {} for k in ('VETO', 'BLEND', 'BLEND_MAX')}
imp_clf, imp_rank = {}, {}
for y in years:
    tr = [t for t in grids if t < pd.Timestamp(f'{y}-01-01') and len(cls_label[t]) > 0]
    te = [t for t in test_grids if t.year == y]
    if len(tr) < 12 or not te:
        for t in te:  # fallback Amihud
            s = F['amihud60'].loc[t, pool_map[t]].sort_values(ascending=False)
            for k in P:
                P[k][t] = list(s.head(N).index)
        continue
    Xtr_raw = pd.concat([pd.DataFrame({f: F[f].loc[t] for f in FEATS}).loc[pool_map[t]] for t in tr])
    # 逐截面标准化
    parts, yparts, groups = [], [], []
    for t in tr:
        d = pd.DataFrame({f: F[f].loc[t] for f in FEATS}).loc[pool_map[t]]
        parts.append(zscore(d))
        yparts.append(cls_label[t])
        groups.append(len(d))
    XX = pd.concat(parts); yy = pd.concat(yparts)
    m = (~XX.isna().any(axis=1)) & yy.notna()
    XX, yy = XX[m], yy[m]
    XX = XX.fillna(0)
    clf = XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05,
                        subsample=0.8, colsample_bytree=0.8, reg_lambda=5.0,
                        monotone_constraints=mono_tpl, n_jobs=4, random_state=7)
    clf.fit(XX.values, yy.values)
    imp_clf[y] = dict(zip(FEATS, [float(x) for x in clf.feature_importances_]))
    # ranker: relevance = cross-sectional rank pct of fwd ret (positional, per-grid dropna)
    Xb_list, rel_list, gg = [], [], []
    for t in tr:
        d = zscore(pd.DataFrame({f: F[f].loc[t] for f in FEATS}).loc[pool_map[t]])
        fr = fwd_map[t]
        common = d.index.intersection(fr.index)
        d, fr = d.loc[common], fr.loc[common]
        ok_rows = ~d.isna().any(axis=1) & fr.notna()
        d, fr = d[ok_rows].fillna(0), fr[ok_rows]
        if len(d) < 50:
            continue
        Xb_list.append(d.values)
        rel_list.append((fr.rank(pct=True) * 10).astype(int).values)
        gg.append(len(d))
    Xrk = np.vstack(Xb_list)
    rel_all = np.concatenate(rel_list)
    rk = XGBRanker(n_estimators=300, max_depth=4, learning_rate=0.05,
                   reg_lambda=5.0, monotone_constraints=mono_tpl, n_jobs=4, random_state=7)
    rk.fit(Xrk, rel_all, group=gg, verbose=False)
    imp_rank[y] = dict(zip(FEATS, [float(x) for x in rk.feature_importances_]))
    for t in te:
        d = pd.DataFrame({f: F[f].loc[t] for f in FEATS}).loc[pool_map[t]]
        dz = zscore(d).fillna(0)
        proba = pd.Series(clf.predict_proba(dz.values)[:, 1], index=dz.index)
        rank_s = pd.Series(rk.predict(dz.values), index=dz.index).sort_values(ascending=False)
        amih = F['amihud60'].loc[t, pool_map[t]].sort_values(ascending=False)
        mc = maxcut_pool(t, pool_map[t])
        # VETO: Amihud前5, 剔除clf池内后30%的, 按Amihud顺位补足
        veto_thr = proba.quantile(0.30)
        picks, k = [], 0
        while len(picks) < N and k < len(amih):
            s = amih.index[k]
            if proba.get(s, 1.0) >= veto_thr:
                picks.append(s)
            k += 1
        P['VETO'][t] = picks
        # BLEND: rank(Amihud)+rank(clf) 各半取前5
        blend = (amih.rank(pct=True) + proba.rank(pct=True)).sort_values(ascending=False)
        P['BLEND'][t] = list(blend.head(N).index)
        # BLEND_MAX: MAX80池内做同样blend
        blend_m = blend[blend.index.isin(mc)]
        P['BLEND_MAX'][t] = list(blend_m.head(N).index)
    print(f'{y}: clf+ranker trained ({len(tr)} grids) -> {len(te)} grids', flush=True)

class MapInputs(pc.Inputs):
    pmap = None
    def picks(self, t, n, size_range=(0.05, 0.30), min_adv=5e6, exclude=(), factor='x'):
        return list((self.pmap or {}).get(t, [])[:n])

def stats(eq):
    eq = eq.dropna()
    out = {'total': round(float(eq.iloc[-1] / eq.iloc[0] - 1) * 100, 2),
           'mdd': round(float((eq / eq.cummax() - 1).min()) * 100, 2)}
    for w, d in {'1m': 21, '3m': 63, '6m': 126, '1y': 252, '2y': 504, '3y': 756}.items():
        sub = eq.tail(d + 1)
        out[w] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
        out[w + '_mdd'] = round(float((sub / sub.cummax() - 1).min()) * 100, 2)
    return out

base = pc.Inputs(piv)
KW = dict(n=N, rebal=REBAL, take=0.80, stop=0.25, stop_exec='next', exclude=MB,
          capital=50000.0, lot=100, cost_one_way=None, slip=0.002,
          run_start=RUN_START, eval_start=grids[0], eval_end=EVAL_END,
          phase=0, legacy_grid=False, full_liquidate=True, exposure=0.9, factor='amihud_60')
res = {'baseline_B': {**stats(pc.run_strategy(base, **KW).eq)}}
rb = pc.run_strategy(base, **KW)
res['baseline_B'] = {**stats(rb.eq), 'trades': len(rb.trades), 'cost': round(float(rb.meta['total_cost']), 0)}
for k in ('VETO', 'BLEND', 'BLEND_MAX'):
    mi = MapInputs(piv); mi.pmap = P[k]
    r = pc.run_strategy(mi, **KW)
    res[k] = {**stats(r.eq), 'trades': len(r.trades), 'cost': round(float(r.meta['total_cost']), 0)}
    r.eq.dropna().to_pickle(ROOT / 'results' / 'r30_bt' / f'xgb_v3_{k}_equity.pkl')
res['importance_clf'] = imp_clf
res['importance_rank'] = imp_rank
open(ROOT / 'results' / 'r30_bt' / 'xgb_v3.json', 'w').write(json.dumps(res, ensure_ascii=False, indent=1))
print(json.dumps({k: v for k, v in res.items() if not k.startswith('importance')}, ensure_ascii=False, indent=1))
print('saved xgb_v3', flush=True)
