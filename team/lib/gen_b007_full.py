"""batch_007 完整版：G2 其他选股器扩展 + G3 价值 + G6 ensemble（Lead 指定）。"""
import json
from pathlib import Path

TEAM = Path(__file__).resolve().parent.parent
OUT = TEAM / "runs" / "batch_007f_specs.json"
SELS = ["low_vol", "vol60", "rev20", "rev5", "turnover", "size", "amount_level", "liq_rev",
        "liq_lowvol", "liq_size", "triple", "quad", "amihud_industry_neutral", "amihud60_neutral"]


def mk(sid, stype, n, R, expo, group, tp=None, portfolio=None, notes=""):
    ex = dict(stop_exec="next")
    if tp is not None:
        ex["take_profit"] = tp
    return dict(id=sid, group=group,
                selector=dict(type=stype, n=n, size_range=[0.05, 0.30], min_adv=5_000_000,
                              exclude_star=True, exclude_bj=True, exclude_chinext=True,
                              price_min=None, price_max=None, params={}),
                rebalance_days=R, exit=ex,
                timing=dict(type="none", index=None, ma=None, out_asset="cash"),
                cost=dict(mode="realistic", one_way=0.005, capital=50000, lot_size=100),
                portfolio=portfolio or dict(exposure=expo, fresh_start=True),
                window=dict(warmup_start="2024-01-01", eval_start="2026-01-05", eval_end="2026-11-04"),
                notes=notes)


def main():
    specs = []
    for st in SELS:
        for n in (5, 10, 20):
            for R in (30, 60):
                for e in (0.6, 0.9):
                    specs.append(mk(f"b007f_G2_{st}_N{n}_R{R}_e{int(e*100)}", st, n, R, e, "G2_selectors",
                                    notes=f"{st} N{n} R{R} e{e}"))
    for st in ("value_ep", "value_bp", "value_sp"):
        for n in (10, 20):
            for R in (60,):
                for e in (0.6, 0.9):
                    specs.append(mk(f"b007f_G3_{st}_N{n}_R{R}_e{int(e*100)}", st, n, R, e, "G3_value",
                                    notes=f"{st} N{n} R{R} e{e}（价值反向对照）"))
    # G6 ensemble（沿用 strategist 的 5 条）
    try:
        src = {x["id"]: x for x in json.load(open(TEAM / "specs" / "batch_007.json"))}
        for sid in [k for k in src if k.startswith("b007_G6_")]:
            specs.append(src[sid])
    except Exception as e:
        print("G6 skipped:", e)
    OUT.write_text(json.dumps(specs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(specs)} specs → {OUT}")


if __name__ == "__main__":
    main()
