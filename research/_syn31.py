import ast
src=open("research/run_3leg10.py").read()
ast.parse(src)
print("syntax OK")
