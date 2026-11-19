import ast
src=open("research/run_3leg19.py").read()
ast.parse(src)
print("syntax OK")
