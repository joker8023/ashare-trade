import sys
p = "research/switch_ns3.py"
src = open(p, encoding="utf-8").read()
def rep(old, new, cnt=1):
    global src
    assert src.count(old) == cnt, (old[:60], src.count(old))
    src = src.replace(old, new)
# 1. signature
rep("def build_ns3(bx=0.18, by_=0.08, bf=0.6, hyst=0.0, min_hold=0, confirm=1, hyst_a=None, hyst_b=None, hyst_c=None):", "def build_ns3(bx=0.18, by_=0.08, bf=0.6, hyst=0.0, min_hold=0, confirm=1, hyst_a=None, hyst_b=None, hyst_c=None, rs_decay_hl=None):")
# 2. constants + decay-RS fn before board_limit
anchor2 = "    def board_limit(code: str) -> float:"
block2 = "    _RS_HL = HLVAL\n    _USE_DECAY = USEDEC\n    def _rs_w(eq_s, s_idx):\n        if eq_s is None:\n            return None\n        j = int(eq_s.index.searchsorted(dates[s_idx], side=\"right\") - 1)\n        if j < rs_lookback:\n            return None\n        _rr = eq_s.pct_change().iloc[j - rs_lookback + 1:j + 1]\n        _wsum = 0.0\n        _acc = 0.0\n        for _k, _rv in enumerate(_rr.fillna(0.0)):\n            _w = 0.5 ** ((rs_lookback - 1 - _k) / _RS_HL)\n            _acc += _w * float(_rv)\n            _wsum += _w\n        if _wsum <= 0:\n            return None\n        return float(_acc / _wsum * rs_lookback)\n"
rep(anchor2, block2 + anchor2)
# 3. use decay RS in 3-way branch
old3 = "            ra = _rs(shadow_a, sig_i)\n            rb = _rs(shadow_b, sig_i)\n            rc = _rs(shadow_c, sig_i) if shadow_c is not None else None"
new3 = "            if _USE_DECAY:\n                ra = _rs_w(shadow_a, sig_i)\n                rb = _rs_w(shadow_b, sig_i)\n                rc = _rs_w(shadow_c, sig_i) if shadow_c is not None else None\n            else:\n                ra = _rs(shadow_a, sig_i)\n                rb = _rs(shadow_b, sig_i)\n                rc = _rs(shadow_c, sig_i) if shadow_c is not None else None"
rep(old3, new3)
open(p, "w", encoding="utf-8").write(src)
print("decay patch ok")