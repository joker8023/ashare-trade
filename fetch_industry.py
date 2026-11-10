"""拉取东财行业板块 → 股票行业映射"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"


def main():
    import akshare as ak
    boards = ak.stock_board_industry_name_em()
    names = boards["板块名称"].tolist()
    print(f"行业板块: {len(names)} 个")

    rows = []
    errs = 0

    def fetch(bname):
        try:
            import akshare as ak2
            d = ak2.stock_board_industry_cons_em(symbol=bname)
            if d is None or len(d) == 0:
                return []
            return [(str(c), n, bname) for c, n in zip(d["代码"], d["名称"])]
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch, n): n for n in names}
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            if r is None:
                errs += 1
            else:
                rows.extend(r)
            if i % 50 == 0:
                print(f"  {i}/{len(names)}  累计 {len(rows)} 条  失败 {errs}", flush=True)

    df = pd.DataFrame(rows, columns=["code", "name", "industry"])
    # 一股多行业时取第一个 (板块按市值排序, 主行业在前)
    df = df.drop_duplicates(subset=["code"], keep="first")

    # 合并过小的行业为 OTHER, 避免分组太碎
    counts = df["industry"].value_counts()
    small = set(counts[counts < 15].index)
    df["industry_group"] = df["industry"].where(~df["industry"].isin(small), "OTHER")

    df.to_pickle(DATA / "industry_map.pkl")
    print(f"\n完成: {len(df)} 只股票, {df['industry'].nunique()} 个原始行业, "
          f"{df['industry_group'].nunique()} 个分组")
    print("\n最大行业:")
    print(df["industry"].value_counts().head(10).to_string())
    print("\n未覆盖股票数:", len(df) and "(见下)")


if __name__ == "__main__":
    main()
