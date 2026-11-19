import ast
src=open("research/run_3leg11.py").read()
ast.parse(src)
print("syntax OK")
