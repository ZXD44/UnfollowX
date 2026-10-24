# -*- coding: utf-8 -*-
import os
import sys
import subprocess

target = os.path.join(os.path.dirname(os.path.abspath(__file__)), "source_code", "python_engine", "set_version.py")
if os.path.exists(target):
    cmd = [sys.executable, target] + sys.argv[1:]
    res = subprocess.run(cmd)
    sys.exit(res.returncode)
else:
    print(f"Error: Could not locate {target}")
    sys.exit(1)
