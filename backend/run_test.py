import subprocess, sys
result = subprocess.run(
    [sys.executable, "test_rag_e2e.py"],
    capture_output=True, text=True, cwd=".", timeout=120
)
# Print only the key lines
for line in (result.stdout + result.stderr).splitlines():
    skip = any(x in line for x in [
        "sqlalchemy.engine", "INFO  [sql", "generated in", "raw sql",
        "Loading weights", "BertModel", "UNEXPECTED", "LOAD REPORT",
        "Key ", "Status ", "Notes", "--------", "embeddings.position",
        "Warning: You", "CategoryInfo", "FullyQualified", "NativeCommand",
        "RemoteException", "BEGIN (implicit)", "COMMIT", "ROLLBACK",
        "SELECT ", "INSERT ", "UPDATE knowledge_chunks SET embedding",
        "FROM ", "WHERE ", "LIMIT ", "RETURNING", "ORDER BY",
    ])
    if not skip:
        print(line)
