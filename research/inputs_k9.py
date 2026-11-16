"""K9:最小新 Inputs 试点 (只新增本文件,不改引擎/口径).

背景:引擎原生因子是二值的 (pc.Inputs 仅 amihud_20 / amihud_60),
size / amount_level 无原生支持.R9 证实短窗墙 = 尾部持仓身份相同 + 分母效应,
换持仓身份必须换选股器.本文件新增 K9Inputs,池子逻辑与 M07 逐字一致,
只换最终排序键 (rank key).

口径 (除选股器外与 M07 / run_m07_final.py 逐字一致):
  * 池:上市>=250交易日 (seasoned, close.shift(250).notna),
    adv20 > min_adv, t日close非空, amihud60非空,
    X3 momentum gate (ret60 < gate60 且 ret10 < 0 则剔除),
    流通市值截面 band 分位, MB前缀排除.
  * ST:pivots 无 ST/名称字段, M07 全链路亦无 ST 过滤 (仅 seasoned+MB),
    K9 与 M07 一致 = 不做 ST 过滤 (如实声明,非遗漏).
  * MAX 彩票过滤 (cut/win) 复用 MaxInputs.maxret (trailing max_win 日最大单日涨幅,
    剔除分位 >= max_cut 的彩票股), use_max=False 时退化为 X3 裸池.
  * 无未来函数:所有矩阵均为 trailing (rolling/min_periods, .loc[t] 只读 t 及以前;
    cap 截面分位用 t 日收盘,与 M07/X3 逐字一致,无 t+1 数据).

新 selector (sel 参数,实例绑定):
  * size     : 流通市值最小优先 (cap.loc[t] ascending).cap = close*shares,
               shares 为静态快照 (M07 同款伪市值口径,如实声明).
  * amount   : 20日均成交额最小优先 (adv20.loc[t] ascending).
  * amihud_5 : 5日 Amihud 最大优先 (trailing 5d mean abs_ret/(amount/1e8), descending),
               与 amihud/amihud_60 同向 (越不流动越优先).
  * amihud / amihud_60 : 透传原生语义 (校准/对照用).

换持仓身份必须换选股器实例:switch 引擎对双腿只传单一 factor
(switch_engine.py L190: inp_cur.picks(sig_day, n_eff, exclude=exclude, factor=factor)),
无法逐腿传 factor.因此 K9Inputs.picks 固定使用构造期 sel,忽略传入的 factor
(签名兼容,行为以实例为准).单腿B试点:A腿=MaxInputs原实例 + B腿=K9实例.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "team" / "audit"))
sys.path.insert(0, str(ROOT / "research"))

import numpy as np
import pandas as pd
from design_r30_grid8 import X3Inputs
from fresh2_max import MaxInputs

SELECTORS = ("amihud", "amihud_60", "amihud_5", "size", "amount")


class K9Inputs(MaxInputs):
    """M07 池 + MAX 复用,只换排序键."""

    def __init__(self, piv, band=(0.05, 0.30), gate60=-1.0, min_adv=5e6,
                 max_win=20, max_cut=0.80, use_max=True, sel="amihud_60"):
        assert sel in SELECTORS, sel
        super().__init__(piv, band=band, gate60=gate60, min_adv=min_adv,
                         max_win=max_win, max_cut=max_cut)
        self.sel = sel
        self.use_max = use_max
        r = self.ret.abs()
        amt = self.amount.replace(0, np.nan)
        # trailing 5d Amihud,只用 t 及以前 (min_periods=5)
        self.amihud5 = (r / (amt / 1e8)).rolling(5, min_periods=5).mean()

    def _rank(self):
        """返回 (matrix, ascending)."""
        if self.sel == "size":
            return self.cap, True
        if self.sel == "amount":
            return self.adv20, True
        if self.sel == "amihud_5":
            return self.amihud5, False
        if self.sel == "amihud":
            return self.amihud, False
        return self.amihud60, False

    def picks(self, t, n, size_range=None, min_adv=None, exclude=(), factor=None):
        """池与 M07/X3 逐字一致,只换排序键.

        factor 参数为引擎签名兼容而保留,一律忽略,以构造期 sel 为准
        (switch 引擎双腿共用单一 factor,逐腿身份必须由实例承载).
        """
        # 池子:复用 MaxInputs (MAX开) / X3Inputs (MAX关) 的 t 日 9999 全池,
        # 内部已含 seasoned/adv/close/amihud60/gate/band/exclude 全套 M07 条件.
        if self.use_max:
            base = super().picks(t, 9999, size_range=size_range,
                                 min_adv=min_adv, exclude=exclude,
                                 factor="amihud_60")
        else:
            base = X3Inputs.picks(self, t, 9999, size_range=size_range,
                                  min_adv=min_adv, exclude=exclude,
                                  factor="amihud_60")
        if not base:
            return []
        mat, asc = self._rank()
        ranked = mat.loc[t, base].dropna().sort_values(ascending=asc)
        return list(ranked.head(n).index)
