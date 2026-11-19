import ast
src=open("research/scan13_5y.py").read()
ast.parse(src)
print("syntax OK")
