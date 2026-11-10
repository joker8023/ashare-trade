"""R7-G：N4选股信号有效期事件研究（信号层，不含策略）。
问题：Alpha第几天最强/何时衰减/何时反转；R7换仓是卖早了还是买差了。
口径：amihud_60/N4/主板池（同策略），R7网格full300/ph0，2024-2026；
执行口径为主（t+1收盘起算），信号口径为辅；超额=篮子-同期pool等权。
"""
import sys
sys.path.insert(0, "team")
import numpy as np
import pandas as pd
from harness import bundle, picks_at, universe_matrix, normalize_spec

sel = dict(type="amihud_60", n=4, size_range=(0.05, 0.30), min_adv=5000000,
           exclude_star=True, exclude_bj=True, exclude_chinext=True)
cfg_sel = dict(type="amihud_60", n=4, size_range=[0.05, 0.30], min_adv=5000000,
               exclude_star=True, exclude_bj=True, exclude_chinext=True,
               exclude_codes=[], max_weight=None, rank_fill=True, params={},
               hold_exempt=None, absmom=None)
# 用 normalize 补全 n_eff 等字段
from harness import normalize_spec as _ns
_tmp = _ns(dict(selector=dict(type="amihud_60", n=4, size_range=[0.05, 0.30],
                              min_adv=5000000, exclude_star=True, exclude_bj=True,
                              exclude_chinext=True),
               rebalance_days=7, exit={}, timing=dict(type="none"),
               cost=dict(mode="fixed", one_way=0.0), rebalance_anchor="full300", phase=0))
SEL = _tmp["selector"]

b = bundle()
dates = b.dates
cf = b.close_ff_np
yg = (pd.Timestamp("2024-01-01"), pd.Timestamp("2026-11-04"))
t0 = int(np.searchsorted(dates, yg[0]))
t1 = int(np.searchsorted(dates, yg[1]))
grid = list(range(max(t0, b.offset + 300 - b.offset, 300), t1 - 31, 7))
um = universe_matrix(b, SEL)

rows = []
for t in grid:
    try:
        picks = picks_at(b, SEL, t).tolist()
    except Exception:
        continue
    if len(picks) < 4:
        continue
    prev = picks_at(b, SEL, t - 7).tolist() if t - 7 >= 0 else []
    mask = um[t]
    pool = np.flatnonzero(mask)
    # 可执行口径 t+1 起算；需 t+1..t+30 有效
    if t + 30 >= len(dates):
        continue
    base_px = cf[t + 1]
    px0 = base_px[picks]
    if not np.all(np.isfinite(px0)) or np.any(px0 <= 0):
        continue
    out = dict(date=str(dates[t].date()), n_pool=int(mask.sum()))
    fwd = {}
    for h in [1, 2, 3, 5, 7, 10, 14, 21, 30]:
        pxh = cf[t + 1 + h] if t + 1 + h < len(dates) else cf[-1]
        r_new = np.nanmean([pxh[j] / base_px[j] - 1.0 for j in picks if np.isfinite(pxh[j]) and base_px[j] > 0])
        # pool 等权同期收益
        rp = []
        for j in pool:
            if np.isfinite(base_px[j]) and base_px[j] > 0 and np.isfinite(pxh[j]):
                rp.append(pxh[j] / base_px[j] - 1.0)
        r_pool = float(np.nanmean(rp)) if rp else np.nan
        # old 篮子同期
        if prev and all(np.isfinite(base_px[j]) and base_px[j] > 0 for j in prev):
            r_old = np.nanmean([pxh[j] / base_px[j] - 1.0 for j in prev if np.isfinite(pxh[j])])
        else:
            r_old = np.nan
        out["new_%d" % h] = float(r_new) if r_new == r_new else None
        out["pool_%d" % h] = r_pool
        out["old_%d" % h] = float(r_old) if r_old == r_old else None
    rows.append(out)

df = pd.DataFrame(rows)
df.to_csv("team/runs/batch_032_r7g_events.csv", index=False)
print("events:", len(df), flush=True)
xs = lambda c, p: (pd.to_numeric(df[c], errors="coerce") - pd.to_numeric(df[p], errors="coerce"))
print("=== 平均累计超额 new-pool (可执行口径) ===", flush=True)
for h in [1, 2, 3, 5, 7, 10, 14, 21, 30]:
    s = xs("new_%d" % h, "pool_%d" % h).dropna()
    print("h=%2d  mean=%+.4f  med=%+.4f  hit=%.3f  n=%d" % (
        h, s.mean(), s.median(), float((s > 0).mean()), len(s)), flush=True)
print("=== new-old 差（换仓增值？） ===", flush=True)
for h in [7, 14, 21, 30]:
    s = (pd.to_numeric(df["new_%d" % h], errors="coerce") - pd.to_numeric(df["old_%d" % h], errors="coerce")).dropna()
    print("h=%2d  mean=%+.4f  med=%+.4f  hit=%.3f" % (h, s.mean(), s.median(), float((s > 0).mean())), flush=True)
print("=== 按年：new超额 h=7/14/30 ===", flush=True)
df["yr"] = pd.to_datetime(df["date"]).dt.year
for y in [2024, 2025, 2026]:
    d = df[df["yr"] == y]
    print("yr=%d n=%d" % (y, len(d)), {h: round(float((pd.to_numeric(d["new_%d" % h], errors="coerce") - pd.to_numeric(d["pool_%d" % h], errors="coerce")).mean()), 4) for h in [7, 14, 30]}, flush=True)
print("=== 集中度：累计超额 top10% 事件占比 ===", flush=True)
for h in [7, 30]:
    s = (pd.to_numeric(df["new_%d" % h], errors="coerce") - pd.to_numeric(df["pool_%d" % h], errors="coerce")).dropna().sort_values()
    tot = s.sum()
    print("h=%d total=%.4f top10%% share=%.3f neg%%=%.3f" % (h, tot, s.iloc[-max(1, len(s)//10):].sum()/tot if tot != 0 else None, float((s < 0).mean())), flush=True)
print("=== DONE ===", flush=True)
