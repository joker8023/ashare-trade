import ast
src=open("research/run_3leg16.py").read()
ast.parse(src)
print("syntax OK")
