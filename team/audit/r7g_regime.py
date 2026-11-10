import sys
sys.path.insert(0, "team")
import numpy as np
import pandas as pd
from harness import bundle
b = bundle()
idx = pd.read_pickle("results/_cache/index_000985.pkl")
s_ = idx.sort_index().astype(float)
s = s_.reindex(b.dates).ffill()
ma20 = s.rolling(20).mean()
df = pd.read_csv("team/runs/batch_032_r7g_events.csv", parse_dates=["date"])
df = df.set_index("date").sort_index()
reg = pd.Series(np.where(s > ma20, "up", "down"), index=b.dates)
for h in [7, 14, 30]:
    xs = pd.to_numeric(df["new_%d" % h], errors="coerce") - pd.to_numeric(df["pool_%d" % h], errors="coerce")
    sp = pd.to_numeric(df["new_%d" % h], errors="coerce") - pd.to_numeric(df["old_%d" % h], errors="coerce")
    print("h=%d" % h, flush=True)
    for r in ["up", "down"]:
        m = reg.reindex(df.index) == r
        x = xs[m].dropna()
        y = sp[m].dropna()
        print("  %s n=%d xs_mean=%+.4f xs_hit=%.3f spread_mean=%+.4f spread_hit=%.3f" % (
            r, int(m.sum()), x.mean(), float((x > 0).mean()), y.mean(), float((y > 0).mean())), flush=True)
print("=== DONE ===", flush=True)
