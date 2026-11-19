import ast
src=open("research/scan14_5y.py").read()
ast.parse(src)
print("syntax OK")
