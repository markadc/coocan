import os
import sys

msg = sys.argv[1] if len(sys.argv) == 2 else "支持代理；加入默认超时6秒；优化代码"

cmd1 = "git add ."
cmd2 = 'git commit -m "{}"'.format(msg)
cmd3 = "git push"

os.system(cmd1)
os.system(cmd2)
os.system(cmd3)
