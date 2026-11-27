# -*- coding: utf-8 -*-
# SuperTrend as timing overlay on the Amihud 50-stock portfolio (live spec).
import numpy as np
import pandas as pd
from pathlib import Path
import risk_control as R
import strategy_supertrend as ST
BASE = Path(__file__).resolve().parent
OUT = BASE / "results_supertrend"
OUT.mkdir(exist_ok=True)
COST = 0.005
FACTOR = "amihud"
NHOLD = 50
REBAL = 60
SIZE = (0.05, 0.30)
MIN_ADV = 5e6
def load_base():
    r = R.cached_base(FACTOR, NHOLD, REBAL, SIZE, COST)
    print("base days " + str(len(r)) + " " + str(r.index[0].date()) + "~" + str(r.index[-1].date()))
    return r

def market_proxy():
    import engine as E
    p = E.piv()
    adv20 = p["amount"].rolling(20, min_periods=10).mean()
    liq = adv20 > MIN_ADV
    mo = p["open"].where(liq).mean(axis=1)
    mh = p["high"].where(liq).mean(axis=1)
    ml = p["low"].where(liq).mean(axis=1)
    mc = p["close"].where(liq).mean(axis=1)
    m = pd.DataFrame({"open": mo, "high": mh, "low": ml, "close": mc}).dropna()
    print("proxy days " + str(len(m)) + " " + str(m.index[0].date()) + "~" + str(m.index[-1].date()))
    return m

def signals(m):
    s = {}
    s["ma20"] = (m["close"] > m["close"].rolling(20).mean()).astype(float)
    d = ST.supertrend(m, 10, 3.0)["dir"]
    s["st"] = (d == 1).astype(float)
    try:
        idx = pd.read_pickle(BASE / "results" / "_cache" / "index_000852.pkl")
        s["idx_ma20"] = ((idx > idx.rolling(20).mean()).astype(float)).reindex(m.index).ffill()
    except Exception as e:
        print("index cache skip: " + str(e))
        s["idx_ma20"] = None
    return s
def apply_overlay(ret, sig, cut=0.5):
    s = sig.map({1.0: 1.0, 0.0: cut}).astype(float)
    pos = s.shift(1).fillna(1.0)
    rc = ret.reindex(pos.index).fillna(0.0)
    ro = rc * pos - (pos - pos.shift(1).fillna(1.0)).abs() * COST
    sw = int((s.diff().abs() > 0).sum())
    return ro, float(pos.mean()), sw

def nav_atr_stop(ret, mult=3.0, n=10, cut=0.5):
    nav = (1 + ret.fillna(0.0)).cumprod()
    chg = nav.diff().abs().fillna(0.0)
    atr = chg.ewm(alpha=1.0 / n, adjust=False).mean()
    pos = np.ones(len(nav))
    peak = float(nav.iloc[0])
    on = True
    for i in range(len(nav)):
        v = float(nav.iloc[i])
        a = float(atr.iloc[i])
        peak = max(peak, v)
        if on and v < peak - mult * a:
            on = False
        elif (not on) and v >= peak - mult * a:
            on = True
        pos[i] = 1.0 if on else cut
    pos = pd.Series(pos, index=nav.index)
    ppos = pos.shift(1).fillna(1.0)
    ro = ret.reindex(nav.index).fillna(0.0) * ppos - (ppos - ppos.shift(1).fillna(1.0)).abs() * COST
    sw = int((pos.diff().abs() > 0).sum())
    return ro, float(ppos.mean()), sw

def perf(ret, equity, label, extra=""):
    ret = ret.dropna()
    n = len(ret)
    tot = float(equity.iloc[-1] - 1)
    yrs = n / 252.0
    ann = (1 + tot) ** (1 / yrs) - 1 if yrs > 0 else 0.0
    vol = float(ret.std() * np.sqrt(252)) if n > 1 else 0.0
    sharpe = float(ret.mean() * 252 / vol) if vol > 0 else 0.0
    mdd = float((equity / equity.cummax() - 1).min())
    return {"label": label, "ann": round(float(ann), 4), "vol": round(vol, 4),
        "sharpe": round(sharpe, 3), "mdd": round(mdd, 4),
        "calmar": round(float(ann) / abs(mdd), 3) if mdd < 0 else 0.0, "info": extra}

def main():
    ret = load_base()
    m = market_proxy()
    common = ret.index.intersection(m.index)
    ret = ret.loc[common]
    m = m.loc[common]
    print("common " + str(len(common)) + " " + str(common[0].date()) + "~" + str(common[-1].date()))
    s = signals(m)
    out = []
    eb = (1 + ret).cumprod()
    out.append(perf(ret, eb, "base-no-overlay", "expo 1.0"))
    cfgs = [("ma20-proxy-0.5", s["ma20"], 0.5), ("st-proxy-0.5", s["st"], 0.5),
        ("st-proxy-0.0", s["st"], 0.0)]
    if s["idx_ma20"] is not None:
        cfgs.insert(0, ("ma20-index000852-0.5", s["idx_ma20"].reindex(common).ffill(), 0.5))
    curves = {"base": eb}
    for name, sig, cut in cfgs:
        ro, expo, sw = apply_overlay(ret, sig.reindex(common).ffill().fillna(1.0), cut)
        eo = (1 + ro).cumprod()
        curves[name] = eo
        out.append(perf(ro, eo, name, "expo " + str(round(expo, 3)) + " switches " + str(sw)))
    ro2, expo2, sw2 = nav_atr_stop(ret)
    curves["nav-atr-stop-0.5"] = (1 + ro2).cumprod()
    out.append(perf(ro2, curves["nav-atr-stop-0.5"], "nav-atr-stop-0.5", "expo " + str(round(expo2, 3)) + " switches " + str(sw2)))
    tbl = pd.DataFrame(out)
    print(tbl.to_string(index=False))
    tbl.to_csv(OUT / "overlay_stats.csv", index=False, encoding="utf-8")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(11, 5))
        for name, eo in curves.items():
            ax.plot(eo.index, eo, label=name, lw=1.3 if name != "base" else 1.1, alpha=0.9)
        ax.set_title("Amihud50 + timing overlays (T+1, cost 0.5pct/side incl. overlay turnover)")
        ax.set_ylabel("equity")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        p = OUT / "overlay_equity.png"
        fig.savefig(p, dpi=130)
        print("plot: " + str(p))
    except Exception as e:
        print("plot skip: " + str(e))

if __name__ == "__main__":
    main()
