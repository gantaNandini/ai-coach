"""Run tests and show summary."""
import subprocess, sys
result = subprocess.run(
    [sys.executable, "-m", "pytest",
     "tests/test_auth_flow.py", "tests/test_rag_pipeline.py",
     "-v", "--tb=short", "-q"],
    capture_output=True, text=True, cwd=".", timeout=180
)
output = result.stdout + result.stderr
# Show last 60 lines
lines = output.splitlines()
for line in lines[-60:]:
    print(line)
print("\nExit code:", result.returncode)
