import ast
with open('src/henchman/utils/intelligent_context.py', 'r') as f:
    content = f.read()
try:
    ast.parse(content)
    print("Syntax is OK")
except SyntaxError as e:
    print(f"Syntax error: {e}")
    print(f"Line {e.lineno}, column {e.offset}")