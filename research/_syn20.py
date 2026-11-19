import ast
src=open("research/switch_ns3.py").read()
ast.parse(src)
print("syntax OK")
