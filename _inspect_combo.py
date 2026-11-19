import pickle, pathlib
import pandas as pd
for name in ["combo_w50_equity","combo_w60_equity","combo_w70_equity","combo_w80_equity","combo_w90_ME_equity","combo_w90_QE_equity"]:
    p = pathlib.Path(f"results/r30_bt/{name}.pkl")
    print("="*60)
    print(name, p.exists(), p.stat().st_size if p.exists() else None)
    obj = pickle.load(open(p,"rb"))
    print(type(obj))
    if isinstance(obj, dict):
        print("keys:", list(obj.keys()))
        for k,v in obj.items():
            print(f"--- {k}: {type(v)}")
            print(str(v)[:1500])
    elif isinstance(obj, pd.DataFrame):
        print(obj.shape)
        print(obj.head(3).to_string())
        print(obj.tail(3).to_string())
    else:
        print(str(obj)[:2000])
