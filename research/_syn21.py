import ast
src=open("research/run_3leg.py").read()
ast.parse(src)
print("syntax OK")
