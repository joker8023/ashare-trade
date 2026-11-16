"""K10:复合秩和排序键 (只新增本文件,不改引擎/口径).

背景:K9 纯新键 12 配全灭 (最高仅 beat 3 窗,mdd 全部更差,见 sweep_beat_m07_k9.json),
本轮试点复合键 = amihud_60 秩 + 第二键秩的秩和,取小者优先.最后的低成本探针,
严格 3 键 x 2 腿 = 6 新配 + base_M07 校准行.

口径 (除选股器外与 M07 / run_m07_final.py 逐字一致,复述自 inputs_k9.py):
  * 池:上市>=250交易日 (seasoned, close.shift(250).notna),
    adv20 > min_adv, t日close非空, amihud60非空,
    X3 momentum gate (ret60 < gate60 且 ret10 < 0 则剔除),
    流通市值截面 band 分位, MB前缀排除.
  * ST:pivots 无 ST/名称字段, M07 全链路亦无 ST 过滤 (仅 seasoned+MB),
    K10 与 M07 一致 = 不做 ST 过滤 (如实声明,非遗漏).
  * MAX 彩票过滤 (cut/win) 复用 MaxInputs.maxret (trailing max_win 日最大单日涨幅,
    剔除分位 >= max_cut 的彩票股), K10 全部 MAX开 (M07默认 cut=0.80/winA40/winB20).
  * 无未来函数:所有矩阵均为 trailing (rolling/min_periods, .loc[t] 只读 t 及以前;
    cap 截面分位用 t 日收盘,与 M07/X3 逐字一致,无 t+1 数据).
    amihud5 与 pc.Inputs.amihud/amihud60 同构 (trailing 5d mean abs_ret/(amount/1e8)).

新 selector (sel 参数,实例绑定,秩和取小者优先):
  * a60_size : rank(amihud60 desc,越不流动秩越小) + rank(cap asc,越小秩越小)
  * a60_adv  : rank(amihud60 desc) + rank(adv20 asc,越小秩越小)
  * a60_a5   : rank(amihud60 desc) + rank(amihud5 desc,越大秩越小)
  秩均在 t 日 MAX过滤后池内截面计算 (pandas rank,默认 average平分并列;
  sort_values 稳定排序,并列顺序确定性一致).任一键缺值即剔除 (与 K9 dropna 同口径).

换持仓身份必须换选股器实例:switch 引擎对双腿只传单一 factor
(switch_engine.py L190: inp_cur.picks(sig_day, n_eff, exclude=exclude, factor=factor)),
无法逐腿传 factor.因此 K10Inputs.picks 固定使用构造期 sel,忽略传入的 factor
(签名兼容,行为以实例为准).单腿B试点:A腿=MaxInputs原实例 + B腿=K10实例.
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

SELECTORS = ("a60_size", "a60_adv", "a60_a5")


class K10Inputs(MaxInputs):
    """M07 池 + MAX 复用,只换排序键为复合秩和."""

    def __init__(self, piv, band=(0.05, 0.30), gate60=-1.0, min_adv=5e6,
                 max_win=20, max_cut=0.80, use_max=True, sel="a60_size"):
        assert sel in SELECTORS, sel
        super().__init__(piv, band=band, gate60=gate60, min_adv=min_adv,
                         max_win=max_win, max_cut=max_cut)
        self.sel = sel
        self.use_max = use_max
        r = self.ret.abs()
        amt = self.amount.replace(0, np.nan)
        # trailing 5d Amihud,只用 t 及以前 (min_periods=5),与 K9 同构
        self.amihud5 = (r / (amt / 1e8)).rolling(5, min_periods=5).mean()

    def _second(self):
        """返回 (matrix, ascending):第二键矩阵与秩方向."""
        if self.sel == "a60_size":
            return self.cap, True
        if self.sel == "a60_adv":
            return self.adv20, True
        return self.amihud5, False

    def composite_order(self, t, base):
        """t 日池内截面秩和排序 (全 trailing,.loc[t] 只读 t 及以前)."""
        mat2, asc2 = self._second()
        df = pd.DataFrame({"a60": self.amihud60.loc[t, base],
                           "s2": mat2.loc[t, base]}).dropna()
        if df.empty:
            return []
        r1 = df["a60"].rank(ascending=False)  # 越不流动秩越小
        r2 = df["s2"].rank(ascending=asc2)
        return list((r1 + r2).sort_values().index)

    def picks(self, t, n, size_range=None, min_adv=None, exclude=(), factor=None):
        """池与 M07/X3 逐字一致,只换排序键为复合秩和.

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
        return self.composite_order(t, base)[:n]
