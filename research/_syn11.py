import ast
src=open("research/scan9_5y.py").read()
ast.parse(src)
print("syntax OK")
