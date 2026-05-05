import subprocess
import sys

msg = sys.argv[1] if len(sys.argv) >= 2 else "..."

subprocess.run(["git", "add", "."], check=True)
subprocess.run(["git", "commit", "-m", msg], check=True)
subprocess.run(["git", "push"], check=True)
