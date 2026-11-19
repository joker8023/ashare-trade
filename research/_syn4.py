import ast
src=open("research/scan2_5y.py").read()
ast.parse(src)
print("syntax OK")
