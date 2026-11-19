import ast
src=open("research/run_3leg20.py").read()
ast.parse(src)
print("syntax OK")
