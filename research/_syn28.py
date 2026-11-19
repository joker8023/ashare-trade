import ast
src=open("research/run_3leg8.py").read()
ast.parse(src)
print("syntax OK")
