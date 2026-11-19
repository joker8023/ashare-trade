import ast
src=open("research/scan5_5y.py").read()
ast.parse(src)
print("syntax OK")
