# -*- coding: utf-8 -*-
# SuperTrend base + upgraded backtest. Daily T+1 next-open execution.
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
BASE = Path(__file__).resolve().parent
OUT = BASE / "results_supertrend"
OUT.mkdir(exist_ok=True)
COST_STOCK = 0.0015


def wilder_atr(h, l, c, n=10):
    prev_c = c.shift(1)
    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False).mean()


def supertrend(df, atr_period=10, multiplier=3.0):
    h, l, c = df["high"], df["low"], df["close"]
    atr = wilder_atr(h, l, c, atr_period)
    hl2 = (h + l) / 2.0
    basic_up = hl2 + multiplier * atr
    basic_lo = hl2 - multiplier * atr
    n = len(df)
    fu = np.full(n, np.nan)
    fl = np.full(n, np.nan)
    direction = np.full(n, 1)
    st = np.full(n, np.nan)
    cu = c.values; bu = basic_up.values; bl = basic_lo.values
    for i in range(n):
        if i == 0:
            fu[i] = bu[i]; fl[i] = bl[i]; direction[i] = 1; st[i] = fl[i]
            continue
        prev_fu = fu[i - 1]; prev_fl = fl[i - 1]; pc = cu[i - 1]
        fu[i] = bu[i] if (bu[i] < prev_fu or pc > prev_fu) else prev_fu
        fl[i] = bl[i] if (bl[i] > prev_fl or pc < prev_fl) else prev_fl
        if cu[i] > fu[i - 1]:
            direction[i] = 1
        elif cu[i] < fl[i - 1]:
            direction[i] = -1
        else:
            direction[i] = direction[i - 1]
        st[i] = fl[i] if direction[i] == 1 else fu[i]
    return pd.DataFrame({"atr": atr.values, "basic_up": bu, "basic_lo": bl,
        "final_up": fu, "final_lo": fl, "dir": direction, "line": st}, index=df.index)


def rsi14(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    r = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    return r.fillna(50)


def eff_ratio(c, n=10):
    chg = (c - c.shift(n)).abs()
    vol = c.diff().abs().rolling(n).sum()
    return (chg / vol.replace(0, np.nan)).fillna(0).clip(0, 1)

def backtest_basic(df, atr_period=10, mult=3.0, cost=COST_STOCK):
    d = df.copy()
    st = supertrend(d, atr_period, mult)
    d = d.join(st)
    sig = st["dir"]
    pos = sig.shift(1).fillna(1).clip(-1, 1)
    pos = pos.where(sig.notna(), 0)
    pos = pos.replace(-1, 0)
    d["pos"] = pos
    prev_pos = d["pos"].shift(1).fillna(0)
    overnight = d["open"] / d["close"].shift(1) - 1
    intraday = d["close"] / d["open"] - 1
    d["ret_asset"] = d["close"].pct_change().fillna(0)
    d["ret_strat"] = prev_pos * overnight.fillna(0) + d["pos"] * intraday.fillna(0)
    d["turn"] = (d["pos"] - prev_pos).abs()
    d["ret_strat"] = d["ret_strat"] - d["turn"] * cost
    d["equity"] = (1 + d["ret_strat"]).cumprod()
    d["equity_bh"] = (1 + d["ret_asset"]).cumprod()
    return d


def backtest_upgraded(df, atr_period=10, base_mult=3.0, ma_trend=60, k_rocket=0.5,
                      body_n=10, er_n=10, init_mult=2.0, rsi_n=14, cost=COST_STOCK,
                      use_rocket=True, use_er=True, use_rsi=True):
    d = df.copy()
    st = supertrend(d, atr_period, base_mult)
    d = d.join(st)
    d["ma60"] = d["close"].rolling(ma_trend).mean()
    body = (d["close"] - d["open"]).abs()
    d["body_ma"] = body.rolling(body_n).mean()
    d["rocket_lv"] = d["open"] + k_rocket * d["body_ma"]
    d["rsi"] = rsi14(d["close"], rsi_n)
    d["er"] = eff_ratio(d["close"], er_n)
    pos = np.zeros(len(d))
    scale = np.ones(len(d))
    holding = False
    cur_scale = 1.0
    entry_px = np.nan
    entry_atr = np.nan
    peak = np.nan
    closes = d["close"].values
    opens = d["open"].values
    dirs = d["dir"].values
    ma = d["ma60"].values
    rlv = d["rocket_lv"].values
    rsi = d["rsi"].values
    er = d["er"].values
    atr = d["atr"].values
    idx = d.index
    sig_pos = np.zeros(len(d))
    for i in range(len(d)):
        if i < max(atr_period + 2, ma_trend, body_n + 1):
            sig_pos[i] = 0
            continue
        c = closes[i]
        up_ok = (c > ma[i]) if not np.isnan(ma[i]) else True
        rocket_ok = (c > rlv[i]) if (not np.isnan(rlv[i]) and use_rocket) else True
        st_ok = (dirs[i] == 1)
        if not holding:
            if up_ok and rocket_ok and st_ok:
                holding = True
                cur_scale = 1.0
                entry_px = c
                entry_atr = atr[i]
                peak = c
        else:
            peak = max(peak, c)
            er_now = er[i] if use_er else 0.0
            m_adapt = base_mult * (1 - 0.6 * er_now)
            trail = peak - m_adapt * atr[i]
            init_stop = entry_px - init_mult * entry_atr
            stop = max(trail, init_stop)
            hard_flip = (dirs[i] == -1)
            if c < stop or hard_flip:
                holding = False
                cur_scale = 1.0
                sig_pos[i] = 0
                scale[i] = 0
                continue
            if use_rsi:
                if cur_scale == 1.0 and rsi[i] > 80:
                    cur_scale = 0.5
                elif cur_scale == 0.5 and rsi[i] <= 30:
                    cur_scale = 1.0
        sig_pos[i] = (1.0 if holding else 0.0)
        scale[i] = (cur_scale if holding else 0.0)
    d["sig"] = sig_pos
    d["scale"] = scale
    d["pos"] = pd.Series(sig_pos, index=idx).shift(1).fillna(0) * pd.Series(scale, index=idx).shift(1).fillna(0)
    prev_pos = d["pos"].shift(1).fillna(0)
    overnight = d["open"] / d["close"].shift(1) - 1
    intraday = d["close"] / d["open"] - 1
    d["ret_asset"] = d["close"].pct_change().fillna(0)
    d["ret_strat"] = prev_pos * overnight.fillna(0) + d["pos"] * intraday.fillna(0)
    d["turn"] = (d["pos"] - prev_pos).abs()
    d["ret_strat"] = d["ret_strat"] - d["turn"] * cost
    d["equity"] = (1 + d["ret_strat"]).cumprod()
    d["equity_bh"] = (1 + d["ret_asset"]).cumprod()
    return d

def perf(ret, equity, label):
    ret = ret.dropna()
    n = len(ret)
    tot = float(equity.iloc[-1] - 1)
    yrs = n / 252.0 if n else np.nan
    ann = (1 + tot) ** (1 / yrs) - 1 if yrs and yrs > 0 else 0
    vol = float(ret.std() * np.sqrt(252)) if n > 1 else 0
    sharpe = float(ret.mean() * 252 / vol) if vol > 0 else 0
    mdd = float((equity / equity.cummax() - 1).min())
    trd = int((ret != 0).sum())
    return {"label": label, "days": n, "total": round(tot, 4), "ann": round(float(ann), 4),
        "vol": round(vol, 4), "sharpe": round(float(sharpe), 3), "mdd": round(mdd, 4),
        "calmar": round(float(ann) / abs(mdd), 3) if mdd < 0 else 0, "trades_days": trd}


def load_stock(code, start="2015-01-01"):
    import os as _os
    piv_name = _os.getenv("ASHARE_PIVOTS", "pivots_2020_clean.pkl")
    p = pd.read_pickle(BASE / "data" / piv_name)
    for k in ["open", "high", "low", "close"]:
        if code not in p[k].columns:
            raise SystemExit("code not in pivots: " + code)
    df = pd.DataFrame({k: p[k][code] for k in ["open", "high", "low", "close"]})
    df = df[df.index >= pd.Timestamp(start)].dropna()
    df = df.astype(float)
    return df


def run_single(code, start="2015-01-01", make_plot=True):
    df = load_stock(code, start)
    b = backtest_basic(df)
    u = backtest_upgraded(df)
    rows = [perf(b["ret_asset"], b["equity_bh"], "buyhold"),
            perf(b["ret_strat"], b["equity"], "basic(10,3)"),
            perf(u["ret_strat"], u["equity"], "upgraded")]
    tbl = pd.DataFrame(rows)
    print("code " + code + "  " + str(df.index[0].date()) + "~" + str(df.index[-1].date()) + "  n=" + str(len(df)))
    print(tbl.to_string(index=False))
    exp_b = float(b["pos"].mean()); exp_u = float(u["pos"].mean())
    print("exposure basic=" + str(round(exp_b, 3)) + " upgraded=" + str(round(exp_u, 3)))
    try:
        n_up = int(((u["sig"].diff() == 1).sum()))
        n_dn = int(((u["sig"].diff() == -1).sum()))
        print("upgraded entries=" + str(n_up) + " exits=" + str(n_dn))
    except Exception as e:
        print("count skip: " + str(e))
    if make_plot:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(11, 5))
            ax.plot(b.index, b["equity_bh"], label="buyhold", lw=1.1, alpha=0.8)
            ax.plot(b.index, b["equity"], label="basic ST(10,3)", lw=1.3)
            ax.plot(u.index, u["equity"], label="upgraded", lw=1.3)
            ax.set_title(code + " SuperTrend basic vs upgraded (T+1, cost 0.15pct/side)")
            ax.set_ylabel("equity")
            ax.legend(); ax.grid(alpha=0.3)
            fig.tight_layout()
            out = OUT / (code + "_st_equity.png")
            fig.savefig(out, dpi=130)
            print("plot: " + str(out))
        except Exception as e:
            print("plot skip: " + str(e))
    return tbl, b, u

def ablation(code, start="2015-01-01"):
    df = load_stock(code, start)
    cfgs = [
        ("basic", dict(use_rocket=False, use_er=False, use_rsi=False)),
        ("+rocket", dict(use_rocket=True, use_er=False, use_rsi=False)),
        ("+ERtrail", dict(use_rocket=False, use_er=True, use_rsi=False)),
        ("+RSIhalf", dict(use_rocket=False, use_er=False, use_rsi=True)),
        ("full-upgraded", dict(use_rocket=True, use_er=True, use_rsi=True)),
    ]
    rows = []
    b = backtest_basic(df)
    rows.append(perf(b["ret_strat"], b["equity"], "basic(10,3)"))
    for name, kw in cfgs:
        if name == "basic":
            continue
        u = backtest_upgraded(df, **kw)
        r = perf(u["ret_strat"], u["equity"], name)
        r["exposure"] = round(float(u["pos"].mean()), 3)
        rows.append(r)
    rows.append(perf(b["ret_asset"], b["equity_bh"], "buyhold"))
    tbl = pd.DataFrame(rows)
    print("ablation on " + code)
    print(tbl.to_string(index=False))
    return tbl


def run_pool(n=50, start="2015-01-01", seed=7):
    import os as _os
    piv_name = _os.getenv("ASHARE_PIVOTS", "pivots_2020_clean.pkl")
    p = pd.read_pickle(BASE / "data" / piv_name)
    closes = p["close"]
    cands = [c for c in closes.columns if closes[c].loc[pd.Timestamp(start):].notna().sum() > 1500]
    rng = np.random.RandomState(seed)
    rng.shuffle(cands)
    codes = cands[:n]
    print("pool codes: " + str(len(codes)))
    rets_b, rets_u, rets_bh = [], [], []
    for code in codes:
        try:
            df = pd.DataFrame({k: p[k][code] for k in ["open", "high", "low", "close"]})
            df = df[df.index >= pd.Timestamp(start)].dropna().astype(float)
            if len(df) < 800:
                continue
            b = backtest_basic(df)
            u = backtest_upgraded(df)
            rets_b.append(b["ret_strat"].rename(code))
            rets_u.append(u["ret_strat"].rename(code))
            rets_bh.append(b["ret_asset"].rename(code))
        except Exception as e:
            print("skip " + code + ": " + str(e))
    Rb = pd.concat(rets_b, axis=1).mean(axis=1)
    Ru = pd.concat(rets_u, axis=1).mean(axis=1)
    Rh = pd.concat(rets_bh, axis=1).mean(axis=1)
    Eb = (1 + Rb).cumprod(); Eu = (1 + Ru).cumprod(); Eh = (1 + Rh).cumprod()
    tbl = pd.DataFrame([perf(Rh, Eh, "pool-buyhold"), perf(Rb, Eb, "pool-basic"), perf(Ru, Eu, "pool-upgraded")])
    print(tbl.to_string(index=False))
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(Eh.index, Eh, label="pool buyhold", lw=1.1, alpha=0.8)
        ax.plot(Eb.index, Eb, label="pool basic", lw=1.3)
        ax.plot(Eu.index, Eu, label="pool upgraded", lw=1.3)
        ax.set_title("random" + str(n) + "-stock equal-weight: ST timing overlay")
        ax.legend(); ax.grid(alpha=0.3)
        fig.tight_layout()
        out = OUT / ("pool" + str(n) + "_st_equity.png")
        fig.savefig(out, dpi=130)
        print("plot: " + str(out))
    except Exception as e:
        print("plot skip: " + str(e))
    return tbl

def run_intraday(sym="159915"):
    path = BASE / "data" / "minute_etf" / (sym + "_5m.csv")
    df5 = pd.read_csv(path, parse_dates=["time_cn"] if "time_cn" in pd.read_csv(path, nrows=1).columns else ["time_col"])
    print("intraday demo: use daily-approx on 5m file header only")
    print(str(path) + " rows=" + str(len(df5)))
    return df5.head(3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default=None)
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--pool", type=int, default=0)
    ap.add_argument("--ablation", action="store_true")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--no-plot", action="store_true")
    a = ap.parse_args()
    if a.demo or (not a.code and not a.pool):
        for code in ["600519", "300750", "000001"]:
            print("=" * 72)
            run_single(code, a.start, make_plot=not a.no_plot)
        print("=" * 72)
        print("ablation on 600519:")
        ablation("600519", a.start)
        return
    if a.ablation and a.code:
        ablation(a.code, a.start)
        return
    if a.pool:
        run_pool(a.pool, a.start)
        return
    if a.code:
        run_single(a.code, a.start, make_plot=not a.no_plot)
        return


if __name__ == "__main__":
    main()
