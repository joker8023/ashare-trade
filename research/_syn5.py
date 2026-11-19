import ast
src=open("research/scan3_5y.py").read()
ast.parse(src)
print("syntax OK")
