import ast
src=open("research/run_3leg9.py").read()
ast.parse(src)
print("syntax OK")
