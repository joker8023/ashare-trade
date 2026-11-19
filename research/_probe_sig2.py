lines = open("research/switch_engine.py", encoding="utf-8").read().split("\n")
for i, t in enumerate(lines):
    if "shadow_a=None" in t:
        print(i+1, repr(t))
