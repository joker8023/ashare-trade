"""EM估值历史批量下载：stock_value_em逐股拉PE(TTM)/PB/PS，全市场约35分钟"""
import pickle, time, os
import pandas as pd
import akshare as ak

codes = pickle.load(open("data/universe.pkl", "rb"))["code"].astype(str).tolist()
print(f"universe: {len(codes)}", flush=True)
out = "data/value_em.pkl"
done = {}
if os.path.exists(out):
    done = pickle.load(open(out, "rb"))
    print(f"resume: 已有 {len(done)} 只", flush=True)

ok = err = 0
for i, code in enumerate(codes):
    if code in done:
        continue
    try:
        df = ak.stock_value_em(symbol=code)
        df["数据日期"] = pd.to_datetime(df["数据日期"])
        done[code] = df.set_index("数据日期")[["PE(TTM)", "市净率", "市销率"]].astype(float)
        ok += 1
    except Exception as e:
        err += 1
    if (ok + err) % 200 == 0:
        pickle.dump(done, open(out, "wb"))
        print(f"[{i+1}/{len(codes)}] ok={ok} err={err}", flush=True)
pickle.dump(done, open(out, "wb"))
print(f"DONE ok={ok} err={err} total={len(done)} -> {out}", flush=True)
