# -*- coding: utf-8 -*-
import json, sys, glob
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

for f in ["PingFang SC","Heiti SC","Arial Unicode MS","Songti SC"]:
    try:
        font_manager.findfont(f, fallback_to_default=False)
        matplotlib.rcParams["font.family"] = f
        break
    except Exception:
        continue
matplotlib.rcParams["axes.unicode_minus"] = False

files = sys.argv[1:]
for path in files:
    d = json.load(open(path))
    tr = d["tr"]; pre = d["pre"]
    x = list(range(len(tr)))
    price = [b["price"] for b in tr]
    avg = [b["avg"] for b in tr]
    t = [b["t"] for b in tr]
    fig, ax = plt.subplots(figsize=(11, 4.2), dpi=140)
    ax.axhspan(min(min(price), pre)*0.99, max(max(price), pre)*1.01, color="#fbfbfb")
    ax.plot(x, price, color="#1f5fd0", lw=1.6, label="股价")
    ax.plot(x, avg, color="#e8a020", lw=1.7, label="均价线")
    ax.axhline(pre, color="#999999", ls="--", lw=0.9, label="昨收 %.2f" % pre)
    i1430 = next((i for i, s in enumerate(t) if s >= "14:30"), None)
    if i1430:
        ax.axvspan(i1430, len(x)-1, color="#ffe9b8", alpha=0.45, lw=0)
        ax.text(i1430+1, max(price)*1.002, "14:30 后", fontsize=9, color="#b07800")
    ih = price.index(max(price))
    ax.scatter([ih], [max(price)], color="#d02020", s=28, zorder=5)
    ax.annotate("日高 %.2f @%s" % (max(price), t[ih]), (ih, max(price)), textcoords="offset points", xytext=(6, 8), fontsize=9, color="#d02020")
    il = price.index(min(price))
    ax.annotate("日低 %.2f @%s" % (min(price), t[il]), (il, min(price)), textcoords="offset points", xytext=(6, -14), fontsize=9, color="#2e8b57")
    step = max(1, len(x)//11)
    ax.set_xticks(x[::step]); ax.set_xticklabels(t[::step], rotation=0, fontsize=8)
    ax.set_xlim(0, len(x)-1)
    ax.grid(alpha=0.25, lw=0.6)
    ax.set_title("%s %s  现价 %.2f (%+.2f%%)  均价 %.2f  换手 %.2f%%  量比 %.2f  市值 %.1f亿" % (
        d["code"], d["name"], tr[-1]["price"], d["pct"], tr[-1]["avg"], d.get("tok",0), d.get("vr",0), d.get("cap",0)), fontsize=11)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.8)
    ax.set_ylabel("价格(元)")
    fig.tight_layout()
    out = path.replace(".json", ".png")
    fig.savefig(out); plt.close(fig)
    print(out)
