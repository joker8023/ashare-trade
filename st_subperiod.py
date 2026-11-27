# -*- coding: utf-8 -*-
import pandas as pd
import st_overlay as O
ret = O.load_base()
m = O.market_proxy()
common = ret.index.intersection(m.index)
ret = ret.loc[common]
m = m.loc[common]
s = O.signals(m)
for label, lo, hi in [("early-2011-2018", "2011-01-01", "2018-12-31"), ("late-2019-2026", "2019-01-01", "2027-01-01")]:
    r = ret.loc[lo:hi]
    sg = s["st"].reindex(r.index).ffill().fillna(1.0)
    mg = s["ma20"].reindex(r.index).fillna(1.0)
    rows = []
    rows.append(O.perf(r, (1 + r).cumprod(), "base"))
    ro, ex, sw = O.apply_overlay(r, mg, 0.5)
    rows.append(O.perf(ro, (1 + ro).cumprod(), "ma20-proxy-0.5", "expo " + str(round(ex, 2))))
    ro, ex, sw = O.apply_overlay(r, sg, 0.5)
    rows.append(O.perf(ro, (1 + ro).cumprod(), "st-proxy-0.5", "expo " + str(round(ex, 2))))
    ro, ex, sw = O.nav_atr_stop(r)
    rows.append(O.perf(ro, (1 + ro).cumprod(), "nav-stop-0.5", "expo " + str(round(ex, 2))))
    print("==== " + label + " n=" + str(len(r)) + " ====")
    print(pd.DataFrame(rows).to_string(index=False))
