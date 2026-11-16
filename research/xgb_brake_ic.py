"""ML刹车第一步: IC验证. 市场状态特征 -> 未来20交易日最大dip(中证500).
 walk-forward按年重训, 只看样本外. 指标: IC(预测dip vs 实际dip秩相关),
 事件AUC(dip<-8%), 以及固定刹车(depth>=18%)的提前/滞后对比.
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'team' / 'audit'))
import pandas as pd, numpy as np
import risk_control as R

piv = pd.read_pickle(ROOT / 'data' / 'pivots_2020_clean.pkl')
c = piv['close']; amt = piv['amount']
dates = c.index
idx = {}
for code in ('000905', '000852', '000300'):
    s = R._index_series(code).loc[:dates[-1]].reindex(dates).ffill()
    idx[code] = s
print('index ready', flush=True)
m500, m1000, hs300 = idx['000905'], idx['000852'], idx['000300']
r500 = m500.pct_change(fill_method=None)

# --- 市场特征 (全部t日及以前) ---
F = pd.DataFrame(index=dates)
for n in (5, 10, 20, 60):
    F[f'r500_{n}'] = m500 / m500.shift(n) - 1
    F[f'r1000_{n}'] = m1000 / m1000.shift(n) - 1
    F[f'r300_{n}'] = hs300 / hs300.shift(n) - 1
F['vol500_20'] = r500.rolling(20).std() * np.sqrt(252)
F['gap15'] = m500 / m500.rolling(15).mean() - 1
F['gap20'] = m500 / m500.rolling(20).mean() - 1
F['gap60'] = m500 / m500.rolling(60).mean() - 1
ma20 = c.rolling(20).mean()
F['breadth'] = (c.gt(ma20)).mean(axis=1)
F['medret1'] = c.pct_change(fill_method=None).median(axis=1)
hi60 = c.rolling(60).max(); lo60 = c.rolling(60).min()
F['pct_high60'] = c.ge(hi60 * 0.999).mean(axis=1)
F['pct_low60'] = c.le(lo60 * 1.001).mean(axis=1)
F['dd60_500'] = m500 / m500.rolling(60).max() - 1
F['dd60_1000'] = m1000 / m1000.rolling(60).max() - 1
FEATS = list(F.columns)
print('features:', len(FEATS), flush=True)

# --- 标签: 未来20d最大dip (t+1起) ---
fwd_min = {}
px = m500.values
for i in range(len(dates) - 1):
    base = px[i + 1] if i + 1 < len(px) else np.nan
    win = px[i + 1:i + 21]
    fwd_min[dates[i]] = (np.nanmin(win) / base - 1) if len(win) and base and not np.isnan(base) else np.nan
Y = pd.Series(fwd_min)

from xgboost import XGBRegressor
start = pd.Timestamp('2023-01-03')
test_days = [d for d in dates if d >= start and d <= dates[-22]]
years = sorted(set(d.year for d in test_days))
pred = pd.Series(index=test_days, dtype=float)
imp = {}
for y in years:
    tr = [d for d in dates if d < pd.Timestamp(f'{y}-01-01') and d >= pd.Timestamp('2021-01-01')]
    te = [d for d in test_days if d.year == y]
    Xtr = F.loc[tr].dropna(); ytr = Y.loc[Xtr.index].dropna()
    Xtr = Xtr.loc[ytr.index]
    if len(Xtr) < 200 or not te:
        continue
    Xte = F.loc[te].reindex(columns=FEATS)
    med = Xtr.median()
    clf = XGBRegressor(n_estimators=300, max_depth=3, learning_rate=0.05,
                       subsample=0.8, colsample_bytree=0.8, reg_lambda=5.0,
                       n_jobs=4, random_state=7)
    clf.fit(Xtr.fillna(med).values, ytr.values)
    imp[y] = dict(zip(FEATS, [float(x) for x in clf.feature_importances_]))
    pred.loc[te] = clf.predict(Xte.fillna(med).values)
    print(f'{y}: train {len(Xtr)} -> pred {len(te)}', flush=True)

al = pd.DataFrame({'pred': pred, 'act': Y.loc[pred.index]}).dropna()
ic = float(al['pred'].rank().corr(al['act'].rank()))
print(f'OVERALL IC(pred dip, actual dip) = {ic:.4f} (n={len(al)})', flush=True)
for y in years:
    s = al[al.index.year == y]
    if len(s) > 30:
        print(f'  {y}: IC={float(s["pred"].rank().corr(s["act"].rank())):.4f} n={len(s)}', flush=True)
# 事件AUC: dip<-8%
from sklearn.metrics import roc_auc_score
for thr in (-0.05, -0.08, -0.10):
    ev = (al['act'] < thr).astype(int)
    if ev.sum() > 5 and ev.sum() < len(ev) - 5:
        print(f'event dip<{thr:.0%}: n={int(ev.sum())} AUC={roc_auc_score(ev, -al["pred"]):.4f}', flush=True)
# 与固定刹车对比: J04 brake ON日, 模型提前几天预警?
j = json.load(open(ROOT / 'results' / 'r30_bt' / 'J04_final.json'))
print('J04 brake_log:', j['brake_log'], flush=True)
al['warn'] = al['pred'] < -0.08
for d, tag, v in j['brake_log']:
    if tag == 'ON':
        dt = pd.Timestamp(d)
        pre = al.loc[:dt].tail(25)
        w = pre[pre['warn']]
        print(f'brake ON {d}: warned {len(w)}/25 days before, first warn: {w.index[0].date() if len(w) else None}', flush=True)
res = {'IC': round(ic, 4), 'n': len(al),
       'yearly_IC': {str(y): round(float(al[al.index.year == y]['pred'].rank().corr(al[al.index.year == y]['act'].rank())), 4) for y in years if (al.index.year == y).sum() > 30},
       'importance': imp}
open(ROOT / 'results' / 'r30_bt' / 'xgb_brake_ic.json', 'w').write(json.dumps(res, ensure_ascii=False, indent=1))
print(json.dumps({k: v for k, v in res.items() if k != 'importance'}, ensure_ascii=False), flush=True)
print('saved xgb_brake_ic', flush=True)
