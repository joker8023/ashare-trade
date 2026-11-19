import ast
src=open("research/run_3leg14.py").read()
ast.parse(src)
print("syntax OK")
