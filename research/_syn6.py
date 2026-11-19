import ast
src=open("research/scan4_5y.py").read()
ast.parse(src)
print("syntax OK")
