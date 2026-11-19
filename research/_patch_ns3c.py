import re
eng = open("research/switch_engine.py", encoding="utf-8").read()
m = re.search(r"^.*shadow_a=None, shadow_b=None.*$", eng, re.M)
anchor = m.group(0)
assert eng.count(anchor) == 1, eng.count(anchor)
p = "research/switch_ns3.py"
src = open(p, encoding="utf-8").read()
add = "    src = _once(" + repr(anchor) + ", " + repr(anchor) + " + " + repr("\n    shadow_c=None,                          # leg-C shadow") + " + " + repr("\n    inp_c=None,                             # leg-C inputs") + " + " + repr("\n    cfg_c=None,                             # dict(n=, rebal=, take=, exposure)") + ")"
out = []
done = False
for ln in src.split("\n"):
    out.append(ln)
    if (not done) and "stop_c=None" in ln:
        out.append(add)
        done = True
assert done
open(p, "w", encoding="utf-8").write("\n".join(out))
print("patched ok")