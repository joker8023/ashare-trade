"""H3 信号层测算：买时 max_weight 对 N4 无效（0.25<cap 恒不触发，见 harness 买入段），
故检验漂移上限的可行性：同批 4 票 30 天内 buy-and-hold（含漂移）vs 每日等权再平衡（去漂移），
差值即漂移贡献；若漂移贡献为正，限漂移将直接砍 alpha，H3 不应立项。
R30 网格 full300/ph0，2024-2026，可执行口径 t+1 起算，pool 等权为基准。零策略回测。
"""
import sys
sys.path.insert(0, "team")
import numpy as np
import pandas as pd
from harness import bundle, picks_at, universe_matrix, normalize_spec as _ns

_tmp = _ns(dict(selector=dict(type="amihud_60", n=4, size_range=[0.05, 0.30],
                              min_adv=5000000, exclude_star=True, exclude_bj=True,
                              exclude_chinext=True),
               rebalance_days=30, exit={}, timing=dict(type="none"),
               cost=dict(mode="fixed", one_way=0.0), rebalance_anchor="full300", phase=0))
SEL = _tmp["selector"]
b = bundle()
dates, cf = b.dates, b.close_ff_np
yg = (pd.Timestamp("2024-01-01"), pd.Timestamp("2026-11-04"))
t0 = int(np.searchsorted(dates, yg[0]))
t1 = int(np.searchsorted(dates, yg[1]))
grid = list(range(max(t0, 300), t1 - 31, 30))
um = universe_matrix(b, SEL)
rows = []
for t in grid:
    try:
        picks = picks_at(b, SEL, t).tolist()
    except Exception:
        continue
    if len(picks) < 4:
        continue
    mask = um[t]
    pool = np.flatnonzero(mask)
    if t + 31 >= len(dates):
        continue
    bpx = cf[t + 1]
    if not all(np.isfinite(bpx[j]) and bpx[j] > 0 for j in picks):
        continue
    # 逐日路径（30 天）
    P = cf[t + 1:t + 32][:, picks]
    if not np.all(np.isfinite(P)):
        continue
    per = P[-1] / P[0] - 1.0
    # pool 同期 BH
    Q = cf[t + 1:t + 32][:, pool]
    with np.errstate(invalid="ignore"):
        qp = Q[-1] / Q[0] - 1.0
    qp = qp[np.isfinite(qp)]
    if len(qp) == 0:
        continue
    r_pool = float(np.mean(qp))
    bh = float(np.mean(per))
    # 每日等权再平衡（无摩擦理论值）
    dr = P[1:] / P[:-1] - 1.0
    ew = float(np.prod(1.0 + np.mean(dr, axis=1)) - 1.0)
    o = np.argsort(-per)
    top1 = float(per[o[0]] - r_pool)
    rows.append(dict(date=str(dates[t].date()), bh_xs=bh - r_pool, ew_xs=ew - r_pool,
                     drift=bh - ew, top1_xs=top1, top1_share=(per[o[0]] - r_pool) / (bh - r_pool) if (bh - r_pool) != 0 else None))
df = pd.DataFrame(rows)
df.to_csv("team/runs/batch_033_h3_signal.csv", index=False)
print("events:", len(df), flush=True)
for c in ["bh_xs", "ew_xs", "drift", "top1_xs"]:
    s = pd.to_numeric(df[c], errors="coerce").dropna()
    print("%s mean=%+.4f med=%+.4f hit=%.3f" % (c, s.mean(), s.median(), float((s > 0).mean())), flush=True)
t1s = pd.to_numeric(df["top1_share"], errors="coerce").dropna()
t1s = t1s[np.isfinite(t1s)]
print("top1_share mean=%.3f med=%.3f frac>0.5=%.3f frac>1=%.3f" % (
    t1s.mean(), t1s.median(), float((t1s > 0.5).mean()), float((t1s > 1.0).mean())), flush=True)
print("=== DONE ===", flush=True)
