import io
p = "research/switch_ns3.py"
src = open(p, encoding="utf-8").read()
anchor = "    shadow_a=None, shadow_b=None,          # 两引擎独立权益曲线 (RS 信号)"
print("count:", src.count(anchor))
add = anchor + "\n    shadow_c=None,                          # 引擎C影子权益（三腿）\n    inp_c=None,                             # 引擎C输入\n    cfg_c=None,                             # dict(n=, rebal=, take=, exposure)"
assert src.count(anchor) == 1
open(p, "w", encoding="utf-8").write(src.replace(anchor, add))
print("patched")