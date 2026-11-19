import ast
src=open("research/sweep_combo_5y.py").read()
ast.parse(src)
print("syntax OK")
