import pandas as pd, glob
G0="2023-09-22"; G1="2024-10-16"; E="2026-11-12"
for f in sorted(glob.glob("results/*daily*.csv")):
  try:
    df = pd.read_csv(f)
    dt = [c for c in df.columns if "date" in c.lower()]
    eq = [c for c in df.columns if c.lower() in ("equity","eq","total","nav","value")]
    if not dt or not eq:
      print(f, "SKIP", list(df.columns)[:6])
      continue
    d = df[[dt[0], eq[0]]].copy()
    d[dt[0]] = pd.to_datetime(d[dt[0]])
    d = d.sort_values(dt[0]).set_index(dt[0])[eq[0]].dropna()
    def gv(t):
      s = d.loc[:t]
      return float(s.iloc[-1]) if len(s) else float("nan")
    g0, g1, e = gv(G0), gv(G1), gv(E)
    import math
    print(f, "n="+str(len(d)), "gap=%.2f" % ((g1/g0-1)*100), "span2y=%.2f" % ((e/g1-1)*100), "full=%.2f" % ((e/float(d.iloc[0])-1)*100))
  except Exception as ex:
    print(f, "ERR", str(ex)[:120])