"""XGBoost 横截面选股原型 v1
 walk-forward: 每年用历史信号日重训一次, 预测当年各 R30 信号日截面, 取前 N 只.
 标签: 未来 30 交易日收益 (t+1 收盘 -> t+31 收盘, ffill 价).
 对比: 同网格/同成本下单引擎 B (Amihud60 前5, R30, TP80, stop25, 敞口0.9).
 口径: 2020 新浪 pivots_2020_clean, RUN_START=2023-01-03, EVAL_END=2026-11-12,
       现实费率+滑点0.002+整手, 5万本金. MB 剔除 (688/689/300/301/8/4).
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'team' / 'audit'))
import pandas as pd, numpy as np
import prior_check as pc

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

print('data:', dates[0].date(), '->', dates[-1].date(), c.shape, flush=True)

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
    turn = amt / cap.replace(0, np.nan)
    F['turn20'] = turn.rolling(20).mean()
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
print('features:', FEATS, flush=True)

grids = [dates[i] for i in range(300, len(dates) - 1, REBAL)]
print('grids:', len(grids), grids[0].date(), '->', grids[-1].date(), flush=True)

def pool_at(t):
    valid = (seasoned.loc[t] & (adv20.loc[t] > 5e6) & c.loc[t].notna()
             & F['amihud60'].loc[t].notna())
    cap_t = cap.loc[t]
    lo, hi = cap_t.quantile(0.05), cap_t.quantile(0.30)
    valid &= ((cap_t >= lo) & (cap_t <= hi)).fillna(False)
    cols = valid.index.to_series()
    valid &= ~cols.str.startswith(MB).values
    return valid[valid].index

def fwd_ret(t, code, h=30):
    i = dates.get_loc(t)
    j = min(i + 1 + h, len(dates) - 1)
    p0 = mark.iloc[i + 1][code]; p1 = mark.iloc[j][code]
    if pd.isna(p0) or p0 <= 0 or pd.isna(p1):
        return np.nan
    return p1 / p0 - 1

# 预计算 pool 与标签
pool_map, label_map = {}, {}
for t in grids:
    pool = pool_at(t)
    pool_map[t] = pool
    label_map[t] = pd.Series({s: fwd_ret(t, s) for s in pool}, dtype='float64')
print('pools ready, median size:', float(np.median([len(v) for v in pool_map.values()])), flush=True)

# walk-forward: 每年重训
from xgboost import XGBRegressor
test_grids = [t for t in grids if t >= pd.Timestamp(RUN_START)]
years = sorted(set(t.year for t in test_grids))
pred_map, imp_map = {}, {}
for y in years:
    tr = [t for t in grids if t < pd.Timestamp(f'{y}-01-01')]
    te = [t for t in test_grids if t.year == y]
    if len(tr) < 12 or not te:
        print(f'{y}: skip (train grids {len(tr)})', flush=True)
        for t in te:
            s = F['amihud60'].loc[t, pool_map[t]].sort_values(ascending=False)
            pred_map[t] = list(s.head(N).index)
        continue
    Xtr = pd.concat([pd.DataFrame({f: F[f].loc[t] for f in FEATS}).loc[pool_map[t]] for t in tr])
    ytr = pd.concat([label_map[t] for t in tr])
    m = (~Xtr.isna().any(axis=1)) & ytr.notna()
    # winsorize label 1%/99%
    yy = ytr[m].clip(ytr[m].quantile(0.01), ytr[m].quantile(0.99))
    XX = Xtr[m]
    # 中位数填充
    med = XX.median()
    XX = XX.fillna(med)
    model = XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05,
                         subsample=0.8, colsample_bytree=0.8, reg_lambda=5.0,
                         n_jobs=4, random_state=7)
    model.fit(XX.values, yy.values)
    imp_map[y] = dict(zip(FEATS, [float(x) for x in model.feature_importances_]))
    for t in te:
        Xt = pd.DataFrame({f: F[f].loc[t] for f in FEATS}).loc[pool_map[t]].fillna(med)
        pred = pd.Series(model.predict(Xt.values), index=Xt.index).sort_values(ascending=False)
        pred_map[t] = list(pred.head(N).index)
    print(f'{y}: trained on {len(tr)} grids/{m.sum()} rows -> predicted {len(te)} grids', flush=True)

# IC: 预测分 vs 未来收益的截面秩相关
ics = []
for t in test_grids:
    if t not in pred_map:
        continue
    Xt_all = pd.DataFrame({f: F[f].loc[t] for f in FEATS}).loc[pool_map[t]]
    # 用当年模型重算全截面分数? 简化: 用排名分数近似 IC 只对 topN 无意义 -> 跳过, 改算 Amihud IC 对照
    pass
# Amihud60 基准 IC
am_ics = []
for t in test_grids:
    a = F['amihud60'].loc[t, pool_map[t]]
    b = label_map[t]
    df = pd.DataFrame({'a': a, 'b': b}).dropna()
    if len(df) > 50:
        am_ics.append(float(df['a'].rank().corr(df['b'].rank())))
print(f'Amihud60 IC mean={np.mean(am_ics):.4f} std={np.std(am_ics):.4f} (n={len(am_ics)})', flush=True)

class XGBInputs(pc.Inputs):
    def picks(self, t, n, size_range=(0.05, 0.30), min_adv=5e6, exclude=(), factor='amihud'):
        return list(pred_map.get(t, [])[:n])

base = pc.Inputs(piv)
xgb = XGBInputs(piv)
KW = dict(n=N, rebal=REBAL, take=0.80, stop=0.25, stop_exec='next', exclude=MB,
          capital=50000.0, lot=100, cost_one_way=None, slip=0.002,
          run_start=RUN_START, eval_start=grids[0], eval_end=EVAL_END,
          phase=0, legacy_grid=False, full_liquidate=True, exposure=0.9, factor='amihud_60')

def stats(eq):
    eq = eq.dropna()
    tot = float(eq.iloc[-1] / eq.iloc[0] - 1) * 100
    mdd = float((eq / eq.cummax() - 1).min()) * 100
    out = {'total': round(tot, 2), 'mdd': round(mdd, 2)}
    for w, d in {'1m': 21, '3m': 63, '6m': 126, '1y': 252, '2y': 504, '3y': 756}.items():
        sub = eq.tail(d + 1)
        out[w] = round(float(sub.iloc[-1] / sub.iloc[0] - 1) * 100, 2)
        out[w + '_mdd'] = round(float((sub / sub.cummax() - 1).min()) * 100, 2)
    return out

rb = pc.run_strategy(base, **KW)
rx = pc.run_strategy(xgb, **KW)
res = {'baseline_B': {**stats(rb.eq), 'trades': len(rb.trades), 'cost': round(float(rb.meta['total_cost']), 0)},
       'xgb_top5': {**stats(rx.eq), 'trades': len(rx.trades), 'cost': round(float(rx.meta['total_cost']), 0)},
       'amihud_IC': {'mean': round(float(np.mean(am_ics)), 4), 'std': round(float(np.std(am_ics)), 4)},
       'importance': imp_map,
       'grids_tested': len(test_grids)}
print(json.dumps(res, ensure_ascii=False, indent=1))
open(ROOT / 'results' / 'r30_bt' / 'xgb_proto_v1.json', 'w').write(json.dumps(res, ensure_ascii=False, indent=1))
rx.eq.dropna().to_pickle(ROOT / 'results' / 'r30_bt' / 'xgb_proto_v1_equity.pkl')
print('saved xgb_proto_v1', flush=True)
