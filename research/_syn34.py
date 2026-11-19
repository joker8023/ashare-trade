import ast
src=open("research/run_3leg13.py").read()
ast.parse(src)
print("syntax OK")
