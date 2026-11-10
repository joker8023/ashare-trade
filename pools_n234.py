import os; os.environ.setdefault("ASHARE_PIVOTS","pivots_long_clean.pkl")
import pandas as pd
import engine as E
for n,reb in [(2,40),(4,40),(2,30),(3,30),(4,30),(5,30),(2,60),(3,60),(4,60),(5,60)]:
    try:
        pd.read_pickle(f'results/pool/long_N{n}_R{reb}_05.pkl')
        print(f'N{n}R{reb} cached', flush=True)
    except Exception:
        r = E.returns_series('amihud',n_hold=n,rebal=reb,size_range=(0.05,0.30),cost=0.005)
        r.to_pickle(f'results/pool/long_N{n}_R{reb}_05.pkl')
        print(f'N{n}R{reb} computed', flush=True)
