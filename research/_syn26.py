import ast
src=open("research/run_3leg6.py").read()
ast.parse(src)
print("syntax OK")
