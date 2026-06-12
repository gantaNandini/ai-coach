import ast, os, sys
errors = []
for root, dirs, files in os.walk("app"):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            try:
                ast.parse(open(path, encoding="utf-8").read())
            except SyntaxError as e:
                errors.append(f"{path}: {e}")
if errors:
    for e in errors: print("ERROR:", e)
    sys.exit(1)
else:
    print("ALL PYTHON FILES: OK")
