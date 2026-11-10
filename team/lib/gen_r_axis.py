"""团队 batch_007 R 轴生成器（Lead 指定网格，可重放）。
N4/N5 × R{20,30,40,60} × TP{40,45,50,60} × exposure{0.6,0.8,0.9,1.0}
+ R40/R60 no-stop 参考 + 控制组（N4 TP45 e1.0 / e0.9）。
全部：amihud_60 / 主板 / fresh 5万 realistic 整手 / t+1 执行。
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "runs" / "batch_007r_specs.json"


def mk(sid, n, R, tp, expo, group, notes=""):
    ex = dict(stop_exec="next")
    if tp is not None:
        ex["take_profit"] = tp
    return dict(
        id=sid, group=group,
        selector=dict(type="amihud_60", n=n, size_range=[0.05, 0.30], min_adv=5_000_000,
                      exclude_star=True, exclude_bj=True, exclude_chinext=True,
                      price_min=None, price_max=None, params={}),
        rebalance_days=R, exit=ex, timing=dict(type="none", index=None, ma=None, out_asset="cash"),
        cost=dict(mode="realistic", one_way=0.005, capital=50000, lot_size=100),
        portfolio=dict(exposure=expo, fresh_start=True),
        window=dict(warmup_start="2024-01-01", eval_start="2026-01-05", eval_end="2026-11-04"),
        notes=notes)


def main():
    specs = []
    for n in (4, 5):
        for R in (20, 30, 40, 60):
            for tp in (0.40, 0.45, 0.50, 0.60):
                for expo in (0.6, 0.8, 0.9, 1.0):
                    sid = f"b007_N{n}_R{R}_TP{int(tp*100)}_e{int(expo*100)}"
                    grp = "R60_priority" if R == 60 else ("R40_priority" if R == 40 else f"R{R}")
                    specs.append(mk(sid, n, R, tp, expo, grp,
                                    notes=f"N{n} R{R} TP{int(tp*100)} exposure {expo}"))
            for expo in (0.6, 0.8, 0.9, 1.0):
                specs.append(mk(f"b007_N{n}_R{R}_TPnone_e{int(expo*100)}", n, R, None, expo,
                                "R60_priority" if R == 60 else ("R40_priority" if R == 40 else f"R{R}"),
                                notes=f"N{n} R{R} no-stop exposure {expo}"))
    # 控制组
    specs.append(mk("b007_CTRL_N4_TP45_e100", 4, 30, 0.45, 1.0, "CTRL", "控制组：+102.07/-11.38"))
    specs.append(mk("b007_CTRL_N4_TP45_e90", 4, 30, 0.45, 0.9, "CTRL", "控制组：+91.23/-9.59"))
    OUT.write_text(json.dumps(specs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(specs)} specs → {OUT}")


if __name__ == "__main__":
    main()
