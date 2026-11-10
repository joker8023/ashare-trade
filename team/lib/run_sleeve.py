"""
team/lib/run_sleeve.py — C5 三 sleeve（相位错开）合成净值
=======================================================
口径（按 specs/batch_003.json 的 notes 与 extensions P0-9）：
  * 三个 sleeve = 同一 spec 在 phase offset ∈ {-8, 0, +8} 各跑一次（各自独立再投资，起始净值 1.0）
  * 合成净值 = 三份日净值**算术平均**（等价于资金三等分、每份 1/3）
  * win_period 用**合成净值**按 R=30 的 phase-0 网格边界算完整段（不按 sleeve 平均）
  * 另报每个 sleeve 自己的 total/mdd/win_period 与 max-min（sleeve_dispersion）
  * win_trade = 三份全部个股交易合并计算

用法：python team/lib/run_sleeve.py
输出：team/runs/batch_003_sleeve.csv / batch_003_sleeve.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
TEAM = HERE.parent
sys.path.insert(0, str(TEAM))

import harness as H              # noqa: E402


def composite_metrics(spec: dict, offsets=(-8, 0, 8)) -> dict:
    cfg = H.normalize_spec(spec)
    sims = []
    for off in offsets:
        c = H.with_overrides(cfg, phase=off)
        sims.append(H.simulate(c))

    nD = len(sims[0]["eq_full"])
    mats = []
    for s in sims:
        e = s["eq_full"].copy()
        e[~np.isfinite(e)] = 1.0          # 未开始/未模拟的日期 = 现金 1.0
        mats.append(e)
    comp = np.mean(mats, axis=0)

    def _mean_attr(key):
        out = np.full(nD, np.nan)
        for s in sims:
            a = np.asarray(s[key], dtype=float)
            out = np.where(np.isfinite(out), out, 0.0) + np.where(np.isfinite(a), a, 0.0)
        return out / len(sims)

    synth = dict(cfg=cfg, eq_full=comp,
                 cost_full=_mean_attr("cost_full"),
                 expo_full=_mean_attr("expo_full"),
                 nhold_full=_mean_attr("nhold_full"),
                 starhold_full=_mean_attr("starhold_full"),
                 rebal=sims[1]["rebal"],                    # phase=0 网格边界
                 trades=pd.concat([s["trades"] for s in sims if len(s["trades"])], ignore_index=True),
                 sim_start=min(s["sim_start"] for s in sims),
                 ev_end=sims[0]["ev_end"],
                 n_trigger=sum(s["n_trigger"] for s in sims),
                 n_deferred=sum(s["n_deferred"] for s in sims),
                 n_limit_down=sum(s["n_limit_down"] for s in sims),
                 anchor_first_date=sims[1].get("anchor_first_date", ""))
    m = H._window_metrics(synth, cfg["window"]["eval_start"], cfg["window"]["eval_end"],
                          "2025-12-31", cfg)
    out = {k: m.get(k) for k in ("total", "ann", "mdd", "win_period", "n_periods", "win_trade",
                                 "n_trades", "win_month", "n_months", "vol", "sharpe",
                                 "calmar", "exposure", "cost_paid_pct", "last_partial_ret",
                                 "block30_win", "n_blocks", "top3_pnl_share",
                                 "max_single_name_pnl_share")}
    out["monthly_2026"] = "|".join(f"{k}:{v:.4f}" for k, v in m.get("months", {}).items())

    sleeves = []
    for off, s in zip(offsets, sims):
        mm = H._window_metrics(s, cfg["window"]["eval_start"], cfg["window"]["eval_end"],
                               "2025-12-31", cfg)
        sleeves.append(dict(offset=off, total=mm["total"], mdd=mm["mdd"],
                            win_period=mm["win_period"], n_periods=mm["n_periods"],
                            win_trade=mm["win_trade"]))
    sd = pd.DataFrame(sleeves)
    out["sleeve_dispersion"] = float(sd["total"].max() - sd["total"].min())
    out["sleeve_mdd_worst"] = float(sd["mdd"].min())
    out["sleeves"] = sleeves
    out["id"] = spec.get("id", "sleeve")
    return out


def main():
    spec = [s for s in json.load(open(TEAM / "specs" / "batch_003.json"))
            if "sleeves" in (s.get("portfolio") or {})][0]
    m = composite_metrics(spec)
    df_sl = pd.DataFrame(m.pop("sleeves"))
    pd.DataFrame([{k: v for k, v in m.items()}]).to_csv(
        TEAM / "runs" / "batch_003_sleeve.csv", index=False)
    df_sl.to_csv(TEAM / "runs" / "batch_003_sleeve_parts.csv", index=False)

    L = ["# C5 三 sleeve（相位错开 -8 / 0 / +8）合成净值\n",
         f"- spec：`{m['id']}`（N5 / TP50 / 主板 / exposure 0.90 / R30 / 0.5%每边）",
         "- 合成净值 = 三份日净值算术平均；win_period 用合成净值按 R=30 phase-0 边界算完整段",
         "",
         "## 合成结果（2026-01-05~2026-11-04，基数 2025-12-31）",
         "",
         "| total | ann | mdd | win_period | n_periods | win_trade | n_trades | win_month | last_partial | exposure | cost_paid |",
         "|---|---|---|---|---|---|---|---|---|---|---|",
         f"| **{m['total']*100:+.2f}%** | {m['ann']*100:+.1f}% | {m['mdd']*100:+.2f}% | "
         f"{m['win_period']*100:.1f}% | {int(m['n_periods'])} | {m['win_trade']*100:.1f}% | "
         f"{int(m['n_trades'])} | {m['win_month']*100:.0f}% | {m['last_partial_ret']*100:+.2f}% | "
         f"{m['exposure']:.3f} | {m['cost_paid_pct']:.2f}% |",
         "",
         "## 每个 sleeve",
         "",
         "| offset | total | mdd | win_period | n_periods | win_trade |",
         "|---|---|---|---|---|---|"]
    for _, r in df_sl.iterrows():
        L.append(f"| {int(r['offset']):+d} | {r['total']*100:+.2f}% | {r['mdd']*100:+.2f}% | "
                 f"{r['win_period']*100:.0f}% | {int(r['n_periods'])} | {r['win_trade']*100:.1f}% |")
    L += ["", f"- sleeve dispersion（total max-min）= **{m['sleeve_dispersion']*100:.2f}pp**",
          f"- 最差 sleeve mdd = {m['sleeve_mdd_worst']*100:+.2f}%",
          "", "## 逐月（2026）", "", m["monthly_2026"].replace("|", "  "), "", "## 限制"]
    L += [f"- {x}" for x in H.LIMITATIONS]
    (TEAM / "runs" / "batch_003_sleeve.md").write_text("\n".join(L), encoding="utf-8")
    print(json.dumps({k: v for k, v in m.items() if k != "sleeves"}, ensure_ascii=False, indent=1))
    print(df_sl.to_string())
    return m


if __name__ == "__main__":
    main()
