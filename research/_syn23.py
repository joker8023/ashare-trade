import ast
src=open("research/run_3leg3.py").read()
ast.parse(src)
print("syntax OK")
