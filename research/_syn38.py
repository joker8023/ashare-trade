import ast
src=open("research/run_3leg18.py").read()
ast.parse(src)
print("syntax OK")
