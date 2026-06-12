import ast, os, sys
errors = []
for root, dirs, files in os.walk("app"):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            try:
                with open(path, encoding="utf-8") as fh:
                    ast.parse(fh.read())
            except SyntaxError as e:
                errors.append(f"{path}: {e}")
if errors:
    print("SYNTAX ERRORS:")
    for e in errors:
        print(" ", e)
    sys.exit(1)
else:
    count = sum(1 for r,d,fs in os.walk("app") for f in fs if f.endswith(".py"))
    print(f"ALL {count} Python files: syntax OK")
