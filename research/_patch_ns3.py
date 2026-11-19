import io
p = "research/switch_ns3.py"
src = open(p, encoding="utf-8").read()
anchor = "    shadow_a=None, shadow_b=None,          # \u4e24\u5f15\u64ce\u72ec\u7acb\u6743\u76ca\u66f2\u7ebf (RS \u4fe1\u53f7)"
assert src.count(anchor) == 1, src.count(anchor)
add = anchor + "\n    shadow_c=None,                          # \u5f15\u64ce C \u7684\u5f71\u5b50\u6743\u76ca (\u4e09\u817f)\n    inp_c=None,                             # \u5f15\u64ce C \u7684 Inputs\n    cfg_c=None,                             # dict(n=, rebal=, take=, exposure)"
open(p, "w", encoding="utf-8").write(src.replace(anchor, add))
print("patched")
