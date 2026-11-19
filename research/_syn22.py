import ast
src=open("research/run_3leg2.py").read()
ast.parse(src)
print("syntax OK")
