import ast
src=open("research/scan6_mdd.py").read()
ast.parse(src)
print("syntax OK")
