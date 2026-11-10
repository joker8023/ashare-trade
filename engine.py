"""
A股因子研究引擎
================
一次建好, 之后每轮研究只需指定因子名 + 方向。

用法:
    python engine.py --factor rev20 --direction low --n 100 --rebal 20
    python engine.py --factor rev20 --direction low --json     # 输出JSON给子agent用
    python engine.py --list                                    # 列出所有可用因子

因子评估两套指标:
  1. IC (信息系数): 因子值与未来收益的横截面秩相关 — 衡量因子的纯预测力,
     不受组合构建方式影响
  2. 组合回测: 按因子排序选股, 等权持有 rebal 天 — 衡量可实现的收益

防未来函数:
  - 因子只用 t 日及以前的数据
  - 组合在 t+1 日建仓, 持有到 t+1+rebal
  - IC 的远期收益用 t+1 → t+1+rebal 区间
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
OUT = BASE / "results"
OUT.mkdir(exist_ok=True)

COST_ONE_WAY = 0.0015
LEDGER = OUT / "factor_ledger.csv"

_PIV = None


def piv():
    """默认用 2020 起的 pivots_full; 设 ASHARE_PIVOTS=pivots_long.pkl 可切到 2010 起的长历史"""
    global _PIV
    if _PIV is None:
        name = os.getenv("ASHARE_PIVOTS", "pivots_full.pkl")
        p = DATA / name
        if not p.exists():
            raise SystemExit(f"缺少 data/{name}, 先跑对应的 rebuild 脚本")
        _PIV = pd.read_pickle(p)
    return _PIV


# ============================================================
# 因子库: 每个函数接收 piv dict, 返回 date × code 的因子值矩阵
# 约定: "方向=high" 表示因子值越大未来收益越高
# ============================================================

def _ret(c, n):
    return c / c.shift(n) - 1


# --- 反转类 ---
def f_rev5(p):
    return -_ret(p["close"], 5)


def f_rev20(p):
    return -_ret(p["close"], 20)


def f_rev60(p):
    return -_ret(p["close"], 60)


# --- 动量类 ---
def f_mom60(p):
    return _ret(p["close"], 60)


def f_mom120(p):
    return _ret(p["close"], 120)


def f_mom12_1(p):
    """经典12-1动量: 过去12个月剔除最近1个月"""
    c = p["close"]
    return c.shift(20) / c.shift(240) - 1


# --- 波动类 (低波溢价) ---
def f_vol20(p):
    return -p["close"].pct_change(fill_method=None).rolling(20).std()


def f_vol60(p):
    return -p["close"].pct_change(fill_method=None).rolling(60).std()


def f_max20(p):
    """MAX效应: 最大单日收益越大, 未来越差"""
    r = p["close"].pct_change(fill_method=None)
    return -r.rolling(20).max()


def f_skew20(p):
    """负偏度溢价"""
    r = p["close"].pct_change(fill_method=None)
    return -r.rolling(20).skew()


def f_idio_vol(p):
    """特质波动率(简化): 个股波动 / 市场波动"""
    r = p["close"].pct_change(fill_method=None)
    mkt = r.mean(axis=1)
    beta_cov = r.rolling(60).cov(mkt)
    mkt_var = mkt.rolling(60).var()
    resid = r.sub(beta_cov.div(mkt_var, axis=0).mul(mkt, axis=0))
    return -resid.rolling(60).std()


# --- 流动性 / 换手 ---
def f_turn20(p):
    """低换手溢价: 换手率 = 成交额 / 流通市值"""
    cap = p["close"] * p["shares"]
    turn = p["amount"] / cap.replace(0, np.nan)
    return -turn.rolling(20).mean()


def f_amihud(p):
    """Amihud非流动性: |收益|/成交额, 越大流动性越差"""
    r = p["close"].pct_change(fill_method=None).abs()
    amt = p["amount"].replace(0, np.nan)
    return (r / (amt / 1e8)).rolling(20).mean()


def f_amount_level(p):
    """成交额水平 (越小=小盘+冷门)"""
    return -p["amount"].rolling(20).mean()


# --- 量价 ---
def f_bias20(p):
    """乖离率: 价格偏离20日均线, 负乖离=超跌"""
    c = p["close"]
    return -(c / c.rolling(20).mean() - 1)


def f_volratio(p):
    """量比: 近期成交量/长期均量, 放量通常短期见顶"""
    v = p["volume"]
    return -(v.rolling(5).mean() / v.rolling(60).mean())


def f_pv_corr(p):
    """量价相关性: 价涨量增为正相关"""
    c = p["close"].pct_change(fill_method=None)
    v = p["volume"].pct_change(fill_method=None)
    return -c.rolling(20).corr(v)


def f_amplitude(p):
    """振幅: (最高-最低)/收盘, 低振幅溢价"""
    a = (p["high"] - p["low"]) / p["close"]
    return -a.rolling(20).mean()


def f_gap(p):
    """隔夜跳空均值"""
    gap = p["open"] / p["close"].shift(1) - 1
    return -gap.rolling(20).mean()


def f_overnight(p):
    """累计隔夜收益 vs 日内收益"""
    on = (p["open"] / p["close"].shift(1)).apply(np.log1p)
    return -on.rolling(20).sum()


# --- 位置 / 技术 ---
def f_high52(p):
    """距52周高点: 越接近高点越强 (动量) 还是越弱(反转)? 先按动量"""
    c = p["close"]
    return c / c.rolling(250, min_periods=120).max() - 1


def f_rsi14(p):
    c = p["close"]
    d = c.diff()
    up = d.clip(lower=0).rolling(14).mean()
    dn = (-d.clip(upper=0)).rolling(14).mean()
    rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    return -(rsi - 50) / 50


def f_size(p):
    """市值因子: 小市值"""
    return -(p["close"] * p["shares"])


# --- 组合因子 ---
def f_size_rev(p):
    """小市值 + 反转 (等权秩和)"""
    s = -(p["close"] * p["shares"])
    r = -_ret(p["close"], 20)
    return s.rank(axis=1, pct=True) + r.rank(axis=1, pct=True)


def f_rev_lowvol(p):
    """反转 + 低波"""
    r = -_ret(p["close"], 20)
    v = -p["close"].pct_change(fill_method=None).rolling(20).std()
    return r.rank(axis=1, pct=True) + v.rank(axis=1, pct=True)




# --- 正交化工具 ---
def _row_resid(y, x):
    """横截面逐行 OLS 残差: 从 y 中剔除 x 的线性影响"""
    xm = x.sub(x.mean(axis=1), axis=0)
    ym = y.sub(y.mean(axis=1), axis=0)
    denom = (xm * xm).sum(axis=1).replace(0, np.nan)
    beta = (xm * ym).sum(axis=1) / denom
    return ym.sub(xm.mul(beta, axis=0), axis=0)


def _rk(df):
    return df.rank(axis=1, pct=True)


# --- 复合因子 (跨因子家族组合) ---
def f_liq_rev(p):
    """流动性 + 反转"""
    return _rk(p["amount"].rolling(20).mean().mul(-1)) + _rk(-_ret(p["close"], 20))


def f_liq_lowvol(p):
    """流动性 + 低波"""
    return _rk(p["amount"].rolling(20).mean().mul(-1)) + _rk(-p["close"].pct_change(fill_method=None).rolling(20).std())


def f_liq_size(p):
    """流动性 + 小市值"""
    return _rk(p["amount"].rolling(20).mean().mul(-1)) + _rk(-(p["close"] * p["shares"]))


def f_triple(p):
    """流动性 + 反转 + 低波"""
    return (_rk(p["amount"].rolling(20).mean().mul(-1))
            + _rk(-_ret(p["close"], 60))
            + _rk(-p["close"].pct_change(fill_method=None).rolling(20).std()))


def f_quad(p):
    """四因子: 流动性 + 反转 + 低波 + 低换手"""
    cap = p["close"] * p["shares"]
    turn = p["amount"] / cap.replace(0, np.nan)
    return (_rk(p["amount"].rolling(20).mean().mul(-1))
            + _rk(-_ret(p["close"], 20))
            + _rk(-p["close"].pct_change(fill_method=None).rolling(20).std())
            + _rk(-turn.rolling(20).mean()))


# --- 正交化因子 ---
def f_amihud_orth(p):
    """Amihud 剔除市值影响后的残差 — 检验是否只是小市值代理"""
    r = p["close"].pct_change(fill_method=None).abs()
    amt = p["amount"].replace(0, np.nan)
    raw = (r / (amt / 1e8)).rolling(20).mean()
    cap = (p["close"] * p["shares"])
    return _row_resid(_rk(raw), _rk(cap))


def f_rev20_orth(p):
    """反转剔除市值影响"""
    cap = (p["close"] * p["shares"])
    return _row_resid(_rk(-_ret(p["close"], 20)), _rk(cap))


def f_turn_orth(p):
    """低换手剔除市值影响"""
    cap = p["close"] * p["shares"]
    turn = p["amount"] / cap.replace(0, np.nan)
    return _row_resid(_rk(-turn.rolling(20).mean()), _rk(cap))




# ============================================================
# 第4轮新增因子 (价格/成交量衍生)
# ============================================================

def f_downvol20(p):
    """下行波动率: 只算负收益的标准差"""
    r = p["close"].pct_change(fill_method=None)
    neg = r.where(r < 0)
    return -neg.rolling(20, min_periods=3).std()


def f_kurt20(p):
    """收益率峰度: 肥尾惩罚"""
    return -p["close"].pct_change(fill_method=None).rolling(20).kurt()


def f_dd48w(p):
    """距48周最大回撤: 当前价距一年内高点的跌幅"""
    c = p["close"]
    peak = c.rolling(250, min_periods=120).max()
    return -(c / peak - 1)


def f_low52(p):
    """距52周低点涨幅: 越低越冷门"""
    c = p["close"]
    trough = c.rolling(250, min_periods=120).min()
    return -(c / trough - 1)


def f_maxdd20(p):
    """近20日内部最大回撤"""
    c = p["close"]
    roll_max = c.rolling(20).max()
    return -(c / roll_max - 1)


def f_beta60(p):
    """Beta: 低beta溢价"""
    r = p["close"].pct_change(fill_method=None)
    mkt = r.mean(axis=1)
    cov = r.rolling(60).cov(mkt)
    var = mkt.rolling(60).var()
    return -cov.div(var, axis=0)


def f_turn_chg(p):
    """换手率变化: 近期换手相对长期变化"""
    cap = p["close"] * p["shares"]
    turn = p["amount"] / cap.replace(0, np.nan)
    return -(turn.rolling(5).mean() / turn.rolling(60).mean())


def f_turn_std(p):
    """换手率波动: 换手越不稳定越差"""
    cap = p["close"] * p["shares"]
    turn = p["amount"] / cap.replace(0, np.nan)
    return -turn.rolling(20).std()


def f_lag_rev(p):
    """滞后反转: 剔除最近5日的20日反转 (避开短期噪音)"""
    c = p["close"]
    return -(c.shift(5) / c.shift(25) - 1)


def f_volvol(p):
    """波动率的波动率"""
    r = p["close"].pct_change(fill_method=None)
    return -r.rolling(20).std().rolling(20).std()


def f_pv_div(p):
    """价量背离: 价格上涨但成交量下降 = 危险"""
    c = p["close"]
    r20 = c / c.shift(20) - 1
    v = p["volume"]
    vr = v.rolling(5).mean() / v.rolling(60).mean()
    return -(r20.rank(axis=1, pct=True) * vr.rank(axis=1, pct=True))


def f_streak(p):
    """连续涨跌: 连涨越多越该反转"""
    r = p["close"].pct_change(fill_method=None)
    up = (r > 0).astype(float)
    dn = (r < 0).astype(float)
    return -(up.rolling(5).sum() - dn.rolling(5).sum())


def f_intraday(p):
    """日内收益累计 (对比隔夜)"""
    intr = (p["close"] / p["open"]).apply(np.log1p)
    return -intr.rolling(20).sum()


def f_amihud_5(p):
    """短窗口 Amihud (5日) — 对比20日版本"""
    r = p["close"].pct_change(fill_method=None).abs()
    amt = p["amount"].replace(0, np.nan)
    return (r / (amt / 1e8)).rolling(5).mean()


def f_amihud_60(p):
    """长窗口 Amihud (60日)"""
    r = p["close"].pct_change(fill_method=None).abs()
    amt = p["amount"].replace(0, np.nan)
    return (r / (amt / 1e8)).rolling(60).mean()


def f_amihud_smooth(p):
    """Amihud + 低换手 双确认 (同族但不同构造, 检验稳健性)"""
    r = p["close"].pct_change(fill_method=None).abs()
    amt = p["amount"].replace(0, np.nan)
    a = (r / (amt / 1e8)).rolling(20).mean()
    cap = p["close"] * p["shares"]
    turn = (p["amount"] / cap.replace(0, np.nan)).rolling(20).mean()
    return _rk(a) * 0.7 + _rk(-turn) * 0.3




def f_amihud_turnstd(p):
    """Amihud + 换手率波动 双因子 (两个独立流动性维度)"""
    r = p["close"].pct_change(fill_method=None).abs()
    amt = p["amount"].replace(0, np.nan)
    a = (r / (amt / 1e8)).rolling(20).mean()
    cap = p["close"] * p["shares"]
    turn = p["amount"] / cap.replace(0, np.nan)
    ts = turn.rolling(20).std()
    return _rk(a) + _rk(-ts)


def f_amihud60_turnstd(p):
    """Amihud60 + 换手率波动"""
    r = p["close"].pct_change(fill_method=None).abs()
    amt = p["amount"].replace(0, np.nan)
    a = (r / (amt / 1e8)).rolling(60).mean()
    cap = p["close"] * p["shares"]
    turn = p["amount"] / cap.replace(0, np.nan)
    ts = turn.rolling(20).std()
    return _rk(a) + _rk(-ts)


def f_amihud_icw(p):
    """Amihud + 反转 按经验IC加权 (0.7/0.3)"""
    r = p["close"].pct_change(fill_method=None).abs()
    amt = p["amount"].replace(0, np.nan)
    a = (r / (amt / 1e8)).rolling(20).mean()
    rev = -(p["close"] / p["close"].shift(20) - 1)
    return _rk(a) * 0.7 + _rk(rev) * 0.3




_IND = None


def industry_map():
    """股票 → 行业分组 映射 (来自东财行业板块)"""
    global _IND
    if _IND is None:
        f = DATA / "industry_map.pkl"
        if f.exists():
            m = pd.read_pickle(f)
            _IND = m.set_index("code")["industry_group"]
        else:
            _IND = pd.Series(dtype=object)
    return _IND


def f_amihud_neutral(p):
    """行业中性化 Amihud: 在每个行业内部排名, 消除行业偏好"""
    r = p["close"].pct_change(fill_method=None).abs()
    amt = p["amount"].replace(0, np.nan)
    a = (r / (amt / 1e8)).rolling(20).mean()
    ind = industry_map()
    if len(ind) == 0:
        return a
    groups = ind.reindex(a.columns)
    out = pd.DataFrame(np.nan, index=a.index, columns=a.columns)
    for g, cols in groups.groupby(groups).groups.items():
        cc = list(cols)
        out[cc] = a[cc].rank(axis=1, pct=True)
    return out


def f_amihud60_neutral(p):
    """60日窗口的行业中性 Amihud"""
    r = p["close"].pct_change(fill_method=None).abs()
    amt = p["amount"].replace(0, np.nan)
    a = (r / (amt / 1e8)).rolling(60).mean()
    ind = industry_map()
    if len(ind) == 0:
        return a
    groups = ind.reindex(a.columns)
    out = pd.DataFrame(np.nan, index=a.index, columns=a.columns)
    for g, cols in groups.groupby(groups).groups.items():
        cc = list(cols)
        out[cc] = a[cc].rank(axis=1, pct=True)
    return out


FACTORS = {k[2:]: v for k, v in list(globals().items()) if k.startswith("f_")}


# ============================================================
# 回测
# ============================================================

def _universe_mask(p, dates_t):
    c = p["close"]
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    seasoned = c.shift(250).notna()
    ok = seasoned.loc[dates_t] & (adv20.loc[dates_t] > 5e6) & c.loc[dates_t].notna()
    return ok


def evaluate(factor_name, direction="high", n_hold=100, rebal=20,
             size_range=None, start=None, end=None,
             cost=COST_ONE_WAY, min_adv=5e6):
    p = piv()
    c = p["close"]
    amount = p["amount"]
    adv20 = amount.rolling(20, min_periods=10).mean()
    seasoned = c.shift(250).notna()

    fac = FACTORS[factor_name](p)
    if not isinstance(fac, pd.DataFrame):
        raise ValueError("因子必须返回 DataFrame")

    dates = c.index
    # 组合期: t+1 建仓, 持有 rebal 天
    idxs = list(range(300, len(dates) - rebal - 2, rebal))

    # IC: 因子值 vs t+1..t+1+rebal 的远期收益
    fwd = c.shift(-(rebal + 1)) / c.shift(-1) - 1

    ic_list, ic_dates = [], []
    port_rets, prev, turn_list = [], set(), []

    for i in idxs:
        t = dates[i]
        t1 = dates[i + 1]
        t2 = dates[min(i + 1 + rebal, len(dates) - 1)]

        valid = seasoned.loc[t] & (adv20.loc[t] > min_adv) & c.loc[t].notna()
        f_t = fac.loc[t]
        valid &= f_t.notna()

        if size_range is not None:
            cap = (c.loc[t] * p["shares"])
            lo = cap.quantile(size_range[0]); hi = cap.quantile(size_range[1])
            valid &= ((cap >= lo) & (cap <= hi)).fillna(False)

        pool = valid[valid].index
        if len(pool) < 100:
            continue

        # ---- IC ----
        fv = f_t.loc[pool]
        fv_rank = fv.rank()
        fr = fwd.loc[t].reindex(pool)
        mask = fv_rank.notna() & fr.notna()
        if mask.sum() > 50:
            ic = fv_rank[mask].corr(fr[mask], method="pearson")
            if pd.notna(ic):
                ic_list.append(ic); ic_dates.append(t)

        # ---- 组合 ----
        asc = direction == "low"
        picks = list(fv.nsmallest(n_hold).index if asc else fv.nlargest(n_hold).index)
        seg = c.loc[t1:t2, picks].ffill()
        if len(seg) < 2:
            continue
        pr = seg.div(seg.iloc[0]).mean(axis=1).pct_change(fill_method=None).dropna()
        cur = set(picks)
        to = 1.0 if not prev else len(cur - prev) / max(len(cur), 1)
        turn_list.append(to)
        if len(pr):
            pr.iloc[0] -= to * 2 * cost
        prev = cur
        port_rets.append(pr)

    if not port_rets:
        return {"factor": factor_name, "error": "无有效持仓期"}

    r = pd.concat(port_rets).sort_index()
    r = r[~r.index.duplicated(keep="first")]
    if start:
        r = r[r.index >= pd.Timestamp(start)]
    if end:
        r = r[r.index <= pd.Timestamp(end)]

    eq = (1 + r).cumprod()
    yrs = len(eq) / 252
    ann = eq.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else 0
    vol = r.std() * np.sqrt(252)
    mdd = (eq / eq.cummax() - 1).min()
    active = r[r != 0]

    ic_s = pd.Series(ic_list, index=pd.to_datetime(ic_dates)).sort_index()
    # 关键: IC 必须和组合收益用同一个日期区间, 否则样本外检验无效
    if start:
        ic_s = ic_s[ic_s.index >= pd.Timestamp(start)]
    if end:
        ic_s = ic_s[ic_s.index <= pd.Timestamp(end)]
    ic_mean = ic_s.mean() if len(ic_s) else np.nan
    ic_std = ic_s.std() if len(ic_s) > 1 else np.nan
    icir = ic_mean / ic_std if ic_std and ic_std > 0 else np.nan
    ic_t = icir * np.sqrt(len(ic_s)) if pd.notna(icir) else np.nan

    yearly = r.groupby(r.index.year).apply(lambda x: (1 + x).prod() - 1)

    return {
        "factor": factor_name,
        "direction": direction,
        "n_hold": n_hold,
        "rebal": rebal,
        "size_range": list(size_range) if size_range else None,
        "cost": cost,
        "min_adv": min_adv,
        "period": f"{r.index[0].date()}~{r.index[-1].date()}",
        "days": int(len(r)),
        # IC 指标
        "IC": round(float(ic_mean), 4) if pd.notna(ic_mean) else None,
        "ICIR": round(float(icir), 3) if pd.notna(icir) else None,
        "IC_t": round(float(ic_t), 2) if pd.notna(ic_t) else None,
        "IC_pos_ratio": round(float((ic_s > 0).mean()), 3) if len(ic_s) else None,
        "IC_n": len(ic_s),
        # 组合指标
        "ann": round(float(ann), 4),
        "total": round(float(eq.iloc[-1] - 1), 4),
        "vol": round(float(vol), 4),
        "sharpe": round(float(r.mean() * 252 / vol), 3) if vol > 0 else None,
        "mdd": round(float(mdd), 4),
        "calmar": round(float(ann / abs(mdd)), 3) if mdd < 0 else None,
        "win_rate": round(float((active > 0).mean()), 4) if len(active) else None,
        "turnover": round(float(np.mean(turn_list)), 3) if turn_list else None,
        "yearly": {str(k): round(float(v), 4) for k, v in yearly.items()},
    }


def returns_series(factor_name, direction="high", n_hold=100, rebal=20,
                   size_range=None, cost=COST_ONE_WAY, min_adv=5e6):
    """返回策略的逐日收益序列 (供 walk-forward 使用)"""
    p = piv()
    c = p["close"]
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    seasoned = c.shift(250).notna()
    fac = FACTORS[factor_name](p)
    dates = c.index
    rets, prev = [], set()

    for i in range(300, len(dates) - rebal - 2, rebal):
        t, t1 = dates[i], dates[i + 1]
        t2 = dates[min(i + 1 + rebal, len(dates) - 1)]
        valid = seasoned.loc[t] & (adv20.loc[t] > min_adv) & c.loc[t].notna() & fac.loc[t].notna()
        if size_range is not None:
            cap = c.loc[t] * p["shares"]
            lo, hi = cap.quantile(size_range[0]), cap.quantile(size_range[1])
            valid &= ((cap >= lo) & (cap <= hi)).fillna(False)
        pool = valid[valid].index
        if len(pool) < n_hold:
            continue
        picks = list(fac.loc[t, pool].nsmallest(n_hold).index if direction == "low"
                     else fac.loc[t, pool].nlargest(n_hold).index)
        seg = c.loc[t1:t2, picks].ffill()
        if len(seg) < 2:
            continue
        pr = seg.div(seg.iloc[0]).mean(axis=1).pct_change(fill_method=None).dropna()
        cur = set(picks)
        to = 1.0 if not prev else len(cur - prev) / max(len(cur), 1)
        if len(pr):
            pr.iloc[0] -= to * 2 * cost
        prev = cur
        rets.append(pr)

    r = pd.concat(rets).sort_index()
    return r[~r.index.duplicated(keep="first")]


def append_ledger(res, note=""):
    row = {k: v for k, v in res.items() if k != "yearly"}
    row["yearly"] = json.dumps(res.get("yearly", {}), ensure_ascii=False)
    row["note"] = note
    row["ts"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    df = pd.DataFrame([row])
    if LEDGER.exists():
        df.to_csv(LEDGER, mode="a", header=False, index=False, encoding="utf-8")
    else:
        df.to_csv(LEDGER, index=False, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--factor")
    ap.add_argument("--direction", default="high", choices=["high", "low"])
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--rebal", type=int, default=20)
    ap.add_argument("--size", nargs=2, type=float, default=None,
                    help="市值分位区间, 如 --size 0.05 0.30")
    ap.add_argument("--cost", type=float, default=0.0015,
                    help="单边交易成本, 如 0.005 = 0.5%%")
    ap.add_argument("--min-adv", type=float, default=5e6,
                    help="日均成交额下限(元)")
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--no-ledger", action="store_true")
    a = ap.parse_args()

    if a.list:
        for k in sorted(FACTORS):
            print(k)
        return

    if not a.factor:
        ap.error("--factor 必填")
    if a.factor not in FACTORS:
        print(f"未知因子: {a.factor}\n可用: {', '.join(sorted(FACTORS))}")
        sys.exit(1)

    sr = tuple(a.size) if a.size else None
    res = evaluate(a.factor, a.direction, a.n, a.rebal, sr, a.start, a.end,
                   cost=a.cost, min_adv=a.min_adv)

    if not a.no_ledger and "error" not in res:
        append_ledger(res)

    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        if "error" in res:
            print(res)
            return
        print(f"因子 {res['factor']} (方向={res['direction']})  N={res['n_hold']} R={res['rebal']}d")
        print(f"区间 {res['period']}  {res['days']} 天")
        print(f"  IC={res['IC']}  ICIR={res['ICIR']}  t={res['IC_t']}  正IC比={res['IC_pos_ratio']}")
        print(f"  年化={res['ann']:.1%}  夏普={res['sharpe']}  回撤={res['mdd']:.1%}  Calmar={res['calmar']}")
        print(f"  年收益: " + "  ".join(f"{k}:{v:+.0%}" for k, v in res["yearly"].items()))


if __name__ == "__main__":
    main()
