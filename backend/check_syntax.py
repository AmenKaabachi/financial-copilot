import ast

files = [
    "backend/app/services/llm/prompts.py",
    "backend/app/services/llm/manager.py",
]

for path in files:
    try:
        with open(path, encoding="utf-8") as f:
            ast.parse(f.read())
        print(f"{path}: OK")
    except SyntaxError as e:
        print(f"{path}: SYNTAX ERROR - {e}")
        raise