# morning rocket diagnostic on 5m data
import pandas as pd
import numpy as np
from pathlib import Path
import strategy_supertrend as ST
BASE = Path(__file__).resolve().parent
SYM = "159915"
df5 = pd.read_csv(BASE / "data" / "minute_etf" / (SYM + "_5m.csv"))
print("cols:")
print(df5.columns.tolist())
print(df5.head(2).to_string())
df5.columns = ["ts", "o", "c", "h", "l", "v", "amt"]
df5["ts"] = pd.to_datetime(df5["ts"])
df5 = df5.sort_values("ts").reset_index(drop=True)
df5["day"] = df5["ts"].dt.date
df5["hm"] = df5["ts"].dt.strftime("%H:%M")
g = df5.groupby("day")
daily = pd.DataFrame({"open": g.first()["o"], "high": g.max()["h"], "low": g.min()["l"], "close": g.last()["c"]})
daily.index = pd.to_datetime(daily.index)
mh = g.apply(lambda x: x.loc[x["hm"] <= "10:30", "h"].max())
mh.index = pd.to_datetime(mh.index)
body = (daily["close"] - daily["open"]).abs()
bma = body.rolling(10).mean()
st = ST.supertrend(daily, 10, 3.0)
daily["sdir"] = st["dir"].values
daily["fwd"] = daily["close"].shift(-1) / daily["close"] - 1
print("days " + str(len(daily)) + " " + str(daily.index[0].date()) + "~" + str(daily.index[-1].date()))
print("st_long_share " + str(round(float((daily["sdir"] == 1).mean()), 3)))
for K in [0.5, 1.0, 1.5]:
    lvl = daily["open"] + K * bma
    rt = (mh > lvl)
    px = (daily["close"] > lvl)
    agree = float((rt == px).mean())
    sub = daily[daily["sdir"] == 1]
    rrk = sub.loc[rt.reindex(sub.index).fillna(False), "fwd"].mean()
    rpl = sub.loc[(~rt).reindex(sub.index).fillna(True), "fwd"].mean()
    print("K=" + str(K) + " rocket_days=" + str(int(rt.sum())) + " agree=" + str(round(agree, 3)) + " fwd_rocket%=" + str(round(float(rrk) * 100, 3)) + " fwd_plain%=" + str(round(float(rpl) * 100, 3)))
