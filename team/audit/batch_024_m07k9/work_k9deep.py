#!/usr/bin/env python3
"""K9 深尾独立复算: base_M07 vs g_bf07_winA30.
只新增本目录文件. 复用已审计引擎 (K8 模块的 get_shadows + v4 build_ns 同配方),
另加 holdings/fills  exact 记录补丁 (仅记录, 不改成交逻辑).
产出: part_k9deep.json (全精度短窗差值 + 尾部21/63持仓身份 + 归因 + 未来函数动静态检查).
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"team"/"audit")); sys.path.insert(0, str(ROOT/"research"))
import pandas as pd
import prior_check as pc
from prior_check import _cost_buy_real, _cost_sell_real
import sweep_beat_m07_k8 as K
import sweep_beat_h1_v4 as V4

M07 = {"1m": -4.09, "3m": 17.28, "6m": 39.00, "1y": 164.05, "2y": 1474.08, "3y": 1677.53,
       "mdd": -27.05, "total": 1863.27}
SLIP = 0.002

def build_ns_hold(bx, by_, bf):
    src = (ROOT/"research"/"switch_engine.py").read_text()
    def _once(old, new):
        assert src.count(old) == 1, (old[:60], src.count(old))
        return src.replace(old, new)
    # NOTE: closure over changing src -> apply sequentially like V4.build_ns
    import sweep_beat_h1_v4 as _v
    ns_src = src
    def once(old, new):
        nonlocal ns_src
        assert ns_src.count(old) == 1, (old[:60], ns_src.count(old))
        ns_src = ns_src.replace(old, new)
    add = "\n    _brake = False\n    _brake_trough = 0.0\n    _brake_peak = 0.0\n    _brake_log: List = []\n    _BRAKE_X = %s\n    _BRAKE_Y = %s\n    _BRAKE_F = %s" % (bx, by_, bf)
    once(_v.AA, _v.AA + add + "\n    hold_rows: List = []\n    fill_rows: List = []")
    once(_v.BB, _v.BB + ", _brake, _brake_trough, _brake_peak, _brake_log")
    brake_eval = "\n        tb_mv_pre = 0.0\n        for tb_cc, tb_p in pos.items():\n            tb_px = px_ffill_or_nan(mark, day, tb_cc)\n            if pd.isna(tb_px):\n                tb_px = tb_p.entry_px\n            tb_mv_pre += tb_p.shares * tb_px\n        tb_eq_pre = cash + tb_mv_pre\n        if tb_eq_pre > _brake_peak:\n            _brake_peak = tb_eq_pre\n        if not _brake and _brake_peak > 0 and (_brake_peak - tb_eq_pre) / _brake_peak >= _BRAKE_X:\n            _brake = True\n            _brake_trough = tb_eq_pre\n            _brake_log.append((str(day.date()), 'ON', round(float((_brake_peak - tb_eq_pre) / _brake_peak) * 100, 2)))\n        elif _brake:\n            if tb_eq_pre < _brake_trough:\n                _brake_trough = tb_eq_pre\n            if _brake_trough > 0 and tb_eq_pre >= _brake_trough * (1.0 + _BRAKE_Y):\n                _brake = False\n                _brake_log.append((str(day.date()), 'OFF', round(float(tb_eq_pre / _brake_trough - 1) * 100, 2)))"
    once(_v.CC, _v.CC + brake_eval)
    skip_block = "\n        if not switching and set(picks) == set(pos):\n            return False"
    once(_v.DD, _v.DD + skip_block)
    once(_v.PICKLINE, "        _ex = (exclude_a if mode == 'A' else exclude_b) if (exclude_a is not None or exclude_b is not None) else exclude\n" + _v.PICKLINE.replace("exclude=exclude", "exclude=_ex"))
    once(_v.SIG, _v.SIG + "\n    exclude_a=None,\n    exclude_b=None,")
    once(_v.EE, "        alloc = alloc * (_BRAKE_F if _brake else 1.0)\n" + _v.EE)
    # holdings 快照 (与 V4 的 brake_peak 更新同序, pos 仍是当日收盘后持仓)
    once(_v.FF, _v.FF + "\n        if (cash + mv) > _brake_peak:\n            _brake_peak = cash + mv\n        hold_rows.append((day, {cc: float(p.shares) for cc, p in pos.items()}))")
    # fills 记录 (买入成交点, sig_day/exec day 均在作用域)
    once("            pos[code] = Pos(shares=sh, entry_px=px, entry_i=i, high=px,",
         "            fill_rows.append((str(day.date()), str(sig_day.date()), code, float(sh), float(px), float(fee)))\n            pos[code] = Pos(shares=sh, entry_px=px, entry_i=i, high=px,")
    once(_v.GG, _v.GG + " brake_log=_brake_log,")
    once("        total_cost=float(total_cost),",
         "        total_cost=float(total_cost),\n        holdings=[(str(d), dict(h)) for d, h in hold_rows],\n        fills=[list(x) for x in fill_rows],")
    ns = {}
    exec(compile(ns_src, "switch_engine_hold", "exec"), ns)
    return ns

def run_hold(tag, **kw):
    cfg = dict(cut_a=0.80, win_a=40, cut_b=0.80, win_b=20, stop=0.25, a_take=1.2,
               b_take=0.80, a_n=5, b_n=4, b_exp=0.9, rs=60, bx=0.18, by_=0.08, bf=0.6)
    cfg.update(kw)
    bx, by_, bf, rs = cfg.pop("bx"), cfg.pop("by_"), cfg.pop("bf"), cfg.pop("rs")
    inp_a, inp_b, ra, rb, CA, CFG_B = K.get_shadows(cfg["cut_a"], cfg["win_a"], cfg["cut_b"],
        cfg["win_b"], cfg["stop"], cfg["a_take"], cfg["b_take"], cfg["a_n"], cfg["b_n"], cfg["b_exp"])
    KW = dict(n=cfg["a_n"], rebal=20, take=cfg["a_take"], exposure=1.0, phase=0,
              inp_b=inp_b, cfg_b=CFG_B, shadow_a=ra.eq, shadow_b=rb.eq, rs_lookback=rs,
              exclude_a=K.MB, exclude_b=K.MB,
              **{k: v for k, v in CA.items() if k != "exclude"})
    ns = build_ns_hold(bx, by_, bf)
    res = ns["run_strategy_switch"](inp_a, lock_mode=None, **KW)
    eq = res.eq.iloc[:, 0] if isinstance(res.eq, pd.DataFrame) else res.eq
    return res, eq.dropna(), inp_a

def win_full(eq, d):
    sub = eq.tail(d+1)
    return float(sub.iloc[-1]/sub.iloc[0]-1)*100, sub.index[0], sub.index[-1]

def main():
    out = {}
    # 1) 两配置重跑 (与 K8 同参)
    GBF07 = dict(by_=0.05, cut_a=0.78, cut_b=0.78, bx=0.15, bf=0.7)
    res_b, eq_b, inp_b = run_hold("base_M07")
    res_g, eq_g, inp_g = run_hold("g_bf07_winA30", win_a=30, **GBF07)
    assert inp_b.mark.equals(inp_g.mark), "mark 不一致则归因不可比"
    mark = inp_b.mark
    out["eval_last"] = str(eq_b.index[-1].date())
    # 2) 与 K8 文件 2dp 对账
    rows = {r["tag"]: r for r in json.loads((ROOT/"results"/"r30_bt"/"sweep_beat_m07_k8.json").read_text())}
    chk = {}
    for tag, eq in (("base_M07", eq_b), ("g_bf07_winA30", eq_g)):
        f = rows[tag]
        calc = {"total": round(float(eq.iloc[-1]/eq.iloc[0]-1)*100, 2)}
        chk[tag] = {"file_total": f["total"], "rerun_total": calc["total"],
                    "match": abs(f["total"]-calc["total"]) < 0.005,
                    "file_trades": f["trades"], "rerun_trades": len(res_b.trades if tag=="base_M07" else res_g.trades)}
    out["file_recon"] = chk
    # 3) 全精度短窗差值
    wins = {}
    for w, d in K.WINDOWS.items():
        rb, sb, eb = win_full(eq_b, d); rg, sg, eg = win_full(eq_g, d)
        wins[w] = {"days": d, "base": rb, "g": rg, "diff_pp": rg-rb,
                   "start": str(sb.date()), "end": str(eb.date())}
    out["windows_full"] = wins
    # 4) 尾部持仓身份 + 归因 (21/63)
    for w, d in (("1m", 21), ("3m", 63)):
        S = eq_b.tail(d+1).index[0]; E = eq_b.tail(d+1).index[-1]
        assert str(E.date()) == out["eval_last"]
        seg = {}
        contribs = {}
        for tag, res, eq in (("base", res_b, eq_b), ("g", res_g, eq_g)):
            hold = {pd.Timestamp(k): v for k, v in res.meta["holdings"]}
            fills = [(pd.Timestamp(x[0]), pd.Timestamp(x[1]), x[2], x[3], x[4], x[5]) for x in res.meta["fills"]]
            tr = res.trades
            hS, hE = hold.get(S, {}), hold.get(E, {})
            days = [x for x in hold if S <= x <= E]
            ever = sorted({c for x in days for c in hold[x]})
            # 买入/卖出名义 (S,E] 内
            bmap, smap, feemap = {}, {}, {}
            for fd, sd, code, sh, px, fee in fills:
                if S < fd <= E:
                    bmap[code] = bmap.get(code, 0.0) + sh*px
                    feemap[code] = feemap.get(code, 0.0) + fee
            if len(tr):
                te = tr[(tr.exit_date > S) & (tr.exit_date <= E)]
                for _, r in te.iterrows():
                    smap[r["code"]] = smap.get(r["code"], 0.0) + float(r["shares"]*r["exit_px"])
                    feemap[r["code"]] = feemap.get(r["code"], 0.0) + _cost_sell_real(float(r["shares"]*r["exit_px"]), SLIP)
            contrib = {}
            for code in sorted(set(ever) | set(bmap) | set(smap)):
                pxS = mark.at[S, code] if code in mark.columns and pd.notna(mark.at[S, code]) else None
                pxE = mark.at[E, code] if code in mark.columns and pd.notna(mark.at[E, code]) else None
                if pxS is None or pxE is None:
                    # 停牌 fallback: 用成交价
                    fb = [f for f in fills if f[2] == code]
                    if pxS is None and fb: pxS = fb[0][4]
                    if pxE is None and fb: pxE = fb[-1][4]
                vS = hS.get(code, 0.0)*(pxS or 0.0); vE = hE.get(code, 0.0)*(pxE or 0.0)
                contrib[code] = (vE - vS) - (bmap.get(code, 0.0) - smap.get(code, 0.0))
            dEq = float(eq.loc[E] - eq.loc[S])
            fees = sum(feemap.values())
            recon = sum(contrib.values()) - fees - dEq
            # entry 日期: fills 中该 code <=E 的最后一次买入 (full_liquidate 下即本仓起点); 结合 trades entry
            entries = {}
            for code in ever:
                fb = [f[0] for f in fills if f[2] == code and f[0] <= E]
                entries[code] = str(max(fb).date()) if fb else None
            seg[tag] = {"start": str(S.date()), "end": str(E.date()),
                        "n_daysnap": len(days), "hold_start": {c: round(float(s),2) for c, s in sorted(hS.items())},
                        "hold_end": {c: round(float(s),2) for c, s in sorted(hE.items())},
                        "ever": ever, "entries": entries,
                        "contrib": {c: round(float(v),2) for c, v in sorted(contrib.items(), key=lambda x: -abs(x[1]))},
                        "fees_inwin": round(float(fees),2), "dEq": round(float(dEq),2),
                        "recon_err": recon,
                        "switch_inwin": [x for x in res.meta["switch_log"] if str(S.date()) < x[0] <= str(E.date())],
                        "trades_inwin": int(len(tr[(tr.exit_date > S) & (tr.exit_date <= E)])) if len(tr) else 0}
            contribs[tag] = contrib
        codes = sorted(set(contribs["base"]) | set(contribs["g"]))
        dtab = sorted(((c, contribs["g"].get(c,0.0)-contribs["base"].get(c,0.0),
                        contribs["base"].get(c,0.0), contribs["g"].get(c,0.0)) for c in codes),
                      key=lambda x: -abs(x[1]))
        out[w+"_tail"] = {"base": seg["base"], "g": seg["g"],
            "diff_by_code": [{"code": c, "d_contrib": round(float(d),2),
                "base": round(float(b),2), "g": round(float(g_),2)} for c, d, b, g_ in dtab],
            "sum_d_contrib": round(float(sum(x[1] for x in dtab)),2)}
    # 5) 未来函数动静态检查
    import re
    dyn = {}
    for tag, res in (("base", res_b), ("g", res_g)):
        fills = res.meta["fills"]
        bad = [f for f in fills if not (f[1] < f[0])]
        dyn[tag] = {"n_fills": len(fills), "exec_after_sig_violations": len(bad),
                    "sig_gt_exec_sample": bad[:3]}
        # 开关切换 RS 回算抽查: 每个 switch 日的 shadow 索引 <= 信号日
    rs_chk = []
    # 用 g 的 shadow (win_a=30) 对其 switch_log 回算
    inp_a30, inp_b78, ra30, rb78, CAI, CFGB = K.get_shadows(0.78, 30, 0.78, 20, 0.25, 1.2, 0.80, 5, 4, 0.9)
    for sd, mode in res_g.meta["switch_log"]:
        sdt = pd.Timestamp(sd)
        for nm, sh in (("A", ra30.eq), ("B", rb78.eq)):
            j = int(sh.index.searchsorted(sdt, side="right") - 1)
            rs_chk.append({"switch": sd, "shadow": nm, "shadow_date": str(sh.index[j].date()),
                           "le_sig": bool(sh.index[j] <= sdt)})
    stat = {}
    for fn in ["team/audit/prior_check.py", "research/design_r30_grid8.py",
               "research/fresh2_max.py", "research/switch_engine.py"]:
        txt = (ROOT/fn).read_text()
        stat[fn] = {"neg_shift": bool(re.search(r"shift\(\s*-\d", txt)),
                    "loc_future": bool(re.search(r"\b(t\s*\+\s*1|i\s*\+\s*1\s*\+\s*sig)", txt))}
    out["lookahead"] = {"dynamic": dyn, "rs_shadow_le_sig": all(x["le_sig"] for x in rs_chk),
                          "rs_detail": rs_chk, "static": stat}
    # 6) 口径断言
    out["caliber"] = {"run_start": K.RUN_START, "eval_end": str(K.EVAL_END),
        "windows": K.WINDOWS, "slip": SLIP, "eq_len": len(eq_b),
        "same_index": bool(eq_b.index.equals(eq_g.index))}
    (ROOT/"team"/"audit"/"batch_024_m07k9"/"part_k9deep.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1, default=str))
    print(json.dumps({"eval_last": out["eval_last"], "file_recon": chk,
        "w1m": {k: round(float(v),6) for k, v in wins["1m"].items() if isinstance(v, float)},
        "w3m": {k: round(float(v),6) for k, v in wins["3m"].items() if isinstance(v, float)}}, ensure_ascii=False, indent=1))
    for w in ("1m", "3m"):
        t = out[w+"_tail"]
        print(w, "recon_base=%.4f recon_g=%.4f" % (t["base"]["recon_err"], t["g"]["recon_err"]))
        print(w, "topdiff:", json.dumps(t["diff_by_code"][:8], ensure_ascii=False))
    print("saved part_k9deep.json")

if __name__ == "__main__":
    main()
