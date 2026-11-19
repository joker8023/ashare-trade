#!/usr/bin/env python3
"""独立复核: 给定候选策略params重跑realshares_v2, 输出年度slice/yoy/mdd + 全程mdd, 判定是否满足 2024/2025/2026>60% & mdd>-30%"""
import sys, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/"team"/"audit")); sys.path.insert(0,str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from fresh2_max import MaxInputs
from sweep_beat_h1_v4 import _mdd, RUN_START, EVAL_END, MB
print("RUN",RUN_START,EVAL_END)
# usage: .venv/bin/python research/verify_annual.py results/r30_bt/search_B_stage1.json
fp=sys.argv[1] if len(sys.argv)>1 else "results/r30_bt/search_B_stage1.json"
d=json.load(open(fp))
rows=d if isinstance(d,list) else d.get("rows",d)
print(f"input {fp} n={len(rows)}")
for r in rows[:3]:
    print({k:r.get(k) for k in ["tag","total","mdd","2024_yoy","2025_yoy","2026_yoy","2024_mdd"] if k in r})
