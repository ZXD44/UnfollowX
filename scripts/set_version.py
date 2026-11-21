# -*- coding: utf-8 -*-
import os
import sys
import subprocess

base = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(base) if os.path.basename(base) == "scripts" else base
target = os.path.join(root, "source_code", "python_engine", "set_version.py")
if os.path.exists(target):
    cmd = [sys.executable, target] + sys.argv[1:]
    res = subprocess.run(cmd)
    sys.exit(res.returncode)
else:
    print(f"Error: Could not locate {target}")
    sys.exit(1)
