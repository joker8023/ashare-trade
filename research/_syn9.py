import ast
src=open("research/scan7_5y.py").read()
ast.parse(src)
print("syntax OK")
