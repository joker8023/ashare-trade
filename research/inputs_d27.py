"""D27: Route-D new selectors (single file, no engine change).

Pool logic verbatim M07/X3 (seasoned>=250d, adv20>min_adv, close non-null,
amihud60 non-null, X3 momentum gate ret60<gate60 & ret10<0, cap cross-section
band quantile, MB prefix exclusion). MAX lottery filter reuses
MaxInputs.maxret (trailing max_win-day max single-day return, drop quantile
>= max_cut). use_max=False falls back to X3 bare pool.

New trailing-only matrices (all .loc[t] reads t-and-before):
  amihud5 : trailing-5d mean(|ret|/(amount/1e8)), larger = more illiquid
  vol20   : trailing-20d std of daily returns, smaller = calmer
  turn20  : trailing-20d mean(volume/shares), smaller = colder trading
Ranks are computed cross-sectionally on day t inside the MAX-filtered pool
(pandas rank average-ties, deterministic sort). No full-sample quantile.

Selectors (instance-bound sel; picks ignores factor arg for compat):
  amihud_60 / amihud / amihud_5 / size / amount / vol20 / turn20 (pure)
  c_a60_a5 / c_a60_size / c_a60_amt / c_a60_turn / c_a60_vol (rank-sum of 2)
  c_4 : rank-sum of amihud60+amihud5+size+turn20 (4-key composite)
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

PURE = ("amihud_60", "amihud", "amihud_5", "size", "amount", "vol20", "turn20")
COMP = ("c_a60_a5", "c_a60_size", "c_a60_amt", "c_a60_turn", "c_a60_vol", "c_4")
SELECTORS = PURE + COMP


class DInputs(MaxInputs):
    def __init__(self, piv, band=(0.05, 0.30), gate60=-1.0, min_adv=5e6,
                 max_win=20, max_cut=0.80, use_max=True, sel="amihud_60"):
        assert sel in SELECTORS, sel
        super().__init__(piv, band=band, gate60=gate60, min_adv=min_adv,
                         max_win=max_win, max_cut=max_cut)
        self.sel = sel
        self.use_max = use_max
        r = self.ret.abs()
        amt = self.amount.replace(0, np.nan)
        self.amihud5 = (r / (amt / 1e8)).rolling(5, min_periods=5).mean()
        self.vol20 = self.ret.rolling(20, min_periods=20).std()
        shr = self.shares.replace(0, np.nan)
        vol = self.piv["volume"].replace(0, np.nan) if "volume" in self.piv else None
        if vol is not None:
            self.turn20 = (vol / shr).rolling(20, min_periods=20).mean()
        else:
            self.turn20 = (self.amount / self.cap.replace(0, np.nan)).rolling(20, min_periods=20).mean()

    def _keys(self):
        a60 = (self.amihud60, False)
        if self.sel == "amihud_60":
            return [a60]
        if self.sel == "amihud":
            return [(self.amihud, False)]
        if self.sel == "amihud_5":
            return [(self.amihud5, False)]
        if self.sel == "size":
            return [(self.cap, True)]
        if self.sel == "amount":
            return [(self.adv20, True)]
        if self.sel == "vol20":
            return [(self.vol20, True)]
        if self.sel == "turn20":
            return [(self.turn20, True)]
        if self.sel == "c_a60_a5":
            return [a60, (self.amihud5, False)]
        if self.sel == "c_a60_size":
            return [a60, (self.cap, True)]
        if self.sel == "c_a60_amt":
            return [a60, (self.adv20, True)]
        if self.sel == "c_a60_turn":
            return [a60, (self.turn20, True)]
        if self.sel == "c_a60_vol":
            return [a60, (self.vol20, True)]
        if self.sel == "c_4":
            return [a60, (self.amihud5, False), (self.cap, True), (self.turn20, True)]
        raise ValueError(self.sel)

    def _order(self, t, base):
        keys = self._keys()
        if len(keys) == 1:
            mat, asc = keys[0]
            s = mat.loc[t, base].dropna().sort_values(ascending=asc)
            return list(s.index)
        df = pd.DataFrame({("k%d" % i): m.loc[t, base] for i, (m, a) in enumerate(keys)}).dropna()
        if df.empty:
            return []
        rs = sum(df[("k%d" % i)].rank(ascending=a) for i, (m, a) in enumerate(keys))
        return list(rs.sort_values().index)

    def picks(self, t, n, size_range=None, min_adv=None, exclude=(), factor=None):
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
        return self._order(t, base)[:n]
