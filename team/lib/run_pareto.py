"""
team/lib/run_pareto.py — batch_006 的 fresh 口径帕累托前沿 + 4 风险画像
=====================================================================
主口径（唯一判定口径，Round 3 起）：
  2026-01-05 空仓起步（基数 1.0）、现实费率（佣金 0.025% 最低 5 + 卖出印花 0.05% + 过户 0.001%
  + 滑点 0.2%/边）、50,000 元 / 100 股整手、只做多无杠杆、t+1 收盘执行。

非支配维度（全部越大越好）：
  fresh_total, fresh_mdd（越接近 0 越好）, fresh_win_period, fresh_win_month, fresh_win_trade

4 个风险画像（各 Top3）：
  收益型     max fresh_total
  均衡型     max fresh_total/|fresh_mdd|，且 fresh_win_period ≥ 70%
  稳健型     max fresh_win_month，且 fresh_mdd ≥ -8%（total 不设硬门槛）
  高胜率型   max min(win_period, win_month, win_trade)，且 fresh_total ≥ 15%

输出：team/runs/batch_006_pareto.csv + team/runs/batch_006_pareto.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
TEAM = HERE.parent
RUNS = TEAM / "runs"
sys.path.insert(0, str(TEAM))

import harness as H              # noqa: E402

DIMS = ["fresh_total", "fresh_mdd", "fresh_win_period", "fresh_win_month", "fresh_win_trade"]
DIM_LABEL = dict(fresh_total="2026 收益", fresh_mdd="最大回撤", fresh_win_period="段胜率",
                 fresh_win_month="月胜率", fresh_win_trade="按笔胜率")
PROFILES = [
    ("收益型", "max fresh_total", "fresh_total"),
    ("均衡型", "max fresh_total/|fresh_mdd|（wp≥70%）", "calmar_fresh"),
    ("稳健型", "max fresh_win_month（mdd≥-8%）", "fresh_win_month"),
    ("高胜率型", "max min(wp,wm,wt)（total≥15%）", "min_hit"),
]


def pareto_rank(df: pd.DataFrame) -> np.ndarray:
    """非支配排序：返回每行的 Pareto 前沿层级（1 = 第一前沿）。"""
    M = df[DIMS].to_numpy(dtype=float)
    n = len(M)
    rank = np.full(n, -1, dtype=int)
    remaining = np.ones(n, dtype=bool)
    level = 1
    while remaining.any():
        idx = np.flatnonzero(remaining)
        sub = M[idx]
        # 支配矩阵：sub[i] 是否支配 sub[j]
        ge = np.all(sub[:, None, :] >= sub[None, :, :], axis=2)
        gt = np.any(sub[:, None, :] > sub[None, :, :], axis=2)
        dom = ge & gt
        nondom = ~dom.any(axis=0)          # 没被任何点支配
        rank[idx[nondom]] = level
        remaining[idx[nondom]] = False
        level += 1
        if level > 50:
            rank[remaining] = level
            break
    return rank


def main(tag: str = "006"):
    p_csv = RUNS / f"batch_{tag}_results.csv"
    df = pd.read_csv(p_csv)
    if "status" in df.columns:
        df = df[df["status"] != "error"].copy()
    df = df.reset_index(drop=True)

    for c in DIMS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["fresh_total", "fresh_mdd"]).reset_index(drop=True)
    df["fresh_win_period"] = df["fresh_win_period"].fillna(0.0)
    df["fresh_win_month"] = df["fresh_win_month"].fillna(0.0)
    df["fresh_win_trade"] = df["fresh_win_trade"].fillna(0.0)
    df["calmar_fresh"] = (df["fresh_calmar_raw"] if "fresh_calmar_raw" in df.columns
                      else df["fresh_total"] / df["fresh_mdd"].abs().clip(lower=1e-6))
    df["min_hit"] = df[["fresh_win_period", "fresh_win_month", "fresh_win_trade"]].min(axis=1)
    df["pareto_rank"] = pareto_rank(df)
    df["is_front1"] = df["pareto_rank"] == 1

    # ---- 4 画像 ----
    picks = {}
    m = df
    picks["收益型"] = m.sort_values("fresh_total", ascending=False).head(3)
    m2 = m[m["fresh_win_period"] >= 0.70]
    picks["均衡型"] = (m2 if len(m2) else m).sort_values("calmar_fresh", ascending=False).head(3)
    m3 = m[(m["fresh_mdd"] >= -0.08)]
    picks["稳健型"] = (m3 if len(m3) else m).sort_values(
        ["fresh_win_month", "fresh_mdd"], ascending=[False, False]).head(3)
    m4 = m[m["fresh_total"] >= 0.15]
    picks["高胜率型"] = (m4 if len(m4) else m).sort_values("min_hit", ascending=False).head(3)

    # 画像命中标记
    for name, _, _ in PROFILES:
        ids = set(picks[name]["id"])
        df[f"profile_{name}"] = df["id"].isin(ids)

    cols = ["id", "group", "selector", "n", "R", "exit", "timing", "max_weight", "staged_take",
            "vol_target", "exposure_target", "phase", "n_sleeves",
            "fresh_total", "fresh_mdd", "fresh_win_period", "fresh_n_periods", "fresh_win_month",
            "fresh_win_trade", "fresh_n_trades", "fresh_calmar_raw", "fresh_calmar_ann",
            "fresh_top3_pnl_share", "fresh_n_picks_avg",
            "fresh_top1_pnl_share", "fresh_exposure", "fresh_n_hold_avg", "fresh_n_picks_avg", "n_picks_avg", "fresh_n_distinct",
            "fresh_cost_paid_pct", "fresh_block30_win", "calmar_fresh", "min_hit",
            "pareto_rank", "is_front1", "fresh_phase_pass", "phase_pass_count", "flags",
            "fresh_monthly", "notes"]
    cols = [c for c in cols if c in df.columns]
    out = df.sort_values(["pareto_rank", "fresh_total"], ascending=[True, False])[cols]
    out.to_csv(RUNS / f"batch_{tag}_pareto.csv", index=False)

    L = []
    A = L.append
    A(f"# batch_{tag} — fresh 口径帕累托前沿与 4 风险画像\n")
    A("**唯一主口径**：2026-01-05 空仓起步（基数 1.0）→ 2026-11-04；现实费率"
      "（佣金 0.025% 最低 5 元 + 卖出印花 0.05% + 过户 0.001% + **滑点 0.2%/边**）；"
      "50,000 元 / 100 股整手；只做多、无杠杆；t+1 收盘执行；调仓网格 `dates[300]` 排到数据末端、phase 0。")
    A(f"\n- 参与排序的 spec：**{len(df)}** 条（排除 error/缺 fresh 指标）")
    A(f"- 第一前沿（非支配）：**{int(df['is_front1'].sum())}** 条；第二前沿 {int((df['pareto_rank']==2).sum())} 条")
    A(f"- 非支配维度：{' / '.join(DIM_LABEL[d] for d in DIMS)}（全部越大越好，mdd 越接近 0 越好）")
    A("")
    A("## 1. 四个风险画像 Top3\n")
    for name, rule, key in PROFILES:
        A(f"### {name}（{rule}）\n")
        A("| # | id | fresh_total | fresh_mdd | 段胜率 | 月胜率 | 按笔 | n_trades | Calmar | top3 | 敞口 | 实际持仓 | fresh_phase_pass |")
        A("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for i, (_, r) in enumerate(picks[name].iterrows(), 1):
            A(f"| {i} | `{r['id']}` | {r['fresh_total']*100:+.2f}% | {r['fresh_mdd']*100:+.2f}% | "
              f"{r['fresh_win_period']*100:.0f}% ({int(round(r['fresh_win_period']*r['fresh_n_periods']))}/{int(r['fresh_n_periods'])}) | "
              f"{r['fresh_win_month']*100:.0f}% | {r['fresh_win_trade']*100:.1f}% | {int(r['fresh_n_trades'])} | "
              f"{r.get('fresh_calmar_raw', r['fresh_total']/abs(r['fresh_mdd'])):.2f} | {r['fresh_top3_pnl_share']*100:.1f}% | {r['fresh_exposure']:.2f} | "
              f"{r.get('fresh_n_hold_avg', float('nan')):.1f}/{r.get('fresh_n_picks_avg', r.get('n_picks_avg', float('nan'))):.1f} | "
              f"{int(r['fresh_phase_pass']) if pd.notna(r.get('fresh_phase_pass')) else '—'}/5 |")
        A("")

    A("## 2. 第一前沿全部条目（按 fresh_total 降序）\n")
    A("| id | fresh_total | fresh_mdd | 段胜率 | 月胜率 | 按笔 | top3 | 敞口 | 持仓 |")
    A("|---|---|---|---|---|---|---|---|---|")
    for _, r in df[df["is_front1"]].sort_values("fresh_total", ascending=False).iterrows():
        A(f"| `{r['id']}` | {r['fresh_total']*100:+.1f}% | {r['fresh_mdd']*100:+.1f}% | "
          f"{r['fresh_win_period']*100:.0f}% | {r['fresh_win_month']*100:.0f}% | "
          f"{r['fresh_win_trade']*100:.0f}% | {r['fresh_top3_pnl_share']*100:.1f}% | "
          f"{r['fresh_exposure']:.2f} | {r.get('fresh_n_hold_avg', float('nan')):.1f} |")
    A("")
    A("## 3. 分布\n")
    for c in DIMS:
        q = df[c].quantile([0.1, 0.5, 0.9])
        A(f"- {DIM_LABEL[c]}：p10 {q.iloc[0]*100:+.1f}% / 中位 {q.iloc[1]*100:+.1f}% / p90 {q.iloc[2]*100:+.1f}%")
    A("")
    A("## 4. 口径与限制\n")
    A("- fresh = 2026-01-05 空仓起步；首个调仓日由固定相位决定（R30 = 2026-01-23 信号 / 01-26 建仓），"
      "之前为现金 → 年初 14 个交易日不计入收益，这是可实施口径的代价。")
    for x in H.LIMITATIONS:
        A(f"- {x}")
    (RUNS / f"batch_{tag}_pareto.md").write_text("\n".join(L), encoding="utf-8")
    print(f"[pareto] {len(df)} specs, front1={int(df['is_front1'].sum())}")
    for name, _, _ in PROFILES:
        r = picks[name].iloc[0]
        r.get("fresh_phase_pass", None)
        print(f"  {name}: {r['id']}  total {r['fresh_total']:+.2%}  mdd {r['fresh_mdd']:+.2%}  "
              f"wp {r['fresh_win_period']:.2f} wm {r['fresh_win_month']:.2f} wt {r['fresh_win_trade']:.2f}")
    return df, picks


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "006")
