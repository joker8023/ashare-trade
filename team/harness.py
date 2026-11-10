"""
team/harness.py — 统一回测器（PROTOCOL v1.2：§1-§3 + §10 + §11）
================================================================

输入一个 spec dict（PROTOCOL §8 schema）→ 输出一行指标（+ 可选 equity/trades 明细）。

防未来函数
----------
* t 日收盘算信号 → **t+1 日收盘成交**（不用 t+1 开盘价，不用 t+1 之后的信息）。
* 因子只用 ≤t 的滚动窗口（rolling / shift），无负向 shift。
* 止损/止盈：见 §11.1 —— 主口径 `stop_exec="next"`：t 日收盘触发、**t+1 日收盘**卖出；
  `stop_exec="same"`（当日收盘价成交）只作乐观敏感性，不进 Tier A 主判定。
* 调仓日 t 的选股池/因子值只用 t 日收盘及以前数据。

网格（§10.1，v1.1 修正）
------------------------
从全量 `dates[300]` 起每 R 个交易日一个**调仓信号日**，**一直生成到最后一个可执行调仓日**
（信号日 i 满足 i+1 < len(dates)）；执行日 = 信号日 +1 收盘。旧脚本 `range(300, len-R-2, R)`
漏掉最后一个调仓日（R=30 时漏掉 2026-10-27），本 harness 不复现旧口径（可用
`rebalance_anchor="legacy_cut"` 单独复现，仅用于差异定位）。
`phase`（§11.2）在该网格上整体平移 phase 个交易日（主口径 phase=0）。

口径声明（引用数字时必须一起引用）
----------------------------------
1. `total_2026`：连续口径，基数 = 2025-12-31 收盘净值，允许 2025 建仓带入 2026（主判定）。
2. `fresh_2026`：2026-01-05 空仓起步，只在 2026 年第一个调仓日建仓（基数 1.0）。
3. `win_period`（主口径）：**完整调仓段** —— 段的两端都是网格调仓执行日、段长恰好 R、
   且完全落在窗口内（段起点 ≥ 窗口首日、段终点 ≤ 窗口末日）；partial 尾段不计入分母，
   单独输出 `last_partial_ret`。`win_period_loose` 额外把贴窗口边界的段（段长 ≥ 0.8R）算进来（参考）。
4. `win_month`：窗口内**完整自然月**（2026 = 1..10 月；11-01..11-04 仅 3 个交易日不计入），
   首月基数 = 2025-12-31。
5. `win_trade`：所有已平仓头寸净收益 > 0 的占比（净收益含双边成本）；未平仓不计入。
6. 停牌/缺失价：停牌前收盘 ffill 估值与成交（同 ledger_10k.py）。**未建模涨跌停不可成交**。
7. 选股池默认：上市 ≥ 250 交易日、adv20 > min_adv(5e6)、当日收盘有效、总市值截面 5%~30% 分位。
8. 中途止损/止盈卖出后资金留现金（或 out_asset=bond 停泊），不立即补仓，等下一调仓日。
9. 选股集合与上期完全相同则不再平衡权重（同 ledger_10k.py），否则清仓后等权买入。
10. 成本：`cost.mode="fixed"`（主）单边 `one_way`（默认 0.5%）× 名义金额，份额可零碎；
    `cost.mode="realistic"`（次）佣金 0.025%(最低5元)+卖出印花 0.05%+过户 0.001%+滑点 0.2%/边，
    按 `lot_size` 整手撮合。

用法
----
    from team.harness import run_spec
    row = run_spec(spec)                       # 主口径 + 敏感性列
    row, eqdf, trdf = run_spec(spec, detail=True)
    python team/harness.py --file /tmp/spec.json --detail
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent          # repo root
HERE = Path(__file__).resolve().parent                 # team/
DATA_PKL = BASE / "data" / "pivots_long_clean.pkl"
BOND_PKL = BASE / "data" / "bond_511880.pkl"
IND_PKL = BASE / "data" / "industry_map.pkl"
IDX_CACHE = BASE / "results" / "_cache"

CALC_START = "2022-01-01"      # 因子计算起点（给 2024 起的 250 日上市判断留足余量）

WINDOWS = {
    "2026":   ("2026-01-05", "2026-11-04", "2025-12-31"),
    "2025":   ("2025-01-01", "2025-12-31", "2024-12-31"),
    "2025h2": ("2025-07-01", "2025-12-31", "2025-06-30"),
    "2024":   ("2024-01-01", "2024-12-31", None),
}
DEFAULTS = dict(eval_start="2026-01-05", eval_end="2026-11-04", warmup_start="2024-01-01")
LOT_FEE = dict(comm=0.00025, min_comm=5.0, stamp=0.0005, transfer=0.00001, slip=0.002)
EXEC_MODES = ("next", "same")

LIMITATIONS = [
    "涨跌停/停牌不可成交未建模：成交价一律用当日收盘（缺失则 ffill 停牌前收盘）。",
    "总股本 shares 为当前快照（非历史），市值分位有轻微前视；与 engine.py / ledger_10k.py 一致。",
    "幸存者偏差：数据仅含当前仍上市股票，无法修复。",
    "择时 index_ma / dd_breaker 只在调仓日决策（与原仓库策略一致）。",
    "现金默认 0 收益；out_asset='bond' 时按 511880 收盘日收益（停牌日按年化 3%/252 兜底）。",
    "同一调仓日先执行 pending 止损再换仓：被止损且又入选的股票多付一次双边成本（保守）。",
    "fresh_2026 的首个调仓日由固定相位决定（R30 = 2026-01-23 信号 / 01-26 建仓），之前为现金。",
]


# ===========================================================================
# 0. 数据包（进程内单例；因子矩阵按需计算并缓存）
# ===========================================================================
def _np32(df) -> np.ndarray:
    a = df.to_numpy(dtype=np.float32) if hasattr(df, "to_numpy") else np.asarray(df, dtype=np.float32)
    return np.ascontiguousarray(a)


def _rank(df: pd.DataFrame) -> pd.DataFrame:
    return df.rank(axis=1, pct=True)


class Bundle:
    def __init__(self, calc_start: str = CALC_START):
        t0 = time.time()
        p = pd.read_pickle(DATA_PKL)
        self.full_dates = p["close"].index
        self.codes = p["close"].columns
        m = self.full_dates >= pd.Timestamp(calc_start)
        self.offset = int(np.argmax(m))
        self.df = {k: v.loc[m] for k, v in p.items() if isinstance(v, pd.DataFrame)}
        self.shares = p["shares"].reindex(self.codes).astype(float)
        self.dates = self.df["close"].index
        self.n_dates = len(self.dates)
        self.n_codes = len(self.codes)
        self.pos = {d: i for i, d in enumerate(self.dates)}

        close = self.df["close"]
        amount = self.df["amount"]
        self.close = close
        self.amount = amount
        self.close_ff = close.ffill()
        self.close_np = np.ascontiguousarray(close.to_numpy(dtype=np.float32))
        self.close_ff_np = np.ascontiguousarray(self.close_ff.to_numpy(dtype=np.float32))
        self.adv20 = amount.rolling(20, min_periods=10).mean()
        self.seasoned = close.shift(250).notna()
        self.cap = close.mul(self.shares, axis=1)
        self.pool_base = (self.seasoned & self.adv20.gt(5e6) & close.notna()).fillna(False)

        self._fac: dict[str, np.ndarray] = {}
        self._np: dict[str, np.ndarray] = {}
        self._univ: dict[str, np.ndarray] = {}
        self._picks: dict[str, np.ndarray] = {}
        self._bond = None
        self._ind = None
        self.load_secs = time.time() - t0

        cs = self.codes.astype(str)
        self.is_star = np.asarray(cs.str.startswith(("688", "689")), dtype=bool)
        self.is_bj = np.asarray(cs.str.startswith(("4", "8", "920")), dtype=bool)
        self.is_chinext = np.asarray(cs.str.startswith(("300", "301", "302")), dtype=bool)
        self.is_board20 = np.asarray(cs.str.startswith(("300", "301", "302", "688", "689")), dtype=bool)
        # 跌停价比例（主板 10%，创业板/科创板 20%）
        self.limit_down_ratio = np.where(self.is_board20, 1.0 - 0.198, 1.0 - 0.098).astype(np.float64)

    def attr_np(self, name: str, fn) -> np.ndarray:
        if name not in self._np:
            self._np[name] = _np32(fn())
        return self._np[name]

    def bond_ret(self) -> np.ndarray:
        if self._bond is None:
            try:
                df = pd.read_pickle(BOND_PKL)
                b = df.set_index(pd.to_datetime(df["date"])).sort_index()["close"].astype(float)
                r = b.pct_change().reindex(self.dates).ffill()
                r = r.where(np.abs(r) > 1e-9, 0.03 / 252).fillna(0.03 / 252)
                self._bond = r.to_numpy(dtype=np.float64)
            except Exception:
                self._bond = np.full(self.n_dates, 0.03 / 252)
        return self._bond

    def industry(self) -> pd.Series:
        if self._ind is None:
            try:
                mm = pd.read_pickle(IND_PKL)
                self._ind = mm.set_index("code")["industry_group"].reindex(self.codes)
            except Exception:
                self._ind = pd.Series(index=self.codes, dtype=object)
        return self._ind


_B: Bundle | None = None


def bundle(force: bool = False) -> Bundle:
    global _B
    if _B is None or force:
        _B = Bundle()
    return _B


# ===========================================================================
# 1. 因子 / 选股器注册表（date×code，数值越大越优先，NaN = 不可选）
# ===========================================================================
def _pct(c):
    return c.pct_change(fill_method=None)


def _amihud(b, window=20):
    r = _pct(b.df["close"]).abs()
    amt = b.df["amount"].replace(0, np.nan)
    return (r / (amt / 1e8)).rolling(window).mean()


def f_amihud(b, window=20):        return _amihud(b, window)
def f_amihud_5(b, window=5):       return _amihud(b, window)
def f_amihud_60(b, window=60):     return _amihud(b, window)


def f_amihud_smooth(b, window=20, w_amihud=0.7, w_turn=0.3):
    turn = (b.df["amount"] / b.cap.replace(0, np.nan)).rolling(20).mean()
    return _rank(_amihud(b, window)).mul(w_amihud) + _rank(-turn).mul(w_turn)


def f_low_vol(b, window=20):
    return -_pct(b.df["close"]).rolling(window).std()


def f_vol60(b, window=60):
    return -_pct(b.df["close"]).rolling(window).std()


def f_rev20(b, window=20):
    c = b.df["close"]
    return -(c / c.shift(window) - 1)


def f_rev5(b, window=5):
    c = b.df["close"]
    return -(c / c.shift(window) - 1)


def f_rev60(b, window=60):
    c = b.df["close"]
    return -(c / c.shift(window) - 1)


def f_turnover(b, window=20):
    turn = b.df["amount"] / b.cap.replace(0, np.nan)
    return -turn.rolling(window).mean()


def f_size(b, window=0):
    return -b.cap


def f_amount_level(b, window=20):
    return -b.df["amount"].rolling(window).mean()


def f_liq_rev(b, window=20):
    adv = b.df["amount"].rolling(window).mean()
    c = b.df["close"]
    return _rank(-adv) + _rank(-(c / c.shift(20) - 1))


def f_liq_lowvol(b, window=20):
    adv = b.df["amount"].rolling(window).mean()
    return _rank(-adv) + _rank(-_pct(b.df["close"]).rolling(20).std())


def f_liq_size(b, window=20):
    adv = b.df["amount"].rolling(window).mean()
    return _rank(-adv) + _rank(-b.cap)


def f_triple(b, window=20):
    adv = b.df["amount"].rolling(window).mean()
    c = b.df["close"]
    return (_rank(-adv) + _rank(-(c / c.shift(60) - 1))
            + _rank(-_pct(c).rolling(20).std()))


def f_quad(b, window=20):
    adv = b.df["amount"].rolling(window).mean()
    c = b.df["close"]
    turn = (b.df["amount"] / b.cap.replace(0, np.nan)).rolling(20).mean()
    return (_rank(-adv) + _rank(-(c / c.shift(20) - 1))
            + _rank(-_pct(c).rolling(20).std()) + _rank(-turn))


def f_liq_rev_lowvol(b, window=20):
    adv = b.df["amount"].rolling(window).mean()
    c = b.df["close"]
    return (_rank(-adv) + _rank(-(c / c.shift(20) - 1))
            + _rank(-_pct(c).rolling(20).std()))


def f_bias20(b, window=20):
    c = b.df["close"]
    return -(c / c.rolling(20).mean() - 1)


def f_max20(b, window=20):
    return -_pct(b.df["close"]).rolling(window).max()


def f_mom60(b, window=60):
    c = b.df["close"]
    return c / c.shift(window) - 1


def _industry_neutral(b, a):
    ind = b.industry()
    if len(ind) == 0 or ind.notna().sum() == 0:
        return a
    groups = ind.reindex(a.columns)
    out = pd.DataFrame(np.nan, index=a.index, columns=a.columns, dtype="float64")
    for g, cols in groups.groupby(groups).groups.items():
        if g is None or (isinstance(g, float) and pd.isna(g)):
            continue
        out[list(cols)] = a[list(cols)].rank(axis=1, pct=True)
    return out


def f_amihud_industry_neutral(b, window=20):
    return _industry_neutral(b, _amihud(b, window))


def f_amihud60_neutral(b, window=60):
    return _industry_neutral(b, _amihud(b, window))


def f_dual_scale(b, alpha=0.5, s7="amihud_5", s30="amihud_60", s7_params=None, s30_params=None):
    """R7-E 双时间尺度融合：Score = alpha*rank(S7) + (1-alpha)*rank(S30)。
    严格 NaN：任一腿无效则融合记 NaN。只用 _fac_matrix（rolling/shift 构造）加当期 rank，无前视。"""
    a = float(alpha)
    if not (0 <= a <= 1):
        raise ValueError(f"dual_scale alpha 需在[0,1]: {alpha}")
    m7 = _fac_matrix(b, str(s7), dict(s7_params or {}))
    m30 = _fac_matrix(b, str(s30), dict(s30_params or {}))
    d7 = pd.DataFrame(m7, index=b.dates)
    d30 = pd.DataFrame(m30, index=b.dates)
    r7 = d7.rank(axis=1, pct=True)
    r30 = d30.rank(axis=1, pct=True)
    return (r7 * a + r30 * (1.0 - a)).where(d7.notna() & d30.notna())


# --- 价值因子（data/value_em.pkl：逐日 PE/市净率/市销率 面板）---
_VALUE = None


def value_panel(field: str) -> pd.DataFrame:
    """把 {code: DataFrame[PE(TTM)/市净率/市销率]} 摊成 date×code 面板（当日快照，缺失 ffill）。"""
    global _VALUE
    if _VALUE is None:
        _VALUE = {}
    if field not in _VALUE:
        raw = pd.read_pickle(BASE / "data" / "value_em.pkl")
        cols = {}
        for code, df in raw.items():
            if field in getattr(df, "columns", ()):
                s_ = df[field]
                s_.index = pd.to_datetime(s_.index)
                cols[code] = s_
        _VALUE[field] = pd.DataFrame(cols).sort_index()
    return _VALUE[field]


def _value_factor(b: Bundle, field: str, invert: bool = True) -> pd.DataFrame:
    v = value_panel(field).reindex(b.dates).ffill()
    v = v.reindex(columns=b.codes)
    if invert:
        v = 1.0 / v.where(v > 0)          # EP=1/PE, BP=1/PB, SP=1/PS
    return v


def f_value_ep(b):
    return _value_factor(b, "PE(TTM)")


def f_value_bp(b):
    return _value_factor(b, "市净率")


def f_value_sp(b):
    return _value_factor(b, "市销率")


FACTORS = {
    "value_ep": f_value_ep, "value_bp": f_value_bp, "value_sp": f_value_sp,
    "amihud": f_amihud, "amihud_5": f_amihud_5, "amihud_60": f_amihud_60,
    "amihud_smooth": f_amihud_smooth, "low_vol": f_low_vol, "vol60": f_vol60,
    "rev20": f_rev20, "rev5": f_rev5, "rev60": f_rev60, "turnover": f_turnover,
    "size": f_size, "amount_level": f_amount_level, "liq_rev": f_liq_rev,
    "liq_lowvol": f_liq_lowvol, "liq_size": f_liq_size, "triple": f_triple,
    "quad": f_quad, "liq_rev_lowvol": f_liq_rev_lowvol, "bias20": f_bias20,
    "max20": f_max20, "mom60": f_mom60,
    "amihud_industry_neutral": f_amihud_industry_neutral,
    "amihud60_neutral": f_amihud60_neutral,
    "dual_scale": f_dual_scale,
}
CUSTOM_SELECTORS = {"breakout", "oversold"}
SELECTOR_ALIASES = {"amihud_neutral": "amihud_industry_neutral"}


def _fac_matrix(b: Bundle, name: str, params: dict | None = None) -> np.ndarray:
    params = params or {}
    key = name + "|" + json.dumps(params, sort_keys=True)
    if key in b._fac:
        return b._fac[key]
    fn = FACTORS[name]
    varnames = fn.__code__.co_varnames[: fn.__code__.co_argcount]
    kwargs = {k: v for k, v in params.items() if k in varnames and k != "b"}
    fac = fn(b, **kwargs)
    if not isinstance(fac, pd.DataFrame):
        raise ValueError(f"selector {name} 未返回 DataFrame")
    arr = _np32(fac)
    if len(b._fac) >= 12:
        for k in list(b._fac)[:4]:
            b._fac.pop(k, None)
    b._fac[key] = arr
    return arr


def _fac_row(b: Bundle, name: str, params: dict | None, t_pos: int) -> np.ndarray:
    return _fac_matrix(b, name, params)[t_pos]


# ===========================================================================
# 2. spec 规范化
# ===========================================================================
def _staged_levels(levels, h, px):
    """返回当前价已触发但尚未执行的档位索引（升序）。"""
    return [i for i, (g, f) in enumerate(levels)
            if px >= h["px"] * (1.0 + g) and i not in h.get("staged_hit", ())]


def _parse_staged(v):
    """分批止盈: [{'gain':0.30,'frac':0.3333}, ...] / [[0.30,0.3333],...] / {'0.30':0.3333}"""
    if not v:
        return None
    items = []
    if isinstance(v, dict):
        items = [(float(k), float(x)) for k, x in v.items()]
    elif isinstance(v, (list, tuple)):
        for x in v:
            if isinstance(x, dict):
                g = x.get("gain", x.get("trigger", x.get("g", x.get("threshold"))))
                fr = x.get("frac", x.get("fraction", x.get("f", x.get("sell", x.get("ratio")))))
                if g is None or fr is None:
                    raise ValueError(f"staged_take 缺少 trigger/fraction 字段: {x!r}")
                items.append((float(g), float(fr)))
            elif isinstance(x, (list, tuple)) and len(x) == 2:
                items.append((float(x[0]), float(x[1])))
            else:
                raise ValueError(f"staged_take 元素非法: {x!r}")
    else:
        raise ValueError(f"staged_take 非法: {v!r}")
    items.sort(key=lambda t: t[0])
    out = []
    for g, f in items:
        if not (0 < g < 5):
            raise ValueError(f"staged_take trigger 非法: {g}")
        if not (0 < f <= 1):
            raise ValueError(f"staged_take fraction 非法: {f}")
        out.append((g, f))            # fraction = 当前**剩余**持仓的比例
    if len(out) < 1:
        raise ValueError("staged_take 不能为空")
    return out


def _opt_float(v):
    if v is None or v == "":
        return None
    return float(v)


def _opt_int(v):
    if v is None or v == "":
        return None
    return int(v)


def _parse_hold_exempt(v):
    """opt-in 持仓豁免：None/False 关闭；dict 开启 {ma, tol, rank_band}。"""
    if v is None or v is False:
        return None
    if v is True:
        v = {}
    if not isinstance(v, dict):
        raise ValueError(f"selector.hold_exempt 非法: {v!r}")
    ma = int(v.get("ma", 20))
    tol = float(v.get("tol", 1.0))
    rb = float(v.get("rank_band", 0.4))
    if ma < 5:
        raise ValueError(f"selector.hold_exempt.ma 需 >=5: {ma}")
    if not (0 < tol <= 1):
        raise ValueError(f"selector.hold_exempt.tol 需在 (0,1]: {tol}")
    if not (0 < rb <= 1):
        raise ValueError(f"selector.hold_exempt.rank_band 需在 (0,1]: {rb}")
    return dict(ma=ma, tol=tol, rank_band=rb)


def _parse_dd_max_off_days(v):
    """opt-in 熔断离场上限：None/"" 关闭；整数≥1，超限执行日数强制恢复。"""
    if v is None or v == "":
        return None
    n = int(v)
    if n < 1:
        raise ValueError(f"timing.dd_max_off_days 需 >=1: {v!r}")
    return n


def _parse_absmom(v):
    """opt-in 绝对动量过滤：None/False/{} 关闭；{ma} 或 {mom_skip:[L,S]}，ma 优先。"""
    if v is None or v is False or v == {}:
        return None
    if not isinstance(v, dict):
        raise ValueError(f"selector.absmom 非法: {v!r}")
    if v.get("ma") is not None:
        ma = int(v["ma"])
        if ma < 5:
            raise ValueError(f"selector.absmom.ma 需 >=5: {ma}")
        return dict(ma=ma, mom_skip=None)
    if v.get("mom_skip") is not None:
        ms = v["mom_skip"]
        if not (isinstance(ms, (list, tuple)) and len(ms) == 2):
            raise ValueError(f"selector.absmom.mom_skip 需为 [L,S] 两整数: {ms!r}")
        L, S = int(ms[0]), int(ms[1])
        if L < 1 or S < 1:
            raise ValueError(f"selector.absmom.mom_skip 需两正整数: {ms!r}")
        if not (L > S):
            raise ValueError(f"selector.absmom.mom_skip 需 L>S: {ms!r}")
        return dict(ma=None, mom_skip=[L, S])
    return None


def _parse_rebalance_gate(v):
    """R7-A/B/C 调仓门控（opt-in；None 关闭=老行为全量换仓）。
    - overlap: {type:'overlap', min_overlap:int} 新旧交集>=阈值则跳过（R7-A 基础版）
    - cost_aware: {type:'cost_aware', min_overlap:int, lam:float} 先交集检查，
      再用 U=Δα-C-λσ>0 判断（R7-A 完整版，Δα=新旧篮子过去20日收益差，C=预估双边成本，σ= involved 20日波动均值；只用≤t数据）
    - rank_hold: {type:'rank_hold', keep_rank:int} 只卖出跌出前keep_rank的持仓（R7-B 换手惩罚）
    - dynamic: {type:'dynamic', keep_rank:int, full_threshold:int} overlap==N跳过(A)；
      overlap>full_threshold部分调(B)；否则全量(C)（R7-C）
    """
    if v is None or v is False:
        return None
    if not isinstance(v, dict):
        raise ValueError(f"rebalance_gate 非法: {v!r}")
    t = str(v.get("type") or "overlap").lower()
    if t == "overlap":
        mo = int(v.get("min_overlap", 3))
        if mo < 1:
            raise ValueError(f"rebalance_gate.min_overlap 需>=1: {mo}")
        return dict(type="overlap", min_overlap=mo)
    if t == "cost_aware":
        mo = int(v.get("min_overlap", 3))
        lam = float(v.get("lam", v.get("lambda", 1.0)))
        if mo < 1:
            raise ValueError(f"rebalance_gate.min_overlap 需>=1: {mo}")
        if not (0 <= lam <= 5):
            raise ValueError(f"rebalance_gate.lam 需在[0,5]: {lam}")
        return dict(type="cost_aware", min_overlap=mo, lam=lam)
    if t == "rank_hold":
        kr = int(v.get("keep_rank", 8))
        if kr < 1:
            raise ValueError(f"rebalance_gate.keep_rank 需>=1: {kr}")
        return dict(type="rank_hold", keep_rank=kr)
    if t == "dynamic":
        kr = int(v.get("keep_rank", 8))
        ft = int(v.get("full_threshold", 1))
        if kr < 1 or ft < 0:
            raise ValueError(f"rebalance_gate dynamic 参数非法: {v!r}")
        return dict(type="dynamic", keep_rank=kr, full_threshold=ft)
    if t == "asymmetric":
        entry_R = int(v.get("entry_R", 7))
        exit_R = v.get("exit_R", None)
        exit_rank = v.get("exit_rank", None)
        exit_R = int(exit_R) if exit_R is not None else None
        exit_rank = int(exit_rank) if exit_rank is not None else None
        if (exit_R is None) == (exit_rank is None):
            raise ValueError("asymmetric 须 exit_R 与 exit_rank 恰其一非空")
        if entry_R < 1 or (exit_R is not None and exit_R < 1) or (exit_rank is not None and exit_rank < 1):
            raise ValueError(f"asymmetric 参数非法: {v!r}")
        return dict(type="asymmetric", entry_R=entry_R, exit_R=exit_R, exit_rank=exit_rank)
    raise ValueError(f"未知 rebalance_gate.type: {t!r}")


def _portfolio_cfg(pf: dict) -> dict:
    """仓位缓冲：exposure ∈ (0,1] 表示每次调仓只投入 cash*exposure，其余留现金。"""
    if not isinstance(pf, dict):
        pf = {}
    expo = float(pf.get("exposure", 1.0))
    if not (0.05 <= expo <= 1.0):
        raise ValueError(f"portfolio.exposure 需在 (0.05,1.0]: {expo}")
    sl = pf.get("sleeves")
    if sl is not None:
        if not isinstance(sl, dict):
            raise ValueError("portfolio.sleeves 必须是 dict")
        offs = [int(x) for x in (sl.get("offsets") or [-8, 0, 8])]
        if len(offs) < 2:
            raise ValueError("portfolio.sleeves.offsets 至少 2 个")
        sl = dict(count=len(offs), offsets=offs, alloc=str(sl.get("alloc") or "equal"))
    vt = _opt_float(pf.get("vol_target"))
    if vt is not None and not (0.05 <= vt <= 1.5):
        raise ValueError(f"portfolio.vol_target 需在 [0.05,1.5]: {vt}")
    ens = pf.get("ensemble")
    if ens is not None:
        if not isinstance(ens, list) or not ens:
            raise ValueError("portfolio.ensemble 必须是非空数组")
        for it in ens:
            if not isinstance(it, dict) or "leg" not in it:
                raise ValueError(f"ensemble 元素需含 leg: {it!r}")
            _w = it.get("weight", (it.get("leg") or {}).get("weight"))
            if _w is None or float(_w) <= 0:
                raise ValueError(f"ensemble 缺少 weight 或 <=0: {it!r}")
    return dict(exposure=expo, cash_asset=str(pf.get("cash_asset") or "cash"),
                sleeves=sl, vol_target=vt, ensemble=ens)


def normalize_spec(spec: dict) -> dict:
    if not isinstance(spec, dict):
        raise ValueError("spec 必须是 dict")
    sel = spec.get("selector") or {}
    if not isinstance(sel, dict):
        raise ValueError("selector 必须是 dict")
    stype = SELECTOR_ALIASES.get(str(sel.get("type", "")).strip(), str(sel.get("type", "")).strip())
    if stype == "ensemble":
        if not (spec.get("portfolio") or {}).get("ensemble"):
            raise ValueError("selector=ensemble 必须在 portfolio.ensemble 里给出 legs")
        stype = "amihud_60"          # 占位选股器；run_sim 会改走 ensemble 合成路径
    if stype not in FACTORS and stype not in CUSTOM_SELECTORS:
        raise ValueError(f"未知 selector: {stype!r}")
    try:
        n = int(sel.get("n"))
    except Exception:
        raise ValueError(f"N 非法: {sel.get('n')!r}")
    if not (1 <= n <= 100):
        raise ValueError(f"N 超范围: {n}")

    size_range = sel.get("size_range", [0.05, 0.30])
    if size_range is not None:
        if not (isinstance(size_range, (list, tuple)) and len(size_range) == 2):
            raise ValueError(f"size_range 非法: {size_range!r}")
        lo, hi = float(size_range[0]), float(size_range[1])
        if not (0.0 <= lo < hi <= 1.0):
            raise ValueError(f"size_range 需 0<=lo<hi<=1: {size_range!r}")
        size_range = (lo, hi)

    mw = _opt_float(sel.get("max_weight"))
    if mw is not None and not (0.05 <= mw <= 1.0):
        raise ValueError(f"selector.max_weight 需在 [0.05,1.0]: {mw}")

    R = int(spec.get("rebalance_days", 30))
    if R < 1:
        raise ValueError(f"rebalance_days 非法: {R}")

    ex = spec.get("exit") or {}
    exit_cfg = dict(trailing_stop=_opt_float(ex.get("trailing_stop")),
                    fixed_stop=_opt_float(ex.get("fixed_stop")),
                    take_profit=_opt_float(ex.get("take_profit")),
                    trailing_take=_opt_float(ex.get("trailing_take")),
                    max_hold_days=_opt_int(ex.get("max_hold_days")),
                    stop_exec=str(ex.get("stop_exec") or "next").lower(),
                    staged_take=_parse_staged(ex.get("staged_take")),
                    tp_fill=str(ex.get("tp_fill") or "close").lower(),
                    tp_trigger=str(ex.get("tp_trigger") or "close").lower(),
                    suspend_exec=str(ex.get("suspend_exec") or "ffill").lower())
    if exit_cfg["stop_exec"] not in EXEC_MODES:
        raise ValueError(f"exit.stop_exec 非法: {exit_cfg['stop_exec']}")
    if exit_cfg["suspend_exec"] not in ("ffill", "defer"):
        raise ValueError(f"exit.suspend_exec 非法: {exit_cfg['suspend_exec']}")
    if exit_cfg["tp_trigger"] not in ("close", "high"):
        raise ValueError(f"exit.tp_trigger 非法: {exit_cfg['tp_trigger']}")
    if exit_cfg["tp_fill"] not in ("close", "target"):
        raise ValueError(f"exit.tp_fill 非法: {exit_cfg['tp_fill']}")
    for k in ("trailing_stop", "fixed_stop", "take_profit", "trailing_take"):
        v = exit_cfg[k]
        if v is not None and not (0 < v < 1):
            raise ValueError(f"exit.{k} 需在 (0,1): {v}")
    if exit_cfg["max_hold_days"] is not None and exit_cfg["max_hold_days"] < 1:
        raise ValueError("exit.max_hold_days 需 >=1")

    tm = spec.get("timing") or {}
    ttype = str(tm.get("type") or "none").lower()
    if ttype not in ("none", "index_ma", "dd_breaker"):
        raise ValueError(f"未知 timing: {ttype}")
    timing = dict(type=ttype, index=str(tm.get("index") or "000905").zfill(6),
                  ma=int(tm.get("ma") or 20),
                  out_asset=str(tm.get("out_asset") or "cash").lower(),
                  dd_trigger=_opt_float(tm.get("dd_trigger")),
                  dd_recover=_opt_float(tm.get("dd_recover")),
                  dd_cut=_opt_float(tm.get("dd_cut")),
                  dd_action=str(tm.get("dd_action") or "clear").lower(),
                  dd_max_off_days=_parse_dd_max_off_days(tm.get("dd_max_off_days")))
    if timing["dd_cut"] is None:
        timing["dd_cut"] = 0.5 if timing["dd_action"] == "half" else 1.0
    if timing["dd_action"] not in ("clear", "half"):
        timing["dd_action"] = "clear" 
    if timing["out_asset"] in ("511880", "sh511880", "bond_511880", "511880.sh"):
        timing["out_asset"] = "bond"
    if timing["out_asset"] not in ("cash", "bond"):
        raise ValueError(f"timing.out_asset 非法: {timing['out_asset']}")

    cost = spec.get("cost") or {}
    ccfg = dict(mode=str(cost.get("mode") or "fixed").lower(),
                one_way=float(cost.get("one_way", 0.005)),
                capital=float(cost.get("capital", 50000)),
                lot_size=int(cost.get("lot_size", 1)),
                slip=float(cost.get("slip", LOT_FEE["slip"])))
    if ccfg["mode"] not in ("fixed", "realistic"):
        raise ValueError(f"cost.mode 非法: {ccfg['mode']}")
    if not (0 <= ccfg["one_way"] < 0.2):
        raise ValueError(f"cost.one_way 非法: {ccfg['one_way']}")
    if ccfg["lot_size"] < 1:
        raise ValueError("cost.lot_size 需 >=1")

    win = spec.get("window") or {}
    window = dict(warmup_start=str(win.get("warmup_start") or DEFAULTS["warmup_start"]),
                  eval_start=str(win.get("eval_start") or DEFAULTS["eval_start"]),
                  eval_end=str(win.get("eval_end") or DEFAULTS["eval_end"]))
    anchor = str(spec.get("rebalance_anchor") or "full300").lower()
    if anchor not in ("full300", "warmup", "legacy_cut"):
        raise ValueError(f"rebalance_anchor 非法: {anchor}")
    phase = int(spec.get("phase", spec.get("rebalance_offset_days", 0)) or 0)
    if not (-60 <= phase <= 60):
        raise ValueError(f"phase 超范围: {phase}")

    hold_exempt = _parse_hold_exempt(sel.get("hold_exempt"))
    absmom = _parse_absmom(sel.get("absmom"))

    return dict(
        id=str(spec.get("id") or "spec"),
        selector=dict(type=stype, n=n,
                      n_eff=(max(n, int(math.ceil(1.0 / mw))) if (mw and bool(sel.get("rank_fill", True))) else n),
                      size_range=size_range,
                      min_adv=float(sel.get("min_adv", 5e6)) if sel.get("min_adv") is not None else 5e6,
                      exclude_star=bool(sel.get("exclude_star", False)),
                      exclude_bj=bool(sel.get("exclude_bj", True)),
                      exclude_chinext=bool(sel.get("exclude_chinext", False)),
                      price_min=_opt_float(sel.get("price_min")),
                      price_max=_opt_float(sel.get("price_max")),
                      exclude_codes=[str(c).zfill(6) for c in (sel.get("exclude_codes") or [])],
                      max_weight=_opt_float(sel.get("max_weight")),
                      rank_fill=bool(sel.get("rank_fill", True)),
                      params=dict(sel.get("params") or {}),
                      hold_exempt=hold_exempt,
                      absmom=absmom),
        portfolio=_portfolio_cfg(spec.get("portfolio") or {}),
        rebalance_days=R, exit=exit_cfg, timing=timing, cost=ccfg,
        window=window, rebalance_anchor=anchor, phase=phase,
        rebalance_gate=_parse_rebalance_gate(spec.get("rebalance_gate")),
        notes=spec.get("notes", ""))


def with_overrides(cfg: dict, **kw) -> dict:
    out = dict(cfg)
    for k, v in kw.items():
        if k in ("exit", "cost", "window", "selector", "timing"):
            out[k] = {**cfg[k], **v}
        else:
            out[k] = v
    return out


# ===========================================================================
# 3. 股票池 / 选股（批次内缓存）
# ===========================================================================
def _universe_key(sel: dict) -> str:
    return json.dumps({k: sel[k] for k in
                       ("size_range", "min_adv", "exclude_star", "exclude_bj",
                        "exclude_chinext", "price_min", "price_max", "exclude_codes")},
                      sort_keys=True)


def universe_matrix(b: Bundle, sel: dict) -> np.ndarray:
    key = _universe_key(sel)
    if key in b._univ:
        return b._univ[key]
    m = b.pool_base.to_numpy(dtype=bool)
    if sel["size_range"] is not None:
        # 逐日截面分位（与 engine.py 的 cap.loc[t].quantile(...) 一致），不是时序分位
        q = b.attr_np(f"capq_{sel['size_range'][0]:.4f}_{sel['size_range'][1]:.4f}",
                      lambda: np.nanquantile(b.cap.to_numpy(dtype=np.float64),
                                             [sel["size_range"][0], sel["size_range"][1]],
                                             axis=1).T)
        cap_np = b.cap.to_numpy(dtype=np.float64)
        with np.errstate(invalid="ignore"):
            m = m & (cap_np >= q[:, 0][:, None]) & (cap_np <= q[:, 1][:, None])
    excl = np.zeros(m.shape[1], dtype=bool)
    if sel["exclude_star"]:
        excl |= b.is_star
    if sel["exclude_bj"]:
        excl |= b.is_bj
    if sel["exclude_chinext"]:
        excl |= b.is_chinext
    if excl.any():
        m = m & (~excl)[None, :]
    if sel["price_min"] is not None:
        m = m & (b.close_np >= sel["price_min"])
    if sel["price_max"] is not None:
        m = m & (b.close_np <= sel["price_max"])
    if sel.get("exclude_codes"):
        idx = [b.codes.get_loc(c) for c in sel["exclude_codes"] if c in b.codes]
        if idx:
            m[:, idx] = False
    m = np.ascontiguousarray(m)
    if len(b._univ) >= 24:
        b._univ.clear()
    b._univ[key] = m
    return m


def _top_n(vals: np.ndarray, n: int) -> np.ndarray:
    v = np.asarray(vals, dtype=np.float64)
    v = np.where(np.isfinite(v), v, -np.inf)
    if v.size == 0 or np.all(np.isneginf(v)):
        return np.empty(0, dtype=np.int64)
    idx = np.argsort(-v, kind="stable")[:n]
    idx = idx[np.isfinite(v[idx])]
    return idx.astype(np.int64)


def _one_pick(b: Bundle, sel: dict, t_pos: int, umask: np.ndarray) -> np.ndarray:
    n, t = sel.get("n_eff", sel["n"]), sel["type"]
    mask = umask[t_pos]
    if not mask.any():
        return np.empty(0, dtype=np.int64)

    if t == "breakout":                       # B: 近 60 日高点（0.97~1.0）内选 Amihud 最大
        hi60 = b.attr_np("hi60", lambda: b.df["close"].rolling(60).max())[t_pos]
        with np.errstate(invalid="ignore", divide="ignore"):
            nh = b.close_np[t_pos] / hi60
        cand = mask & np.isfinite(nh) & (nh > 0.97) & (nh <= 1.0)
        if not cand.any():
            return np.empty(0, dtype=np.int64)
        return _top_n(np.where(cand, _fac_row(b, "amihud", {}, t_pos), -np.inf), n)

    if t == "oversold":                       # C: 深跌(rev20 top5%) + 5日企稳 + Amihud 最大
        pool = np.flatnonzero(mask)
        rev = _fac_row(b, "rev20", {}, t_pos)[pool]
        k = min(max(len(pool) // 20, 30), len(pool))
        order = pool[np.argsort(-np.nan_to_num(rev, nan=-np.inf), kind="stable")[:k]]
        c = b.close_np
        with np.errstate(invalid="ignore", divide="ignore"):
            ret5 = c[t_pos, order] / c[t_pos - 5, order] - 1.0
        firm = order[np.nan_to_num(ret5, nan=-np.inf) > -0.03]
        if not len(firm):
            return np.empty(0, dtype=np.int64)
        vals = np.full(b.n_codes, -np.inf)
        vals[firm] = _fac_row(b, "amihud", {}, t_pos)[firm]
        return _top_n(vals, n)

    return _top_n(np.where(mask, _fac_row(b, t, sel["params"], t_pos), -np.inf), n)


def _ranked_order(b: Bundle, sel: dict, t_pos: int, umask: np.ndarray) -> np.ndarray:
    """与 _one_pick 同口径的完整降序排名（absmom 顺延补足用）。只用 t_pos 及以前数据。"""
    t, params = sel["type"], sel.get("params") or {}
    mask = umask[t_pos]
    if t == "breakout":
        hi60 = b.attr_np("hi60", lambda: b.df["close"].rolling(60).max())[t_pos]
        with np.errstate(invalid="ignore", divide="ignore"):
            nh = b.close_np[t_pos] / hi60
        cand = mask & np.isfinite(nh) & (nh > 0.97) & (nh <= 1.0)
        vals = np.where(cand, _fac_row(b, "amihud", {}, t_pos), -np.inf)
    elif t == "oversold":
        pool = np.flatnonzero(mask)
        if not len(pool):
            return np.empty(0, dtype=np.int64)
        rev = _fac_row(b, "rev20", {}, t_pos)[pool]
        k = min(max(len(pool) // 20, 30), len(pool))
        order = pool[np.argsort(-np.nan_to_num(rev, nan=-np.inf), kind="stable")[:k]]
        c = b.close_np
        with np.errstate(invalid="ignore", divide="ignore"):
            ret5 = c[t_pos, order] / c[t_pos - 5, order] - 1.0
        firm = order[np.nan_to_num(ret5, nan=-np.inf) > -0.03]
        if not len(firm):
            return np.empty(0, dtype=np.int64)
        vals = np.full(b.n_codes, -np.inf)
        vals[firm] = _fac_row(b, "amihud", {}, t_pos)[firm]
    else:
        vals = np.where(mask, _fac_row(b, t, params, t_pos), -np.inf)
    v = np.where(np.isfinite(vals), vals, -np.inf)
    order = np.argsort(-v, kind="stable")
    return order[np.isfinite(v[order])].astype(np.int64)


def _apply_absmom(b: Bundle, sel: dict, t_pos: int, um, base: np.ndarray) -> np.ndarray:
    """绝对动量过滤 + 按原排名顺延补足到 len(base)。收盘只用信号日(t_pos)及以前。"""
    am = sel.get("absmom")
    order = _ranked_order(b, sel, t_pos, um)
    if len(order) == 0:
        return np.empty(0, dtype=np.int64)
    c = b.close_ff_np
    ok = np.zeros(len(order), dtype=bool)
    if am.get("ma") is not None:
        ma = int(am["ma"])
        if t_pos - ma + 1 >= 0:
            px = c[t_pos, order]
            win = c[t_pos - ma + 1:t_pos + 1][:, order]
            with np.errstate(invalid="ignore"):
                m = win.mean(axis=0)
            ok = np.isfinite(px) & np.all(np.isfinite(win), axis=0) & (px > m)
    else:
        L, S = [int(x) for x in am["mom_skip"]]
        e, s = t_pos - S, t_pos - L
        if s >= 0:
            p0 = c[s, order]
            p1 = c[e, order]
            with np.errstate(invalid="ignore", divide="ignore"):
                r = p1 / p0 - 1.0
            ok = np.isfinite(p0) & np.isfinite(p1) & (p0 > 0) & (r > 0)
    keep = [int(j) for j, f in zip(order.tolist(), ok.tolist()) if f][:len(base)]
    return np.asarray(keep, dtype=np.int64)


def _exempt_holds(b: Bundle, sel: dict, umask: np.ndarray, t: int, held: list) -> set:
    """持仓豁免判定（信号日 t=执行日-1）：收盘>MA(ma)×tol 且截面因子排名前 rank_band。

    排名用与选股同一因子行（breakout/oversold 用 amihud 行），分母为信号日
    universe 有效且因子有限的截面；MA/排名/回报只用 ≤t 收盘，无未来函数。"""
    he = sel.get("hold_exempt")
    if not he or not held:
        return set()
    ma = int(he["ma"])
    tol = float(he["tol"])
    rb = float(he["rank_band"])
    if t - ma + 1 < 0:
        return set()
    c = b.close_ff_np
    ftype = "amihud" if sel["type"] in ("breakout", "oversold") else sel["type"]
    vals = _fac_row(b, ftype, sel.get("params") or {}, t)
    mask = umask[t]
    finite = np.isfinite(vals) & mask
    if not bool(finite.any()):
        return set()
    fv = np.where(finite, vals, -np.inf)
    n_valid = int(finite.sum())
    out = set()
    for j in held:
        if not (0 <= j < b.n_codes) or not finite[j]:
            continue
        px = c[t, j]
        if not np.isfinite(px):
            continue
        win = c[t - ma + 1:t + 1, j]
        if not bool(np.all(np.isfinite(win))):
            continue
        if not (float(px) > float(win.mean()) * tol):
            continue
        rank_pos = int(np.sum(fv > fv[j])) + 1
        if rank_pos / n_valid <= rb:
            out.add(j)
    return out


def picks_at(b: Bundle, sel: dict, t_pos: int) -> np.ndarray:
    am = sel.get("absmom")
    key = "|".join([sel["type"], _universe_key(sel), str(sel.get("n_eff", sel["n"])),
                    json.dumps(sel["params"], sort_keys=True), str(t_pos)])
    if am is not None:
        key += "|abs=" + json.dumps(am, sort_keys=True)
    got = b._picks.get(key)
    if got is not None:
        return got
    um = universe_matrix(b, sel)
    if int(um[t_pos].sum()) < sel.get("n_eff", sel["n"]):
        out = np.empty(0, dtype=np.int64)
    else:
        out = _one_pick(b, sel, t_pos, um)
        if am is not None and len(out):
            out = _apply_absmom(b, sel, t_pos, um, out)
    b._picks[key] = out
    return out


# ===========================================================================
# 4. 择时信号
# ===========================================================================
def _timing_on(b: Bundle, cfg: dict) -> np.ndarray | None:
    tm = cfg["timing"]
    if tm["type"] != "index_ma":
        return None
    f = IDX_CACHE / f"index_{tm['index']}.pkl"
    if not f.exists():
        raise FileNotFoundError(f"缺少指数缓存 {f}")
    s = pd.read_pickle(f).astype(float)
    s = s.reindex(s.index.union(b.dates)).ffill().reindex(b.dates)
    ma = s.rolling(tm["ma"]).mean()
    return (s > ma).shift(1).fillna(True).to_numpy(dtype=bool)   # 只用 t-1 及以前


# ===========================================================================
# 5. 回测核心
# ===========================================================================
def _buy_cost(notional: float, cfg: dict) -> float:
    c = cfg["cost"]
    if c["mode"] == "fixed":
        return notional * c["one_way"]
    return (max(notional * LOT_FEE["comm"], LOT_FEE["min_comm"])
            + notional * (LOT_FEE["transfer"] + c.get("slip", LOT_FEE["slip"])))


def _sell_cost(notional: float, cfg: dict) -> float:
    c = cfg["cost"]
    if c["mode"] == "fixed":
        return notional * c["one_way"]
    return (max(notional * LOT_FEE["comm"], LOT_FEE["min_comm"])
            + notional * (LOT_FEE["stamp"] + LOT_FEE["transfer"] + c.get("slip", LOT_FEE["slip"])))


def _grid_positions(b: Bundle, cfg: dict) -> list[int]:
    """调仓**信号日**位置（切片坐标）；执行日 = 信号日 + 1。"""
    R = cfg["rebalance_days"]
    phase = cfg["phase"]
    warm_ts = pd.Timestamp(cfg["window"]["warmup_start"])
    warm = b.pos.get(warm_ts)
    if warm is None:
        warm = int(np.searchsorted(b.dates, warm_ts))
    anchor = cfg["rebalance_anchor"]
    nf = len(b.full_dates)

    if anchor == "full300":
        full = [i + phase for i in range(300, nf - 1, R)]
        cand = [i - b.offset for i in full if 0 <= i < nf]
    elif anchor == "legacy_cut":                     # 旧口径（仅用于差异定位，不用于结论）
        full = [i + phase for i in range(300, nf - R - 2, R)]
        cand = [i - b.offset for i in full if 0 <= i < nf]
    else:                                            # warmup 相位
        cand = [p + phase for p in range(warm, b.n_dates - 1, R)]

    out = [p for p in cand if warm <= p <= b.n_dates - 2]
    return sorted(set(out))


def _apply_rebalance_gate(b, cfg, umask, t_sig, holds_keys, picks):
    """R7-A/B/C 门控。只用信号日 t_sig 及以前数据，无未来函数。
    返回 (do_rebal, sell_list, buy_list, gate_info)。holds_keys=list[int]。
    """
    gate = cfg.get("rebalance_gate")
    info = dict(gate=(gate["type"] if gate else "none"), overlap=0)
    holds_set = set(holds_keys)
    picks = list(picks)
    picks_set = set(picks)
    if not holds_set and picks:
        info["first_build"] = True
        return True, [], picks, info
    if not gate:
        if set(picks) != holds_set:
            return True, list(holds_keys), picks, info
        return False, [], [], info
    n = int(cfg["selector"]["n"])
    overlap = len(holds_set & picks_set)
    info["overlap"] = overlap
    gtype = gate["type"]
    if gtype == "overlap":
        if overlap >= int(gate["min_overlap"]):
            info["skip"] = True
            return False, [], [], info
        return True, list(holds_keys), picks, info
    if gtype == "cost_aware":
        if overlap >= int(gate["min_overlap"]):
            info["skip"] = "overlap"
            try:
                nD = b.n_dates
                t7 = min(int(t_sig) + 7, nD - 1); t14 = min(int(t_sig) + 14, nD - 1)
                cF = b.close_ff_np
                def _bret0(js, ta, tb):
                    js = [j for j in js if 0 <= j < b.n_codes and np.isfinite(cF[ta, j]) and np.isfinite(cF[tb, j]) and cF[ta, j] > 0]
                    if not js:
                        return np.nan
                    return float(np.nanmean([cF[tb, j] / cF[ta, j] - 1.0 for j in js]))
                f7 = _bret0(picks, int(t_sig), t7) - _bret0(list(holds_keys), int(t_sig), t7)
                f14 = _bret0(picks, int(t_sig), t14) - _bret0(list(holds_keys), int(t_sig), t14)
                info["fwd7"] = float(f7) if np.isfinite(f7) else None
                info["fwd14"] = float(f14) if np.isfinite(f14) else None
            except Exception:
                pass
            return False, [], [], info
        # U=Δα-C-λσ：Δα=新旧篮子过去20日收益差；C=预估双边成本率×换手比例；σ= involved 20日波动均值
        try:
            c = b.close_ff_np
            t = int(t_sig)
            lo = max(t - 20, 1)
            def basket_ret(js):
                js = [j for j in js if 0 <= j < b.n_codes and np.isfinite(c[t, j]) and np.isfinite(c[lo, j]) and c[lo, j] > 0]
                if not js:
                    return np.nan, np.nan
                r = np.nanmean([c[t, j] / c[lo, j] - 1.0 for j in js])
                vols = []
                for j in js:
                    w = c[lo:t + 1, j]
                    if np.all(np.isfinite(w)) and np.all(w > 0):
                        rr = w[1:] / w[:-1] - 1.0
                        vols.append(float(np.std(rr, ddof=1)) if len(rr) > 2 else 0.0)
                return float(r), (float(np.mean(vols)) if vols else 0.0)
            r_new, _ = basket_ret(picks)
            r_old, _ = basket_ret(list(holds_keys))
            js_all = list(set(picks) | holds_set)
            _, sig = basket_ret(js_all)
            dalpha = (r_new - r_old) if (np.isfinite(r_new) and np.isfinite(r_old)) else np.nan
            turnover_frac = 1.0 - overlap / max(len(picks_set | holds_set), 1)
            # realistic 双边约 0.45%+滑点，fixed 0.5%一边；用 max 保守估计
            cc = cfg["cost"]
            if cc["mode"] == "realistic":
                c_rate = 2 * (0.00025 + 0.001 + 0.00001) + 0.0005 + 2 * float(cc.get("slip", 0.002))
            else:
                c_rate = 2 * float(cc.get("one_way", 0.005))
            C = turnover_frac * c_rate
            lam = float(gate.get("lam", 1.0))
            U = dalpha - C - lam * (sig if np.isfinite(sig) else 0.0)
            info.update(dict(dalpha=float(dalpha) if np.isfinite(dalpha) else None,
                             C=float(C), sigma=float(sig) if np.isfinite(sig) else None,
                             U=float(U) if np.isfinite(U) else None, lam=lam))
            # 诊断专用：记录执行后7/14日新旧篮子收益差（只写日志，不参与决策，无未来函数问题）
            try:
                nD = b.n_dates
                t7 = min(t + 7, nD - 1); t14 = min(t + 14, nD - 1)
                cF = b.close_ff_np
                def _bret(js, ta, tb):
                    js = [j for j in js if 0 <= j < b.n_codes and np.isfinite(cF[ta, j]) and np.isfinite(cF[tb, j]) and cF[ta, j] > 0]
                    if not js:
                        return np.nan
                    return float(np.nanmean([cF[tb, j] / cF[ta, j] - 1.0 for j in js]))
                f7 = _bret(picks, t, t7) - _bret(list(holds_keys), t, t7)
                f14 = _bret(picks, t, t14) - _bret(list(holds_keys), t, t14)
                info["fwd7"] = float(f7) if np.isfinite(f7) else None
                info["fwd14"] = float(f14) if np.isfinite(f14) else None
            except Exception:
                pass
            if not np.isfinite(U) or U <= 0:
                info["skip"] = "U<=0"
                return False, [], [], info
            return True, list(holds_keys), picks, info
        except Exception as e:
            info["err"] = str(e)[:120]
            return True, list(holds_keys), picks, info
    # rank_hold / dynamic 共用：保留仍在前 keep_rank 的持仓
    keep_rank = int(gate.get("keep_rank", 8))
    try:
        order = _ranked_order(b, cfg["selector"], int(t_sig), umask)
        keep_set = set(order[:keep_rank].tolist())
    except Exception:
        keep_set = picks_set
    if gtype == "rank_hold":
        keep_holds = [j for j in holds_keys if j in keep_set]
        # 目标=保留的旧仓 + 按排名补足到 N（优先 picks 中未持有的）
        want = []
        for j in picks:
            if j not in holds_set:
                want.append(j)
        # 若保留+新选不足 N，用排名顺延补
        target = list(dict.fromkeys(keep_holds + want))[:n]
        if len(target) < n:
            try:
                for j in order.tolist():
                    if j not in target and j not in holds_set:
                        target.append(j)
                    if len(target) >= n:
                        break
            except Exception:
                pass
        target_set = set(target)
        if target_set == holds_set:
            info["skip"] = True
            return False, [], [], info
        info["mode"] = "partial"
        info["n_keep"] = len([j for j in holds_keys if j in target_set])
        sell_list = [j for j in holds_keys if j not in target_set]
        buy_list = [j for j in target if j not in holds_set]
        return True, sell_list, buy_list, info
    # dynamic
    ft = int(gate.get("full_threshold", 1))
    if overlap == n and len(holds_set) == n:
        info["state"] = "A"
        info["skip"] = True
        return False, [], [], info
    if overlap > ft:
        info["state"] = "B"
        keep_holds = [j for j in holds_keys if j in keep_set]
        want = [j for j in picks if j not in holds_set]
        target = list(dict.fromkeys(keep_holds + want))[:n]
        if len(target) < n:
            try:
                for j in order.tolist():
                    if j not in target and j not in holds_set:
                        target.append(j)
                    if len(target) >= n:
                        break
            except Exception:
                pass
        if set(target) == holds_set:
            info["skip"] = True
            return False, [], [], info
        info["mode"] = "partial"
        return True, [j for j in holds_keys if j not in set(target)], [j for j in target if j not in holds_set], info
    info["state"] = "C"
    return True, list(holds_keys), picks, info


def _apply_asymmetric_gate(b, cfg, umask, t_sig, pos, holds, picks):
    """R7-D 非对称调仓：entry 每 entry_R 全量吸纳新面孔，exit 按年龄(exit_R)或信号死亡(exit_rank)卖出。
    holds: dict j->{...,'pos':建仓执行日}；pos: 本次执行日；t_sig: 信号日(=pos-1)。
    只用≤t_sig 数据 + 执行计数器，无未来函数。返回 (do_rebal, sell_list, buy_list, gate_info)。"""
    gate = cfg.get("rebalance_gate") or {}
    info = dict(gate="asymmetric")
    holds_keys = list(holds.keys())
    holds_set = set(holds_keys)
    picks = list(picks)
    if not holds_set and picks:
        info["first_build"] = True
        return True, [], picks, info
    exit_R = gate.get("exit_R", None)
    exit_rank = gate.get("exit_rank", None)
    sell = []
    age_max = 0
    for j in holds_keys:
        h = holds.get(j, {})
        try:
            age = int(pos) - int(h.get("pos", pos))
        except Exception:
            age = 0
        age_max = max(age_max, age)
        if exit_R is not None and age >= int(exit_R):
            sell.append(j)
    death = []
    if exit_rank is not None:
        try:
            order = _ranked_order(b, cfg["selector"], int(t_sig), umask)
            rankpos = {int(j): i + 1 for i, j in enumerate(order.tolist())}
        except Exception:
            rankpos = {}
        kr = int(exit_rank)
        for j in holds_keys:
            rp = rankpos.get(int(j), None)
            if rp is None or rp > kr:
                death.append(j)
    # 过期但被新 picks 重选：等价无成本再买入（刷新建仓日+成本价+最高价，thesis 续存），
    # 不做先卖后买的 wash。TP45 时钟与 BASE 的每周重买语义对齐。
    picks_set = set(picks)
    refreshed = 0
    _pxrow = b.close_ff_np[int(pos)]
    for j in list(dict.fromkeys(sell + death)):
        if j in picks_set:
            try:
                px = float(_pxrow[j])
                if px == px and px > 0:
                    holds[j]["pos"] = int(pos)
                    holds[j]["px"] = px
                    if px > float(holds[j].get("high", px)):
                        holds[j]["high"] = px
                    refreshed += 1
            except Exception:
                pass
    sell = [j for j in dict.fromkeys(sell + death) if j not in picks_set]
    death_ids = [j for j in dict.fromkeys(death) if j not in picks_set]
    info["asym_death_ids"] = death_ids
    retained = set(holds_keys) - set(sell)
    buy = [j for j in picks if j not in retained]
    info.update(dict(overlap=len(holds_set & picks_set), asym_exit_n=len(sell),
                     asym_death_n=len([j for j in death if j not in picks_set]),
                     asym_age_max=int(age_max), asym_refreshed=int(refreshed)))
    if not sell and not buy:
        info["skip"] = True
        return False, [], [], info
    info["mode"] = "partial"
    return True, sell, buy, info


def simulate(cfg: dict) -> dict:
    b = bundle()
    dates = b.dates
    nD = b.n_dates
    c_np = b.close_ff_np          # ffill 后的收盘（估值/成交价）
    raw_np = b.close_np           # 原始收盘（NaN = 停牌）
    lim_ratio = b.limit_down_ratio
    sig_pos = _grid_positions(b, cfg)
    if not sig_pos:
        raise ValueError("窗口内没有调仓信号日")
    sim_start = sig_pos[0]
    ev_end = b.pos.get(pd.Timestamp(cfg["window"]["eval_end"]))
    if ev_end is None:
        ev_end = int(np.searchsorted(dates, pd.Timestamp(cfg["window"]["eval_end"]), "right") - 1)
    ev_end = min(ev_end, nD - 1)
    if ev_end <= sim_start:
        raise ValueError("eval_end 早于首个调仓执行日")

    exec_map: dict[int, list[int]] = {}
    for p in sig_pos:
        if p + 1 > ev_end:
            break
        exec_map[p + 1] = picks_at(b, cfg["selector"], p).tolist()

    timing_on = _timing_on(b, cfg)
    tm = cfg["timing"]
    bond = b.bond_ret() if tm["out_asset"] == "bond" else None
    stop_next = cfg["exit"]["stop_exec"] == "next"
    real = cfg["cost"]["mode"] == "realistic"
    lot = cfg["cost"]["lot_size"] if real else 1
    budget_pad = (1.0 + cfg["cost"]["one_way"]) if not real else \
        (1.0 + LOT_FEE["comm"] + LOT_FEE["transfer"] + cfg["cost"].get("slip", LOT_FEE["slip"]))
    dd_cut = float(tm["dd_cut"]) if tm["type"] == "dd_breaker" and tm["dd_cut"] is not None else 0.0
    dd_max_off = tm.get("dd_max_off_days") if tm["type"] == "dd_breaker" else None
    expo_frac = float(cfg.get("portfolio", {}).get("exposure", 1.0))
    vol_target = cfg.get("portfolio", {}).get("vol_target")
    mw = cfg["selector"].get("max_weight")
    staged = cfg["exit"].get("staged_take")
    n_staged = 0
    dd_state = True
    dd_off_days = 0
    code_list = list(b.codes)
    star_mask = b.is_star
    _gate = cfg.get("rebalance_gate") or {}
    _need_umask = bool(cfg["selector"].get("hold_exempt")) or _gate.get("type") in ("rank_hold", "dynamic") or (_gate.get("type") == "asymmetric" and _gate.get("exit_rank") is not None)
    umask = universe_matrix(b, cfg["selector"]) if _need_umask else None

    cash0 = float(cfg["cost"]["capital"]) if real else 1.0
    cash = cash0
    holds: dict[int, dict] = {}
    pending: dict[int, dict] = {}          # j -> {reason, deferred, limit_down}
    eq_path = np.full(nD, np.nan)
    cost_path = np.zeros(nD)
    expo_path = np.full(nD, np.nan)
    nhold_path = np.zeros(nD)
    starhold_path = np.zeros(nD)
    wmax_path = np.zeros(nD)
    trades: list[dict] = []
    rebal: list[dict] = []
    cost_total = 0.0
    peak = 0.0
    n_trigger = 0
    n_deferred = 0
    n_ld = 0

    def sell(j, pos, px, reason):
        nonlocal cash, cost_total
        h = holds.pop(j)
        pending.pop(j, None)
        notional = h["shares"] * px
        fee = _sell_cost(notional, cfg)
        cash += notional - fee
        cost_total += fee
        pnl = notional - fee - h["notional"] - h["cost"]
        trades.append(dict(code=code_list[j], entry_pos=h["pos"], exit_pos=pos,
                           entry_date=dates[h["pos"]], exit_date=dates[pos],
                           shares=h["shares"], entry_px=h["px"], exit_px=px,
                           notional=h["notional"], cost=h["cost"] + fee, pnl=pnl,
                           ret=pnl / (h["notional"] + h["cost"]) if h["notional"] > 0 else 0.0,
                           reason=reason))

    def sell_partial(j, pos, px, level_idx, frac, reason):
        """卖出当前剩余持仓的 frac（分批止盈的一档）。"""
        nonlocal cash, cost_total
        h = holds.get(j)
        if h is None:
            pending.pop(j, None)
            return
        if level_idx in h.get("staged_hit", ()):
            return
        q = h["shares"] * frac
        q = min(q, h["shares"])
        if q <= 1e-12:
            return
        if frac >= 0.999 or q >= h["shares"] - 1e-9:
            sell(j, pos, px, reason)
            return
        notional = q * px
        fee = _sell_cost(notional, cfg)
        cash += notional - fee
        cost_total += fee
        cost_part = h["notional"] * q / h["shares"]
        buyfee_part = h["cost"] * q / h["shares"]
        pnl = notional - fee - cost_part - buyfee_part
        trades.append(dict(code=code_list[j], entry_pos=h["pos"], exit_pos=pos,
                           entry_date=dates[h["pos"]], exit_date=dates[pos],
                           shares=q, entry_px=h["px"], exit_px=px,
                           notional=cost_part, cost=buyfee_part + fee, pnl=pnl,
                           ret=pnl / (cost_part + buyfee_part) if cost_part > 0 else 0.0,
                           reason=reason))
        h["shares"] -= q
        h["notional"] -= cost_part
        h["cost"] -= buyfee_part
        h.setdefault("staged_hit", []).append(level_idx)
        h["staged_sells"] = h.get("staged_sells", 0) + 1
        h["staged_pnl"] = h.get("staged_pnl", 0.0) + pnl
        if h["shares"] <= 1e-9:
            holds.pop(j, None)
            pending.pop(j, None)

    def tradable(pos, j):
        """(是否可成交, 是否跌停)。

        停牌（原始收盘 NaN）：默认按 PROTOCOL §1 用停牌前收盘 ffill 成交（suspend_exec="ffill"）；
        设成 "defer" 则顺延到下一可成交日。跌停：默认顺延。
        """
        px = raw_np[pos, j]
        if not np.isfinite(px):
            if cfg["exit"].get("suspend_exec", "ffill") == "ffill":
                return True, False
            return False, False
        if pos > 0:
            prev = c_np[pos - 1, j]
            if np.isfinite(prev) and px <= prev * lim_ratio[j] * 1.0005:
                return False, True
        return True, False

    for pos in range(sim_start, ev_end + 1):
        px_row = c_np[pos]
        hi_row = b.df["high"].to_numpy(dtype=np.float32)[pos] if cfg["exit"].get("tp_trigger") == "high" else None
        if bond is not None:
            cash *= (1.0 + float(bond[pos]))

        # ---------- (0) 执行上一交易日触发的离场（stop_exec="next"；跌停/停牌顺延） ----------
        for j, meta in list(pending.items()):
            if j not in holds:
                pending.pop(j, None)
                continue
            if not np.isfinite(px_row[j]):
                continue
            ok, is_ld = tradable(pos, j)
            if not ok:
                if not meta["deferred"]:
                    meta["deferred"] = True
                    if is_ld:
                        meta["limit_down"] = True
                continue
            if meta.get("kind") == "staged":
                for i in meta.get("levels", []):
                    if j in holds:
                        sell_partial(j, pos, px_row[j], i, staged[i][1], meta["reason"])
            else:
                _px = px_row[j]
                if (meta["reason"] == "take_profit" and cfg["exit"].get("tp_fill") == "target"
                        and j in holds):
                    _px = holds[j]["px"] * (1.0 + cfg["exit"]["take_profit"])
                sell(j, pos, _px, meta["reason"])

        # ---------- (1) 每日收盘判断离场触发（止损优先于止盈） ----------
        if holds:
            ex = cfg["exit"]
            for j in list(holds.keys()):
                px = px_row[j]
                if not np.isfinite(px):
                    continue
                h = holds[j]
                if px > h["high"]:
                    h["high"] = px
                reason = None
                if ex["trailing_stop"] is not None and px <= h["high"] * (1.0 - ex["trailing_stop"]):
                    reason = "trailing_stop"
                elif ex["fixed_stop"] is not None and px <= h["px"] * (1.0 - ex["fixed_stop"]):
                    reason = "fixed_stop"
                elif staged and _staged_levels(staged, h, px):
                    reason = "staged_take"
                elif ex["take_profit"] is not None and (
                        (hi_row[j] if (ex.get("tp_trigger") == "high" and hi_row is not None
                                       and np.isfinite(hi_row[j])) else px)
                        >= h["px"] * (1.0 + ex["take_profit"])):
                    reason = "take_profit"
                elif ex["trailing_take"] is not None and h["high"] > h["px"]:
                    if (h["high"] - px) >= ex["trailing_take"] * (h["high"] - h["px"]):
                        reason = "trailing_take"
                elif ex["max_hold_days"] is not None and (pos - h["pos"]) >= ex["max_hold_days"]:
                    reason = "max_hold_days"
                if reason and j not in pending:
                    partial = reason == "staged_take"
                    lv = _staged_levels(staged, h, px) if partial else []
                    if partial:
                        n_staged += len(lv)
                    else:
                        n_trigger += 1
                    if stop_next:
                        ok, is_ld = tradable(pos, j)
                        pending[j] = dict(reason=reason, deferred=not ok, limit_down=is_ld and not ok,
                                          kind=("staged" if partial else "full"), levels=lv)
                        if not ok:
                            n_deferred += 1
                            if is_ld:
                                n_ld += 1
                    else:
                        ok, is_ld = tradable(pos, j)
                        if not ok:
                            n_deferred += 1
                            if is_ld:
                                n_ld += 1
                        if partial:
                            for i in lv:
                                sell_partial(j, pos, px, i, staged[i][1], reason)
                        else:
                            sell(j, pos, px, reason)

        # ---------- (2) 调仓执行日 ----------
        is_exec = pos in exec_map
        if is_exec:
            mv_before = sum(holds[j]["shares"] * px_row[j] for j in holds if np.isfinite(px_row[j]))
            eq_before = cash + mv_before
            on = True
            if timing_on is not None:
                on = bool(timing_on[max(pos - 1, 0)])
            cut_cash = 0.0
            if tm["type"] == "dd_breaker":
                dd = (eq_before / peak - 1.0) if peak > 0 else 0.0
                trig = tm["dd_trigger"] if tm["dd_trigger"] is not None else -0.08
                rec = tm["dd_recover"] if tm["dd_recover"] is not None else -0.02
                if dd_state and dd <= trig:
                    dd_state = False
                elif (not dd_state) and dd >= rec:
                    dd_state = True
                if dd_state:
                    dd_off_days = 0
                elif dd_max_off is not None:
                    # 离场执行日计数（只用计数器，无未来函数）；超限强制恢复
                    dd_off_days += 1
                    if dd_off_days > dd_max_off:
                        dd_state = True
                        dd_off_days = 0
                if not dd_state:
                    if dd_cut >= 1.0:
                        on = False
                    else:
                        cut_cash = dd_cut
            picks = exec_map[pos] if on else []

            vol_scale = 1.0
            if vol_target and on and pos - 1 > sim_start:
                lo = max(sim_start, pos - 21)
                e = eq_path[lo:pos]
                e = e[np.isfinite(e)]
                if len(e) >= 21:
                    rr = e[1:] / e[:-1] - 1.0
                    rv = float(np.std(rr, ddof=1) * math.sqrt(252))
                    if rv > 1e-9:
                        vol_scale = float(min(1.0, vol_target / rv))
            sold = 0.0
            he = cfg["selector"].get("hold_exempt")
            exempt: set = set()
            if he and on and len(holds):
                # 豁免判定信号日 t=pos-1，只用 ≤t 收盘/因子；豁免票保留 high/pos/staged_done
                exempt = _exempt_holds(b, cfg["selector"], umask, pos - 1,
                                        list(holds.keys()))
            gate_info: dict = dict(gate="none")
            if he and on:
                eff_set = set(picks) | exempt
                do_rebal = set(eff_set) != set(holds.keys())
                sell_list = [j for j in list(holds.keys()) if j not in eff_set]
                buy_list = [j for j in picks if j not in holds]
            elif cfg.get("rebalance_gate") and (cfg["rebalance_gate"].get("type") == "asymmetric") and on:
                if int(cfg["rebalance_gate"].get("entry_R", 7)) != int(cfg["rebalance_days"]):
                    raise ValueError("asymmetric.entry_R 须等于 rebalance_days(Entry网格即调仓网格)")
                do_rebal, sell_list, buy_list, gate_info = _apply_asymmetric_gate(
                    b, cfg, umask, pos - 1, pos, dict(holds), list(picks))
            elif cfg.get("rebalance_gate") and on and len(holds):
                do_rebal, sell_list, buy_list, gate_info = _apply_rebalance_gate(
                    b, cfg, umask, pos - 1, list(holds.keys()), list(picks))
            else:
                do_rebal = (not on) or set(picks) != set(holds.keys())
                sell_list = list(holds.keys())
                buy_list = list(picks)
            if do_rebal:
                _death = set(gate_info.get("asym_death_ids", []) or [])
                for j in sell_list:
                    px = px_row[j]
                    if not np.isfinite(px):
                        continue
                    sold += holds[j]["shares"] * px
                    sell(j, pos, px, "signal_death" if j in _death else "rebalance")
                bought = 0.0
                if buy_list:
                    _partial = bool(gate_info.get("mode") == "partial") or gate_info.get("gate") == "asymmetric"
                    if _partial:
                        # 部分调仓：按调仓前权益定等权目标（否则新票被系统性低配 N 倍）
                        budget = eq_before * expo_frac * vol_scale * (1.0 - cut_cash)
                    else:
                        budget = cash * expo_frac * vol_scale * (1.0 - cut_cash)
                    k = len(picks)
                    w = min(1.0 / k, mw) if mw else 1.0 / k
                    per = budget / budget_pad * w
                    for j in buy_list:
                        px = px_row[j]
                        if not np.isfinite(px) or px <= 0:
                            continue
                        sh = per / px
                        if lot > 1:
                            sh = math.floor(sh / lot) * lot
                        if sh <= 0:
                            continue
                        notional = sh * px
                        fee = _buy_cost(notional, cfg)
                        if notional + fee > cash:
                            sh = min(per, cash / budget_pad) / px
                            if lot > 1:
                                sh = math.floor(sh / lot) * lot
                            if sh <= 0:
                                continue
                            notional = sh * px
                            fee = _buy_cost(notional, cfg)
                            if notional + fee > cash + 1e-12:
                                continue
                        cash -= notional + fee
                        cost_total += fee
                        bought += notional
                        holds[j] = dict(shares=sh, orig=sh, px=px, notional=notional, cost=fee,
                                        high=px, pos=pos, staged_done=0.0)
                eq_after = cash + sum(holds[j]["shares"] * px_row[j]
                                      for j in holds if np.isfinite(px_row[j]))
                one_way = (sold + bought) / 2.0 / max(eq_after, 1e-12)
            else:
                one_way = 0.0
            _gi = dict(gate_info) if isinstance(gate_info, dict) else dict(gate="none")
            rebal.append(dict(pos=pos, one_way=one_way, on=bool(on), n_picks=len(picks),
                              n_base=int(cfg["selector"]["n"]), mw=mw,
                              dd_state=bool(dd_state), vol_scale=vol_scale,
                              n_exempt=len(exempt), dd_off_days=int(dd_off_days),
                              gate=_gi.get("gate", "none"), overlap=_gi.get("overlap", 0),
                              gate_skip=bool(_gi.get("skip", False)), gate_state=_gi.get("state", ""),
                              gate_U=_gi.get("U"), gate_mode=_gi.get("mode", ""),
                              gate_dalpha=_gi.get("dalpha"), gate_fwd7=_gi.get("fwd7"),
                              gate_fwd14=_gi.get("fwd14"),
                              asym_exit_n=_gi.get("asym_exit_n", 0), asym_death_n=_gi.get("asym_death_n", 0),
                              asym_age_max=_gi.get("asym_age_max", 0)))

        # ---------- (3) 记录净值 ----------
        mv = sum(holds[j]["shares"] * px_row[j] for j in holds if np.isfinite(px_row[j]))
        eq = cash + mv
        eq_path[pos] = eq
        cost_path[pos] = cost_total
        expo_path[pos] = mv / eq if eq > 1e-12 else 0.0
        nhold_path[pos] = len(holds)
        starhold_path[pos] = sum(1 for j in holds if star_mask[j])
        wmax_path[pos] = (max((holds[j]["shares"] * px_row[j] for j in holds
                               if np.isfinite(px_row[j])), default=0.0) / eq) if eq > 1e-12 else 0.0
        if eq > peak:
            peak = eq
        if is_exec:
            rebal[-1]["exposure"] = expo_path[pos]
            rebal[-1]["equity"] = eq

    if cash0 != 1.0:
        eq_path = eq_path / cash0
        cost_path = cost_path / cash0
    sl = slice(sim_start, ev_end + 1)
    eq_s = pd.Series(eq_path[sl], index=dates[sl])
    tr = pd.DataFrame(trades)
    if len(tr):
        tr = tr.sort_values(["exit_pos", "code"]).reset_index(drop=True)
    return dict(cfg=cfg, equity=eq_s, eq_full=eq_path, cost_full=cost_path,
                expo_full=expo_path, nhold_full=nhold_path, starhold_full=starhold_path,
                wmax_full=wmax_path,
                trades=tr, rebal=rebal, sim_start=sim_start, ev_end=ev_end,
                sig_pos=sig_pos, exec_map=exec_map, n_trigger=n_trigger,
                n_deferred=n_deferred, n_limit_down=n_ld, n_staged=n_staged,
                staged_pnl_total=sum(h.get("staged_pnl", 0.0) for h in holds.values()),
                anchor_first_date=str(dates[sig_pos[0] + 1].date()) if sig_pos[0] + 1 < nD else "")


# ---------------------------------------------------------------------------
# 5b. sleeve（多相位资金等分）支持
# ---------------------------------------------------------------------------
def sleeve_offsets(cfg: dict) -> list[int] | None:
    sl = (cfg.get("portfolio") or {}).get("sleeves")
    if not sl:
        return None
    offs = [int(x) for x in (sl.get("offsets") or [-8, 0, 8])]
    return offs if len(offs) >= 2 else None


def _simulate_sleeves(cfg: dict, offsets: list[int]) -> dict:
    """资金等分 M 份，每份用 phase+offset 独立再投资；合成净值 = 各份净值算术平均。

    realistic 口径下**必须把本金也等分**（每份 capital/M），否则整手撮合会按「每份都有全额本金」
    计算，5 万三/五等分时真实能买到的票会被高估（auditor 2026-11-05 发现）。
    """
    sub = cfg
    if cfg["cost"]["mode"] == "realistic" and len(offsets) > 1:
        sub = with_overrides(cfg, cost={"capital": float(cfg["cost"]["capital"]) / len(offsets)})
    sims = [simulate(with_overrides(sub, phase=cfg["phase"] + o)) for o in offsets]
    nD = bundle().n_dates
    mats = []
    for s in sims:
        e = s["eq_full"].copy()
        e[~np.isfinite(e)] = 1.0
        mats.append(e)
    comp = np.mean(mats, axis=0)

    def _mean_attr(key):
        out = np.zeros(nD)
        for s in sims:
            a = np.asarray(s[key], dtype=float)
            out += np.where(np.isfinite(a), a, 0.0)
        return out / len(sims)

    def _sum_attr(key):
        out = np.zeros(nD)
        for s in sims:
            a = np.asarray(s[key], dtype=float)
            out += np.where(np.isfinite(a), a, 0.0)
        return out

    trades = pd.concat([s["trades"].assign(sleeve=o) for s, o in zip(sims, offsets)
                        if len(s["trades"])], ignore_index=True) if any(len(s["trades"]) for s in sims) \
        else pd.DataFrame()
    base = sims[len(sims) // 2]
    synth = dict(cfg=cfg, equity=None, eq_full=comp,
                 cost_full=_mean_attr("cost_full"), expo_full=_mean_attr("expo_full"),
                 nhold_full=_sum_attr("nhold_full"), starhold_full=_sum_attr("starhold_full"),
                 rebal=base["rebal"], trades=trades,
                 sim_start=min(s["sim_start"] for s in sims), ev_end=base["ev_end"],
                 sig_pos=base["sig_pos"], exec_map=base["exec_map"],
                 n_trigger=sum(s["n_trigger"] for s in sims),
                 n_deferred=sum(s["n_deferred"] for s in sims),
                 n_limit_down=sum(s["n_limit_down"] for s in sims),
                 anchor_first_date=base.get("anchor_first_date", ""),
                 is_sleeve=True, sleeve_offsets=list(offsets), n_sleeves=len(offsets),
                 sleeve_sims=sims)
    sl = slice(synth["sim_start"], synth["ev_end"] + 1)
    synth["equity"] = pd.Series(comp[sl], index=bundle().dates[sl])
    return synth


def ensemble_legs(cfg: dict):
    return (cfg.get("portfolio") or {}).get("ensemble")


def _leg_cfg(cfg: dict, leg: dict, weight: float) -> dict:
    """把 ensemble 的一个 leg 展开成独立配置；capital = 总资本 × weight（避免 sleeve 老 bug）。"""
    n = int(leg.get("n", 6))
    sel = dict(type=str(leg.get("selector")), n=n, n_eff=n,
               size_range=tuple(leg.get("size_range") or (0.05, 0.30)),
               min_adv=float(leg.get("min_adv", 5e6)),
               exclude_star=bool(leg.get("exclude_star", True)),
               exclude_bj=True, exclude_chinext=bool(leg.get("exclude_chinext", True)),
               price_min=None, price_max=None, exclude_codes=[], max_weight=None,
               rank_fill=True, params=dict(leg.get("params") or {}))
    ex = dict(trailing_stop=None, fixed_stop=None, take_profit=leg.get("tp"),
              trailing_take=None, max_hold_days=None, stop_exec="next", staged_take=None)
    cost = dict(cfg["cost"])
    cost["capital"] = float(cfg["cost"]["capital"]) * weight
    out = dict(cfg)
    out.update(selector=sel, exit=ex, cost=cost,
               rebalance_days=int(leg.get("R", cfg["rebalance_days"])),
               phase=cfg["phase"] + int(leg.get("phase", 0)))
    out["portfolio"] = {**cfg["portfolio"], "ensemble": None, "sleeves": None}
    return out


def _simulate_ensemble(cfg: dict, legs: list) -> dict:
    """多 leg 合成：等权/加权 NAV 合成，每 leg 的 capital = 总资本 × weight。"""
    b = bundle()
    nD = b.n_dates
    def _w(item):
        return float(item.get("weight", (item.get("leg") or {}).get("weight", 1.0)))
    total_w = sum(_w(x) for x in legs)
    navs, weights, trades, sims = [], [], [], []
    anchor = None
    for item in legs:
        w = _w(item)
        leg = item["leg"] or {}
        stype = str(leg.get("selector") or "")
        if stype in ("bond_511880", "cash", "bond", "511880"):
            nav = np.cumprod(1.0 + b.bond_ret())
            navs.append(nav); weights.append(w)
            continue
        c = _leg_cfg(cfg, leg, w)
        sim = simulate(c)
        e = sim["eq_full"].copy()
        e[~np.isfinite(e)] = 1.0
        navs.append(e); weights.append(w)
        sims.append(sim)
        trades.append(sim["trades"].assign(leg=stype + f"_R{c['rebalance_days']}"))
        if anchor is None:
            anchor = sim
    comp = np.zeros(nD)
    for nv, w in zip(navs, weights):
        comp += nv * w
    comp /= total_w
    if anchor is None:
        raise ValueError("ensemble 至少需要一个股票 leg")
    tr = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame()
    synth = dict(cfg=cfg, equity=None, eq_full=comp,
                 cost_full=np.zeros(nD), expo_full=np.ones(nD) * float(cfg["portfolio"]["exposure"]),
                 nhold_full=np.sum([np.where(np.isfinite(s["nhold_full"]), s["nhold_full"], 0.0)
                                    for s in sims], axis=0) if sims else np.zeros(nD),
                 starhold_full=np.zeros(nD), rebal=anchor["rebal"], trades=tr,
                 sim_start=min(s["sim_start"] for s in sims), ev_end=anchor["ev_end"],
                 sig_pos=anchor["sig_pos"], exec_map=anchor["exec_map"],
                 n_trigger=sum(s["n_trigger"] for s in sims), n_deferred=0, n_limit_down=0,
                 n_staged=sum(s.get("n_staged", 0) for s in sims), anchor_first_date="",
                 is_ensemble=True, n_legs=len(legs), ensemble_weights=weights)
    sl = slice(synth["sim_start"], synth["ev_end"] + 1)
    synth["equity"] = pd.Series(comp[sl], index=b.dates[sl])
    return synth


def run_sim(cfg: dict) -> dict:
    ens = ensemble_legs(cfg)
    if ens:
        return _simulate_ensemble(cfg, ens)
    offs = sleeve_offsets(cfg)
    return _simulate_sleeves(cfg, offs) if offs else simulate(cfg)


# ===========================================================================
# 6. 指标
# ===========================================================================
def _r(v):
    if v is None:
        return None
    try:
        f = float(v)
    except Exception:
        return v
    if math.isnan(f):
        return None
    if math.isinf(f):
        return 999.0 if f > 0 else -999.0
    return round(f, 6)


def _window_metrics(sim: dict, start: str, end: str, base_date: str | None, cfg: dict) -> dict:
    b = bundle()
    eq_full = sim["eq_full"]
    sim_start = sim["sim_start"]
    ds, de = pd.Timestamp(start), pd.Timestamp(end)
    s_pos = max(int(np.searchsorted(b.dates, ds, "left")), sim_start)
    e_pos = min(int(np.searchsorted(b.dates, de, "right") - 1), sim["ev_end"])
    if e_pos <= s_pos:
        return {"n_days": 0}

    if base_date is not None:
        bpos = min(int(np.searchsorted(b.dates, pd.Timestamp(base_date), "right") - 1), e_pos - 1)
        base_val = float(eq_full[bpos]) if bpos >= 0 and np.isfinite(eq_full[bpos]) else 1.0
        base_pos = bpos if np.isfinite(eq_full[max(bpos, 0)]) else s_pos - 1
    else:
        base_val = float(eq_full[s_pos - 1]) if s_pos - 1 >= sim_start else 1.0
        base_pos = s_pos - 1

    curve = np.concatenate([[base_val], eq_full[s_pos:e_pos + 1]])
    rets = curve[1:] / curve[:-1] - 1.0
    total = curve[-1] / base_val - 1.0
    n_days = e_pos - s_pos + 1
    ann = (1.0 + total) ** (252.0 / n_days) - 1.0 if total > -1 else -1.0
    peak = np.maximum.accumulate(curve)
    mdd = float(np.min(curve / peak - 1.0))
    vol = float(np.std(rets, ddof=1) * math.sqrt(252)) if len(rets) > 1 else 0.0
    sharpe = float(np.mean(rets) * 252 / vol) if vol > 1e-12 else 0.0
    calmar = float(ann / abs(mdd)) if mdd < -1e-12 else None

    # ---- 调仓段（§10.1 完整段定义） ----
    R = cfg["rebalance_days"]
    rb_pos = [r["pos"] for r in sim["rebal"] if s_pos <= r["pos"] <= e_pos]
    periods = []
    for a, c in zip(rb_pos[:-1], rb_pos[1:]):
        if (c - a) == R and a >= s_pos and c <= e_pos:
            periods.append(float(eq_full[c] / eq_full[a] - 1.0))
    n_p = len(periods)
    win_period = float(np.mean([x > 0 for x in periods])) if n_p else float("nan")
    # 参考口径：贴窗口边界的段（段长 ≥ 0.8R）也算
    min_len = 0.8 * R
    bounds = [p for p in sorted(set(([base_pos] if base_pos >= s_pos - 1 else []) + rb_pos + [e_pos]))
              if p >= s_pos - 1 and np.isfinite(eq_full[max(p, 0)])]
    loose = []
    for a, c in zip(bounds[:-1], bounds[1:]):
        if c > a and (c - a) >= min_len and np.isfinite(eq_full[a]) and np.isfinite(eq_full[c]):
            loose.append(float(eq_full[c] / eq_full[a] - 1.0))
    n_pl = len(loose)
    win_period_loose = float(np.mean([x > 0 for x in loose])) if n_pl else float("nan")
    last_partial = float(eq_full[e_pos] / eq_full[rb_pos[-1]] - 1.0) if rb_pos else float("nan")

    # ---- 逐笔 ----
    n_tr = 0
    wt = avg_win = avg_loss = pf = max_name = top3 = float("nan")
    tr = sim["trades"]
    if len(tr):
        t = tr[(tr["exit_pos"] >= s_pos) & (tr["exit_pos"] <= e_pos)]
        n_tr = int(len(t))
        if n_tr:
            wt = float((t["ret"] > 0).mean())
            w, l = t["ret"][t["ret"] > 0], t["ret"][t["ret"] < 0]
            avg_win = float(w.mean()) if len(w) else 0.0
            avg_loss = float(l.mean()) if len(l) else 0.0
            pos_sum = float(t["pnl"][t["pnl"] > 0].sum())
            neg_sum = float(-t["pnl"][t["pnl"] < 0].sum())
            pf = float(pos_sum / neg_sum) if neg_sum > 1e-12 else float("inf")
            by = t.groupby("code")["pnl"].sum()
            tot = float(by.sum())
            if tot > 1e-9:
                max_name = float(by.max() / tot)
                top3 = float(by.nlargest(3).sum() / tot)

    # ---- 月度（只计完整自然月） ----
    months = {}
    prev_base = base_val
    for (y, m), g in pd.Series(eq_full[s_pos:e_pos + 1],
                               index=b.dates[s_pos:e_pos + 1]).groupby(lambda d: (d.year, d.month)):
        if len(g) < 5:
            continue
        months[f"{y}-{m:02d}"] = float(g.iloc[-1] / prev_base - 1.0)
        prev_base = float(g.iloc[-1])
    win_month = float(np.mean([x > 0 for x in months.values()])) if months else float("nan")

    # ---- 30 交易日块胜率（含最后一个 >=10 日的 partial 块） ----
    blocks, i = [], 0
    while i < n_days:
        j = min(i + 30, n_days)
        if j - i >= 10:
            blocks.append(float(curve[j] / curve[i] - 1.0))
        i = j
    block30 = float(np.mean([x > 0 for x in blocks])) if blocks else float("nan")

    # ---- 成本 / 换手 / 敞口 ----
    c0 = sim["cost_full"][base_pos] if base_pos >= 0 else 0.0
    cost_pct = float((sim["cost_full"][e_pos] - c0) / base_val * 100.0)
    rbs = [r["one_way"] for r in sim["rebal"] if s_pos <= r["pos"] <= e_pos]
    turnover = float(np.mean(rbs)) if rbs else float("nan")
    turnover_ann = float(sum(rbs) * 2.0 * 252.0 / n_days) if rbs else float("nan")
    expo = float(np.nanmean(sim["expo_full"][s_pos:e_pos + 1]))

    n_hold_avg = float(np.nanmean(sim["nhold_full"][s_pos:e_pos + 1]))
    n_hold_max = float(np.nanmax(sim["nhold_full"][s_pos:e_pos + 1]))
    n_distinct = 0
    if len(tr):
        tt = tr[(tr["exit_pos"] >= s_pos) & (tr["entry_pos"] <= e_pos)]
        n_distinct = int(tt["code"].nunique())
    n_hold_star = float(np.nanmean(sim["starhold_full"][s_pos:e_pos + 1]))
    n_stop = int(sim.get("n_trigger", 0))
    n_staged = int(sim.get("n_staged", 0))
    n_defer = int(sim.get("n_deferred", 0))
    n_ld = int(sim.get("n_limit_down", 0))
    # ---- 权重/分批止盈/波动目标 统计 ----
    wmax = sim.get("wmax_full")
    max_w = float(np.nanmax(wmax[s_pos:e_pos + 1])) if wmax is not None else float("nan")
    expo_win = sim["expo_full"][s_pos:e_pos + 1]
    min_expo = float(np.nanmin(expo_win)) if len(expo_win) else float("nan")
    below90 = float(np.nanmean(expo_win < 0.90)) if len(expo_win) else float("nan")
    rb_win = [r for r in sim["rebal"] if s_pos <= r["pos"] <= e_pos]
    n_picks_avg = float(np.mean([r.get("n_picks", 0) for r in rb_win])) if rb_win else float("nan")
    n_fill = float(np.mean([max(0, r.get("n_picks", 0) - r.get("n_base", r.get("n_picks", 0)))
                            for r in rb_win])) if rb_win else float("nan")
    w_over = float(np.mean([r.get("n_picks", 0) * (r.get("mw") or 1.0) < 0.999
                            for r in rb_win])) if rb_win else float("nan")
    staged_pnl = float(t["pnl"][t["reason"] == "staged_take"].sum()) if n_tr else 0.0
    _cap = float(cfg["cost"].get("capital", 1.0)) if cfg["cost"]["mode"] == "realistic" else 1.0
    return dict(n_days=n_days, total=float(total), ann=float(ann), mdd=mdd, vol=vol,
                n_picks_avg=n_picks_avg, n_fill_names=n_fill, weight_overflow_pct=w_over,
                max_realized_weight=max_w, min_exposure=min_expo, pct_days_below_90pct=below90,
                staged_pnl_pct=float(staged_pnl / (base_val * _cap) * 100.0),
                sharpe=sharpe, calmar=calmar, win_period=win_period, n_periods=n_p,
                n_hold_avg=n_hold_avg, n_hold_max=n_hold_max, n_distinct_names=n_distinct,
                n_hold_star=n_hold_star,
                n_stop_events=n_stop, n_staged_events=n_staged,
                stop_deferred_pct=(n_defer / n_stop if n_stop else 0.0),
                stop_limit_down_pct=(n_ld / n_stop if n_stop else 0.0),
                periods=periods, win_period_loose=win_period_loose, n_periods_loose=n_pl,
                last_partial_ret=last_partial,
                win_trade=wt, n_trades=n_tr, win_month=win_month, n_months=len(months),
                months=months,
                avg_win=avg_win, avg_loss=avg_loss, profit_factor=pf,
                turnover=turnover, turnover_ann=turnover_ann, cost_paid_pct=cost_pct,
                block30_win=block30, n_blocks=len(blocks), block30=blocks,
                exposure=expo, max_single_name_pnl_share=max_name, top3_pnl_share=top3,
                base_equity=base_val)


def _extract(sim: dict, cfg: dict, name: str) -> dict:
    if name == "2026":
        return _window_metrics(sim, cfg["window"]["eval_start"], cfg["window"]["eval_end"],
                               "2025-12-31", cfg)
    s, e, bd = WINDOWS[name]
    return _window_metrics(sim, s, e, bd, cfg)


def _exit_label(ex: dict) -> str:
    parts = []
    for k, tag in (("trailing_stop", "ts"), ("fixed_stop", "fs"),
                   ("take_profit", "tp"), ("trailing_take", "tt"), ("max_hold_days", "mh")):
        if ex[k] is not None:
            parts.append(f"{tag}{ex[k]:g}")
    return "+".join(parts) if parts else "none"


CORE_KEYS = ("total", "ann", "mdd", "win_period", "n_periods", "win_period_loose",
             "block30_win", "n_blocks",
             "n_hold_avg", "n_hold_max", "n_distinct_names", "n_hold_star",
             "n_picks_avg", "n_fill_names", "weight_overflow_pct", "max_realized_weight",
             "min_exposure", "pct_days_below_90pct", "staged_pnl_pct",
             "n_stop_events", "n_staged_events", "stop_deferred_pct",
             "stop_limit_down_pct",
             "n_periods_loose", "last_partial_ret", "win_trade", "n_trades", "win_month",
             "n_months", "vol", "sharpe", "calmar", "avg_win", "avg_loss",
             "profit_factor", "turnover", "turnover_ann", "cost_paid_pct", "exposure",
             "max_single_name_pnl_share", "top3_pnl_share", "n_days")


def run_spec(spec: dict, detail: bool = False, variants: tuple = ("next", "same", "real", "fresh")):
    """跑一个 spec。

    variants:
      next  -> 主口径（0.5%/边，t+1 收盘执行止损）→ 无后缀列
      same  -> 乐观敏感性（当日收盘成交）→ `_same` 后缀
      real  -> 现实费率+整手（主口径执行时点）→ `_real` 后缀
      fresh -> 2026-01-05 空仓起步 → `fresh_2026`
    """
    t0 = time.time()
    cfg = normalize_spec(spec)
    sim = run_sim(cfg)
    m26 = _extract(sim, cfg, "2026")
    row = {
        "id": cfg["id"], "selector": cfg["selector"]["type"], "n": cfg["selector"]["n"],
        "R": cfg["rebalance_days"],
        "size_range": ("%.0f-%.0f%%" % (cfg["selector"]["size_range"][0] * 100,
                                        cfg["selector"]["size_range"][1] * 100))
        if cfg["selector"]["size_range"] else "all",
        "exit": _exit_label(cfg["exit"]), "stop_exec": cfg["exit"]["stop_exec"],
        "timing": cfg["timing"]["type"], "out_asset": cfg["timing"]["out_asset"],
        "phase": cfg["phase"], "anchor": cfg["rebalance_anchor"],
        "dd_action": cfg["timing"]["dd_action"] if cfg["timing"]["type"] == "dd_breaker" else "",
        "dd_trigger": cfg["timing"]["dd_trigger"] if cfg["timing"]["type"] == "dd_breaker" else None,
        "cost_mode": cfg["cost"]["mode"], "one_way": cfg["cost"]["one_way"],
        "exposure_target": cfg.get("portfolio", {}).get("exposure", 1.0),
        "max_weight": cfg["selector"].get("max_weight"),
        "staged_take": (",".join(f"{g:g}:{f:g}" for g, f in cfg["exit"]["staged_take"])
                        if cfg["exit"].get("staged_take") else ""),
        "vol_target": cfg.get("portfolio", {}).get("vol_target"),
        "n_sleeves": int(sim.get("n_sleeves", 1)),
        "sleeve_offsets": ",".join(str(x) for x in sim.get("sleeve_offsets", [])),
        "lot_size": cfg["cost"]["lot_size"], "capital": cfg["cost"]["capital"],
    }
    for k in CORE_KEYS:
        row[k] = _r(m26.get(k))
    row["periods_2026"] = "|".join(f"{x:.4f}" for x in m26.get("periods", []))
    row["monthly_2026"] = "|".join(f"{k}:{v:.4f}" for k, v in m26.get("months", {}).items())
    # 主口径 = next 结束（如果 spec 指定 same，主指标仍是 same 那份）
    if cfg["exit"]["stop_exec"] == "same":
        row["stop_exec"] = "same"

    # ---- 敏感性 / 副口径 ----
    if "same" in variants:
        m = _extract(run_sim(with_overrides(cfg, exit={"stop_exec": "same"})), cfg, "2026")
        for k, suf in (("total", "same"), ("ann", "same"), ("mdd", "same"),
                       ("win_period", "same"), ("win_trade", "same"), ("win_month", "same"),
                       ("n_periods", "same")):
            row[f"{k}_{suf}"] = _r(m.get(k))
    if "real" in variants:
        cfg_r = with_overrides(cfg, cost={"mode": "realistic", "lot_size": cfg["cost"]["lot_size"]
                                          if cfg["cost"]["lot_size"] > 1 else 100})
        m = _extract(run_sim(cfg_r), cfg, "2026")
        for k in ("total", "ann", "mdd", "win_period", "win_trade", "win_month"):
            row[f"{k}_real"] = _r(m.get(k))
    if "fresh" in variants:
        # fresh 口径：2026-01-05 空仓起步（基数 1.0），首个调仓日建仓；同成本/整手/执行纪律
        cfg_f = with_overrides(cfg, window={"warmup_start": cfg["window"]["eval_start"]})
        mf = _extract(run_sim(cfg_f), cfg_f, "2026")
        for k, name in (("total", "fresh_total"), ("mdd", "fresh_mdd"),
                        ("win_period", "fresh_win_period"), ("win_month", "fresh_win_month"),
                        ("win_trade", "fresh_win_trade"), ("n_trades", "fresh_n_trades"),
                        ("calmar", "fresh_calmar_ann"), ("top3_pnl_share", "fresh_top3_pnl_share"),
                        ("max_single_name_pnl_share", "fresh_top1_pnl_share"),
                        ("exposure", "fresh_exposure"), ("ann", "fresh_ann"),
                        ("n_periods", "fresh_n_periods"), ("n_months", "fresh_n_months"),
                        ("win_period_loose", "fresh_win_period_loose"),
                        ("block30_win", "fresh_block30_win"), ("n_hold_avg", "fresh_n_hold_avg"),
                        ("n_picks_avg", "fresh_n_picks_avg"), ("n_distinct_names", "fresh_n_distinct"), ("vol", "fresh_vol"),
                        ("sharpe", "fresh_sharpe"), ("cost_paid_pct", "fresh_cost_paid_pct"),
                        ("last_partial_ret", "fresh_last_partial_ret")):
            row[name] = _r(mf.get(k))
        row["fresh_calmar"] = row["fresh_calmar_ann"]          # 兼容旧列名（= ann/|mdd|）
        _t, _m = mf.get("total"), mf.get("mdd")
        row["fresh_calmar_total_over_mdd"] = _r(float(_t) / abs(float(_m))) if _t is not None and _m not in (None, 0) else None
        row["fresh_calmar_raw"] = row["fresh_calmar_total_over_mdd"]   # 兼容别名
        row["fresh_monthly"] = "|".join(f"{k}:{v:.4f}" for k, v in mf.get("months", {}).items())
        row["fresh_periods"] = "|".join(f"{x:.4f}" for x in mf.get("periods", []))
        row["fresh_2026"] = row["fresh_total"]                       # 兼容旧列名
        row["fresh_2026_win_period"] = row["fresh_win_period"]
        row["fresh_2026_mdd"] = row["fresh_mdd"]

    # ---- 稳健性窗口（主口径） ----
    for w in ("2025", "2025h2", "2024"):
        mw = _extract(sim, cfg, w)
        for k in ("total", "ann", "mdd", "win_period", "n_periods", "win_trade",
                  "n_trades", "win_month", "last_partial_ret"):
            row[f"{k}_{w}"] = _r(mw.get(k))

    row["anchor_first_date"] = sim.get("anchor_first_date", "")
    row["total_same_close"] = row.get("total_same")
    row["equity_end"] = _r(float(sim["equity"].iloc[-1]))
    row["sig_days"] = len(sim["sig_pos"])
    row["secs"] = round(time.time() - t0, 3)
    row["status"] = "ok"
    row["error"] = ""
    if detail:
        eq_df = pd.DataFrame({"date": sim["equity"].index, "equity": sim["equity"].to_numpy()})
        tr = sim["trades"].copy()
        if len(tr):
            tr = tr[["code", "entry_date", "exit_date", "shares", "entry_px", "exit_px",
                     "notional", "cost", "pnl", "ret", "reason"]]
        return row, eq_df, tr
    return row


# ===========================================================================
# 7. 基准（等权小微盘，§10.3）
# ===========================================================================
def benchmark(start="2026-01-05", end="2026-11-04", base_date="2025-12-31") -> dict:
    """等权小微盘基准：seasoned + adv20>5e6 + 市值 5~30% 分位，逐日等权、无成本、t-1 选池。"""
    b = bundle()
    um = universe_matrix(b, dict(size_range=(0.05, 0.30), min_adv=5e6, exclude_star=False,
                                 exclude_bj=True, exclude_chinext=False,
                                 price_min=None, price_max=None))
    ret = np.full((b.n_dates, b.n_codes), np.nan, dtype=np.float32)
    c = b.close_ff_np
    with np.errstate(invalid="ignore", divide="ignore"):
        ret[1:] = np.where(um[:-1], c[1:] / c[:-1] - 1.0, np.nan)
    daily = np.nanmean(np.where(np.isfinite(ret), ret, np.nan), axis=1)
    r = pd.Series(np.nan_to_num(daily, nan=0.0), index=b.dates)
    ds, de = pd.Timestamp(start), pd.Timestamp(end)
    seg = r.loc[ds:de]
    eq = (1 + seg).cumprod()
    tot = float(eq.iloc[-1] - 1)
    mdd = float((eq / eq.cummax() - 1).min())
    months = {}
    for (y, m), g in seg.groupby(lambda d: (d.year, d.month)):
        if len(g) >= 5:
            months[f"{y}-{m:02d}"] = float((1 + g).prod() - 1)
    # 同款调仓段（R=30 相位的边界，供 summary 分段对比）
    return dict(total=tot, mdd=mdd, n_days=int(len(seg)), months=months,
                daily=seg, equity=(1 + seg).cumprod())


# ===========================================================================
# 8. CLI
# ===========================================================================
def harness_md5() -> str:
    return hashlib.md5(Path(__file__).read_bytes()).hexdigest()


def spec_hash(spec: dict) -> str:
    return hashlib.md5(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="team/harness.py 单 spec 回测")
    ap.add_argument("--file")
    ap.add_argument("--spec")
    ap.add_argument("--detail", action="store_true")
    ap.add_argument("--outdir", default=str(HERE / "runs"))
    a = ap.parse_args(argv)
    if a.spec:
        spec = json.loads(a.spec)
    elif a.file:
        spec = json.loads(Path(a.file).read_text())
    else:
        ap.error("需要 --spec 或 --file")
    specs = spec if isinstance(spec, list) else [spec]
    rows = []
    for sp in specs:
        row, eqd, tr = run_spec(sp, detail=True)
        rows.append(row)
        if a.detail:
            out = Path(a.outdir)
            (out / "equity").mkdir(parents=True, exist_ok=True)
            (out / "trades").mkdir(parents=True, exist_ok=True)
            eqd.to_csv(out / "equity" / f"{row['id']}.csv", index=False)
            tr.to_csv(out / "trades" / f"{row['id']}.csv", index=False)
    print(json.dumps(rows if len(rows) > 1 else rows[0], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _main()
