import ast
src=open("research/run_3leg7.py").read()
ast.parse(src)
print("syntax OK")
