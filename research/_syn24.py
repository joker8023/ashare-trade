import ast
src=open("research/run_3leg4.py").read()
ast.parse(src)
print("syntax OK")
