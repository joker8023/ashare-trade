# -*- coding: utf-8 -*-
"""分时图渲染：股价 + 均价线(VWAP) + 昨收 + 14:30 分界。

用法:
    .venv/bin/python .dsh/skills/ashare-six-step-screen/scripts/render_fenshi.py results/min/002566.json [更多.json ...]

输出与输入同目录的同名 .png。数据由 scripts/screen.mjs 写入。
"""
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

for name in ("PingFang SC", "Hiragino Sans GB", "Heiti SC", "Arial Unicode MS", "Songti SC"):
    try:
        font_manager.findfont(name, fallback_to_default=False)
        matplotlib.rcParams["font.family"] = name
        break
    except Exception:
        continue
matplotlib.rcParams["axes.unicode_minus"] = False


def render(path):
    d = json.load(open(path, encoding="utf-8"))
    tr = d["tr"]
    pre = d["pre"]
    t = [b["t"] for b in tr]
    price = [b["price"] for b in tr]
    avg = [b["avg"] for b in tr]

    fig, ax = plt.subplots(figsize=(11, 4.2), dpi=140)
    ax.plot(range(len(tr)), price, color="#1f5fd0", lw=1.6, label="股价")
    ax.plot(range(len(tr)), avg, color="#e8a020", lw=1.7, label="均价线")
    ax.axhline(pre, color="#999999", ls="--", lw=0.9, label="昨收 %.2f" % pre)

    i1430 = next((i for i, s in enumerate(t) if s >= "14:30"), None)
    if i1430 is not None:
        ax.axvspan(i1430, len(tr) - 1, color="#ffe9b8", alpha=0.45, lw=0)
        ax.text(i1430 + 1, max(price) * 1.002, "14:30 后", fontsize=9, color="#b07800")

    hi = max(price)
    ih = price.index(hi)
    ax.scatter([ih], [hi], color="#d02020", s=30, zorder=5)
    ax.annotate("日高 %.2f @%s" % (hi, t[ih]), (ih, hi), textcoords="offset points",
                xytext=(6, 8), fontsize=9, color="#d02020")
    lo = min(price)
    il = price.index(lo)
    ax.annotate("日低 %.2f @%s" % (lo, t[il]), (il, lo), textcoords="offset points",
                xytext=(6, -14), fontsize=9, color="#2e8b57")

    step = max(1, len(tr) // 11)
    ax.set_xticks(range(0, len(tr), step))
    ax.set_xticklabels(t[::step], fontsize=8)
    ax.set_xlim(0, len(tr) - 1)
    ax.grid(alpha=0.25, lw=0.6)
    ax.set_ylabel("价格(元)")
    ax.set_title("%s %s  现价 %.2f (%+.2f%%)  均价 %.2f  换手 %.2f%%  量比 %.2f  市值 %.1f亿" % (
        d.get("code", ""), d.get("name", ""), price[-1], d.get("pct", 0), avg[-1],
        d.get("tok", 0), d.get("vr", 0), d.get("cap", 0)), fontsize=11)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.8)
    fig.tight_layout()
    out = path[:-5] + ".png"
    fig.savefig(out)
    plt.close(fig)
    print(out)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: render_fenshi.py <min.json> [...]")
        sys.exit(1)
    for p in sys.argv[1:]:
        render(p)
