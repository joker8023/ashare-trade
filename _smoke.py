import pandas as pd
from pathlib import Path
BASE = Path("/Users/joker/coding/ashare-trade")
DATA = BASE / "data"
daily = pd.read_pickle(DATA / "ashare_daily_long.pkl")
LAST = daily["date"].max()
START = (LAST + pd.Timedelta(days=1)).strftime("%Y%m%d")
END = "20261112"
KEEP = ["date","open","high","low","close","volume","amount"]
def one(code):
    import akshare as ak
    df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=START, end_date=END, adjust="qfq")
    if df is None or len(df)==0:
        return None
    df = df.rename(columns={"日期": "date", "\u5f00\u76d8": "open", "\u6536\u76d8": "close", "\u6700\u9ad8": "high", "\u6700\u4f4e": "low", "\u6210\u4ea4\u91cf": "volume", "\u6210\u4ea4\u989d": "amount"})
    df = df[KEEP].copy()
    df["date"] = pd.to_datetime(df["date"])
    df["code"] = code
    df = df[df["date"] > LAST]
    return df
for c in ["000001","600000","300750"]:
    df=one(c)
    print(c, "rows", 0 if df is None else len(df))
    if df is not None and len(df):
        print(df.to_string(index=False))
