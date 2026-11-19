import sys
p = "research/switch_ns3.py"
src = open(p, encoding="utf-8").read()
def rep(old, new):
    global src
    assert src.count(old) == 1, (old[:50], src.count(old))
    src = src.replace(old, new)
# 1. gate -> per-leg table
rep("                    if (_bestv - _mv) >= _HYST:", "                    if (_bestv - _mv) >= {\"A\": _HYST_A, \"B\": _HYST_B, \"C\": _HYST_C}[mode]:")
# 2. signature
rep("def build_ns3(bx=0.18, by_=0.08, bf=0.6, hyst=0.0, min_hold=0, confirm=1):", "def build_ns3(bx=0.18, by_=0.08, bf=0.6, hyst=0.0, min_hold=0, confirm=1, hyst_a=None, hyst_b=None, hyst_c=None):")
# 3a. compute per-leg thresholds after read_text
rep("    src = (ROOT / 'research' / 'switch_engine.py').read_text()\n    def _once(old, new):", "    src = (ROOT / 'research' / 'switch_engine.py').read_text()\n    _HA = hyst if hyst_a is None else hyst_a\n    _HB = hyst if hyst_b is None else hyst_b\n    _HC = hyst if hyst_c is None else hyst_c\n    def _once(old, new):")
# 3b. inject constants (anchor has literal backslash-n in file)
rep("    src = _once(BB, BB + ', _brake, _brake_trough, _brake_peak, _brake_log, _confirm_count, _last_switch_i')", "    src = _once(BB, BB + ', _brake, _brake_trough, _brake_peak, _brake_log, _confirm_count, _last_switch_i')\n    src = _once('    _confirm_count = 0\\n    _last_switch_i = -1000000000', '    _confirm_count = 0\\n    _last_switch_i = -1000000000\\n    _HYST_A = %s\\n    _HYST_B = %s\\n    _HYST_C = %s' % (_HA, _HB, _HC))")
open(p, "w", encoding="utf-8").write(src)
print("patched ok")