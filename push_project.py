import subprocess
import sys

msg = sys.argv[1] if len(sys.argv) == 2 else "Auto Submit"

cmd1 = "git add ."
cmd2 = 'git commit -m "{}"'.format(msg)
cmd3 = "git push"

subprocess.run(cmd1, shell=False    , check=True)
subprocess.run(cmd2, shell=True)
subprocess.run(cmd3, shell=True)
