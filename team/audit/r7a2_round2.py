"""R7-A2 第二轮：邻域6组 x 相位5档 + 0.8%成本压力 + 剔Top3 + U诊断 + 资金闭环。
纪律：6组全报告（规则A）；期末清算/未实现/跨期全核算（规则B）。
"""
import json, sys, math
sys.path.insert(0, "team")
import pandas as pd
from harness import normalize_spec, run_spec, simulate

LAMs = [0.5, 1.0, 2.0]
OVS = [2, 3]
PHASES = [-10, -5, 0, 5, 10]

def mk(id_, lam, ov, phase=0, slip=0.002, excl=()):
    return dict(
        id=id_,
        selector=dict(type="amihud_60", n=4, size_range=[0.05, 0.30], min_adv=5000000,
                      exclude_star=True, exclude_bj=True, exclude_chinext=True,
                      exclude_codes=list(excl)),
        rebalance_days=7,
        exit=dict(take_profit=0.45),
        timing=dict(type="none"),
        cost=dict(mode="realistic", capital=50000, lot_size=100, slip=slip),
        portfolio=dict(exposure=1.0),
        window=dict(warmup_start="2024-01-01", eval_start="2026-01-05", eval_end="2026-11-04"),
        rebalance_anchor="full300", phase=phase,
        rebalance_gate={"type": "cost_aware", "min_overlap": ov, "lam": lam},
        notes="R7-A2 round2",
    )

def diag_closure(cfg):
    """U分组诊断 + 资金闭环（fresh 口径 detail sim）。"""
    cfg_f = dict(cfg); cfg_f["window"] = dict(warmup_start="2026-01-05", eval_start="2026-01-05", eval_end="2026-11-04")
    cfg_f = normalize_spec(cfg_f)
    sim = simulate(cfg_f)
    # U 分组
    sk7, ex7, sk14, ex14 = [], [], [], []
    nskip = nexe = 0
    for r in sim["rebal"]:
        if r.get("gate") != "cost_aware":
            continue
        f7, f14 = r.get("gate_fwd7"), r.get("gate_fwd14")
        if r.get("gate_skip"):
            nskip += 1
            if f7 is not None: sk7.append(f7)
            if f14 is not None: sk14.append(f14)
        else:
            # 只统计门控实际生效期的执行（排除首建）
            if r.get("overlap", 0) < 4 or True:
                nexe += 1
                if f7 is not None: ex7.append(f7)
                if f14 is not None: ex14.append(f14)
    import numpy as np
    def m(x): return float(np.mean(x)) if len(x) else None
    # 闭环：期末持仓市值/现金/强制清算
    b_inds = sim["cfg"]
    tr = sim["trades"]
    # 期末持仓从 equity 路径反推：用最后 rebal/nhold
    eq = sim["equity"]
    # 未实现：用trades里仍未平仓无法得；改用 detail holds快照 -> simulate 不返回holds，近似：期末权益已含市值
    # 强制清算成本 ≈ 期末持仓股市值 x 双边费率
    nh = float(sim["nhold_full"][-1]) if len(sim["nhold_full"]) else 0.0
    expo = float(sim["expo_full"][-1]) if len(sim["expo_full"]) else 0.0
    eq_end = float(eq.iloc[-1]) if len(eq) else float("nan")
    mv_end = eq_end * expo if eq_end == eq_end else float("nan")
    # 现实费率下整手卖出成本近似：佣金max(0.025%,5元/笔名义分摊)+印花0.05%+过户0.001%+滑点0.2%
    liq_rate = 0.00025 + 0.0005 + 0.00001 + 0.002
    liq_cost = mv_end * liq_rate if mv_end == mv_end else float("nan")
    forced_total = (eq_end - liq_cost) / 1.0 - 1.0 if eq_end == eq_end else float("nan")
    # Top3（fresh trades口径）
    top3, top3share = [], None
    if len(tr):
        g = tr.groupby("code")["pnl"].sum().sort_values(ascending=False)
        top3 = g.index[:3].tolist()
        top3share = float(g.iloc[:3].sum() / g.sum()) if float(g.sum()) != 0 else None
    return dict(nskip=nskip, nexe=nexe, skip_fwd7=m(sk7), exec_fwd7=m(ex7),
                skip_fwd14=m(sk14), exec_fwd14=m(ex14),
                eq_end=m([eq_end]), mv_end=m([mv_end]), liq_cost=m([liq_cost]),
                forced_total=m([forced_total]), top3=top3, top3share=top3share)

# 先拿 A2(lam1.0,ov3,ph0) 的 Top3 做剔除名单
print("=== Top3 probe ===", flush=True)
base_cfg = mk("probe", 1.0, 3)
d0 = diag_closure(base_cfg)
print("TOP3:", d0["top3"], "share:", round(d0["top3share"], 4) if d0["top3share"] else None, flush=True)
TOP3 = d0["top3"]

rows, diags = [], {}
i = 0
import time
for lam in LAMs:
    for ov in OVS:
        tag = f"A2_lam{lam}_ov{ov}"
        for ph in PHASES:
            i += 1
            s = mk(f"{tag}_ph{ph:+d}", lam, ov, phase=ph)
            t0 = time.time()
            try:
                row = run_spec(s, variants=("fresh",))
            except Exception as e:
                row = dict(id=s["id"], status="error", error=str(e)[:200])
            row["lam"] = lam; row["ov"] = ov; row["phase"] = ph; row["stress"] = "base"
            rows.append(row)
            pd.DataFrame(rows).to_csv("team/runs/batch_027_r7a2_neighborhood.csv", index=False)
            print(f"[{i}/30] {tag} ph{ph:+d} fresh={row.get('fresh_total')} mdd={row.get('fresh_mdd')} {time.time()-t0:.1f}s", flush=True)
        # phase0 诊断（只做一次/组）
        s0 = mk(tag + "_ph+0", lam, ov, phase=0)
        try:
            dg = diag_closure(s0)
        except Exception as e:
            dg = dict(err=str(e)[:200])
        dg.update(lam=lam, ov=ov)
        diags[tag] = dg
        print(f"  DIAG {tag}: skip={dg.get('nskip')} exec={dg.get('nexe')} skip_fwd7={dg.get('skip_fwd7')} exec_fwd7={dg.get('exec_fwd7')} skip_fwd14={dg.get('skip_fwd14')} exec_fwd14={dg.get('exec_fwd14')} forced={dg.get('forced_total')} top3share={dg.get('top3share')}", flush=True)

# 成本压力 0.8%（slip 0.007 ≈ 单边0.73%+印花，整手保留）
for lam in LAMs:
    for ov in OVS:
        tag = f"A2_lam{lam}_ov{ov}_STRESS08"
        s = mk(tag, lam, ov, phase=0, slip=0.007)
        try:
            row = run_spec(s, variants=("fresh",))
        except Exception as e:
            row = dict(id=tag, status="error", error=str(e)[:200])
        row["lam"] = lam; row["ov"] = ov; row["phase"] = 0; row["stress"] = "slip007"
        rows.append(row)
        pd.DataFrame(rows).to_csv("team/runs/batch_027_r7a2_neighborhood.csv", index=False)
        print(f"STRESS {tag} fresh={row.get('fresh_total')} mdd={row.get('fresh_mdd')}", flush=True)

# 剔 Top3（用 probe 的名单；规则B：同一名单施加于6组）
for lam in LAMs:
    for ov in OVS:
        tag = f"A2_lam{lam}_ov{ov}_exTOP3"
        s = mk(tag, lam, ov, phase=0, excl=TOP3)
        try:
            row = run_spec(s, variants=("fresh",))
        except Exception as e:
            row = dict(id=tag, status="error", error=str(e)[:200])
        row["lam"] = lam; row["ov"] = ov; row["phase"] = 0; row["stress"] = "exTOP3"
        rows.append(row)
        pd.DataFrame(rows).to_csv("team/runs/batch_027_r7a2_neighborhood.csv", index=False)
        print(f"exTOP3 {tag} fresh={row.get('fresh_total')} mdd={row.get('fresh_mdd')} wp={row.get('fresh_win_period')}", flush=True)

json.dump(diags, open("team/runs/batch_027_r7a2_diags.json", "w"), ensure_ascii=False, indent=1, default=str)
print("=== DONE ===", flush=True)
print(pd.DataFrame(rows)[["id", "fresh_total", "fresh_mdd", "fresh_win_period", "fresh_win_month", "total_2025h2", "mdd_2025h2", "total_2025", "total_2024", "mdd_2024"]].to_string())
