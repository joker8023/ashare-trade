import ast
src=open("research/run_3leg5.py").read()
ast.parse(src)
print("syntax OK")
