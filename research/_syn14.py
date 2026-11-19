import ast
src=open("research/scan12_5y.py").read()
ast.parse(src)
print("syntax OK")
