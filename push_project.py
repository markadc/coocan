import os
import sys

msg = sys.argv[1] if len(sys.argv) == 2 else "修复一些BUG"

cmd1 = "git add ."
cmd2 = 'git commit -m "{}"'.format(msg)
cmd3 = "git push"

os.system(cmd1)
os.system(cmd2)
os.system(cmd3)
