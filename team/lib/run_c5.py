"""
team/lib/run_c5.py — C5 三 sleeve 官方分析（Lead 追加要求 1-5）
==============================================================
配置：
  · C5-N5-e90  : amihud_60 N5 R30 TP50 主板、每 sleeve exposure 0.90（strategist 骨架）
  · C5-N6-e100 : N6、每 sleeve 满仓（Lead 指定）
  · C5-N6-e90  : N6、每 sleeve 0.90
每个配置输出：
  1) 合成净值 total/mdd/win_period/win_month/win_trade/block30 + top1/top3 PnL 占比（三份 trades 合并）
  2) 剔除 PnL Top3 → exclude_codes 重跑 3 sleeve 再合成
  3) realistic 成本版（5 万三等分，每份 16,667，100 股整手）
  4) 5 相位表（phase p 时 sleeve offset = p-8 / p / p+8）
  5) equity/trades 明细落地
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

WIN = ("2026-01-05", "2026-11-04")


def mk(n, exposure, cost_mode="fixed", capital=50000.0, exclude=(), sid="", phase=0):
    return dict(
        id=sid or f"C5_N{n}_e{int(round(exposure*100))}_{cost_mode}",
        selector=dict(type="amihud_60", n=n, size_range=[0.05, 0.30], min_adv=5e6,
                      exclude_star=True, exclude_bj=True, exclude_chinext=True,
                      exclude_codes=list(exclude)),
        rebalance_days=30,
        exit=dict(take_profit=0.50, stop_exec="next"),
        timing=dict(type="none"),
        cost=dict(mode=cost_mode, one_way=0.005, capital=capital, lot_size=100),
        portfolio=dict(exposure=exposure, sleeves=dict(offsets=[-8, 0, 8])),
        window=dict(warmup_start="2024-01-01", eval_start=WIN[0], eval_end=WIN[1]),
        phase=phase)


def net(spec, **kw):
    cfg = H.normalize_spec(spec)
    for k, v in kw.items():
        if k in ("window", "cost"):
            cfg = H.with_overrides(cfg, **{k: v})
        else:
            cfg = H.with_overrides(cfg, **{k: v})
    return cfg


def one(spec, detail=False, warmup=None):
    cfg = H.normalize_spec(dict(spec))
    if warmup:
        cfg = H.with_overrides(cfg, window={"warmup_start": warmup})
    sim = H.run_sim(cfg)
    m = H._window_metrics(sim, cfg["window"]["eval_start"], cfg["window"]["eval_end"],
                          "2025-12-31", cfg)
    tr = sim["trades"]
    # 只统计 **2026 窗口内平仓** 的交易（与 harness 的 top3_pnl_share 口径一致）
    if len(tr):
        b = H.bundle(); sp0 = int(np.searchsorted(b.dates, pd.Timestamp(cfg["window"]["eval_start"]), "left"))
        ep0 = int(np.searchsorted(b.dates, pd.Timestamp(cfg["window"]["eval_end"]), "right") - 1)
        trw = tr[(tr["exit_pos"] >= sp0) & (tr["exit_pos"] <= ep0)]
    else:
        trw = tr
    by = trw.groupby("code")["pnl"].sum().sort_values(ascending=False) if len(trw) else pd.Series(dtype=float)
    tot = float(by.sum()) if len(by) else 0.0
    d = {k: m.get(k) for k in ("total", "ann", "mdd", "win_period", "n_periods", "win_trade",
                               "n_trades", "win_month", "block30_win", "n_blocks", "vol",
                               "sharpe", "exposure", "cost_paid_pct", "n_hold_avg",
                               "n_hold_max", "n_distinct_names", "top3_pnl_share",
                               "max_single_name_pnl_share", "last_partial_ret")}
    d.update(top1_code=(by.index[0] if len(by) else ""), top1_share=float(by.iloc[0] / tot) if tot > 0 else float("nan"),
             top3_codes=list(by.index[:3]) if len(by) else [], top3_share=float(by.iloc[:3].sum() / tot) if tot > 0 else float("nan"))
    d["monthly"] = "|".join(f"{k}:{v:.4f}" for k, v in m.get("months", {}).items())
    if detail:
        eq = pd.DataFrame({"date": sim["equity"].index, "equity": sim["equity"].to_numpy()})
        d["equity"], d["trades"] = eq, tr
    return d


def fmt(x, pct=True, nd=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x*100:+.{nd}f}%" if pct else f"{x:.{nd}f}"


def main():
    (RUNS / "batch_003_sleeve_equity").mkdir(exist_ok=True)
    (RUNS / "batch_003_sleeve_trades").mkdir(exist_ok=True)
    cfglist = [("C5-N5-e90", 5, 0.90), ("C5-N6-e100", 6, 1.00), ("C5-N6-e90", 6, 0.90)]
    rows, L = [], []
    L.append("# C5 三 sleeve 官方分析（offsets -8 / 0 / +8，资金三等分）\n")
    L.append("- 合成净值 = 三份日净值算术平均（每份 1/3 资金、各自独立再投资）；"
             "`win_period` 用合成净值按 R=30 phase-0 边界算完整段（6 段）")
    L.append("- 主口径 `stop_exec=next`、TP50、主板（exclude_star/bj/chinext 全 true）、成本 0.5%/边")
    L.append("- `top3 PnL 占比` = 三份 trades 合并后，P&L 贡献最大的 3 只股票 / 总 P&L")
    L.append("- `block30` = 2026 窗口按 30 个交易日切块（最后一块 ≥10 日）的胜率\n")

    for name, n, expo in cfglist:
        base = one(mk(n, expo, sid=name), detail=True)
        # 明细落地
        base["equity"].to_csv(RUNS / "batch_003_sleeve_equity" / f"{name}.csv", index=False)
        base["trades"].to_csv(RUNS / "batch_003_sleeve_trades" / f"{name}.csv", index=False)

        top3 = base["top3_codes"]
        ex = one(mk(n, expo, exclude=top3, sid=name + "_exTop3"))
        exF = one(mk(n, expo, exclude=top3, sid=name + "_exTop3"), warmup=WIN[0])
        real = one(mk(n, expo, cost_mode="realistic", capital=50000 / 3, sid=name + "_real"))
        realF = one(mk(n, expo, cost_mode="realistic", capital=50000 / 3, sid=name + "_real"), warmup=WIN[0])
        fresh = one(mk(n, expo, sid=name), warmup=WIN[0])

        phases = []
        for ph in (-10, -5, 0, 5, 10):
            r = one(mk(n, expo, sid=f"{name}_ph{ph:+d}", phase=ph))
            ok = (r["total"] >= 0.60) and (r["mdd"] >= -0.15) and (r["win_period"] or 0) >= 0.80
            phases.append(dict(phase=ph, total=r["total"], mdd=r["mdd"],
                               win_period=r["win_period"], win_trade=r["win_trade"],
                               fresh=r["total"] if False else None, pass3=bool(ok)))
        pass_n = sum(p["pass3"] for p in phases)

        row = dict(config=name, n=n, exposure=expo, top1=base["top1_share"], top3=base["top3_share"],
                   total=base["total"], mdd=base["mdd"], win_period=base["win_period"],
                   win_trade=base["win_trade"], win_month=base["win_month"],
                   block30=base["block30_win"], fresh=fresh["total"],
                   ex_top3_total=ex["total"], ex_top3_mdd=ex["mdd"],
                   ex_top3_wp=ex["win_period"], ex_top3_wt=ex["win_trade"], ex_top3_fresh=exF["total"],
                   real_total=real["total"], real_mdd=real["mdd"], real_wp=real["win_period"],
                   real_fresh=realF["total"], real_nhold=real["n_hold_avg"],
                   n_hold_avg=base["n_hold_avg"], n_distinct=base["n_distinct_names"],
                   phase_pass=pass_n, sleeve_dispersion=None)
        rows.append(row)

        L.append(f"## {name}：N{n} / TP50 / 主板 / 每份 exposure {expo:.2f}\n")
        L.append("| 口径 | total | mdd | win_period | win_trade | win_month | block30 | fresh_2026 | top1 | top3 | n_hold | 不同标的 |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        L.append(f"| **合成（0.5%/边）** | **{fmt(base['total'])}** | **{fmt(base['mdd'],nd=2)}** | "
                 f"{(base['win_period'] or 0)*100:.1f}% ({int(round((base['win_period'] or 0)*base['n_periods']))}/{int(base['n_periods'])}) | "
                 f"{(base['win_trade'] or 0)*100:.1f}% | {(base['win_month'] or 0)*100:.0f}% | "
                 f"{(base['block30_win'] or 0)*100:.0f}% | {fmt(fresh['total'])} | "
                 f"{base['top1_share']*100:.1f}% | {base['top3_share']*100:.1f}% | "
                 f"{base['n_hold_avg']:.1f} | {int(base['n_distinct_names'])} |")
        L.append(f"| 剔除 Top3（{','.join(top3)}） | {fmt(ex['total'])} | {fmt(ex['mdd'],nd=2)} | "
                 f"{(ex['win_period'] or 0)*100:.1f}% | {(ex['win_trade'] or 0)*100:.1f}% | "
                 f"{(ex['win_month'] or 0)*100:.0f}% | — | {fmt(exF['total'])} | — | — | — | — |")
        L.append(f"| realistic（5万/3=16667 每份） | {fmt(real['total'])} | {fmt(real['mdd'],nd=2)} | "
                 f"{(real['win_period'] or 0)*100:.1f}% | {(real['win_trade'] or 0)*100:.1f}% | "
                 f"{(real['win_month'] or 0)*100:.0f}% | — | {fmt(realF['total'])} | — | — | "
                 f"{real['n_hold_avg']:.1f} | {int(real['n_distinct_names'])} |")
        L.append("")
        L.append("五相位（sleeve offset = phase-8 / phase / phase+8）：\n")
        L.append("| phase | total | mdd | win_period | win_trade | 三线全过 |")
        L.append("|---|---|---|---|---|---|")
        for p in phases:
            L.append(f"| {p['phase']:+d} | {fmt(p['total'])} | {fmt(p['mdd'],nd=2)} | "
                     f"{(p['win_period'] or 0)*100:.1f}% | {(p['win_trade'] or 0)*100:.1f}% | "
                     f"{'✅' if p['pass3'] else '❌'} |")
        L.append(f"\n→ phase_pass_count = **{pass_n}/5**\n")

    df = pd.DataFrame(rows)
    df.to_csv(RUNS / "batch_003_sleeve.csv", index=False)
    (RUNS / "batch_003_sleeve.md").write_text("\n".join(L), encoding="utf-8")
    print(df.to_string())
    return df


if __name__ == "__main__":
    main()
