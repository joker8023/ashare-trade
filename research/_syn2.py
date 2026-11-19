import ast
src=open("research/scan_22_leg.py").read()
ast.parse(src)
print("syntax OK")
