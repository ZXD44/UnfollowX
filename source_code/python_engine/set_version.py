# -*- coding: utf-8 -*-
"""
UnfollowX Version Manager & Build Automation Tool
Single command to update version across all files and compile EXE.

Usage:
    python set_version.py 0.0.2
    python set_version.py 0.0.2 --build
"""

import sys
import os
import re
import subprocess
import shutil

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(ENGINE_DIR, "..", ".."))

VERSION_PY = os.path.join(ENGINE_DIR, "version.py")
VERSION_INFO_TXT = os.path.join(ENGINE_DIR, "version_info.txt")
HOW_TO_USE_TXT = os.path.join(ROOT_DIR, "HOW_TO_USE.txt")
AGENT_README = os.path.join(ROOT_DIR, ".agent", "README.md")
SPEC_FILE = os.path.join(ENGINE_DIR, "build_gui_exe.spec")
DIST_EXE = os.path.join(ENGINE_DIR, "dist", "UnfollowX.exe")
ROOT_EXE = os.path.join(ROOT_DIR, "UnfollowX.exe")


def parse_version_tuple(ver_str):
    parts = ver_str.strip().split(".")
    nums = []
    for p in parts:
        clean = re.sub(r"\D", "", p)
        nums.append(int(clean) if clean else 0)
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums[:4])


def update_version_py(ver_str):
    if not os.path.exists(VERSION_PY):
        return
    with open(VERSION_PY, "r", encoding="utf-8") as f:
        content = f.read()
    new_content = re.sub(r'VERSION\s*=\s*["\'][^"\']+["\']', f'VERSION = "{ver_str}"', content)
    with open(VERSION_PY, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"  [✓] Updated: {VERSION_PY}")


def update_version_info(ver_str):
    quad = parse_version_tuple(ver_str)
    file_ver_str = f"{quad[0]}.{quad[1]}.{quad[2]}.{quad[3]}"
    
    content = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={quad},
    prodvers={quad},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', 'ZirconX'),
            StringStruct('FileDescription', 'UnfollowX PRO — Automatic Instagram Cleaner'),
            StringStruct('FileVersion', '{file_ver_str}'),
            StringStruct('InternalName', 'UnfollowX'),
            StringStruct('LegalCopyright', 'Copyright © 2026 ZirconX. All rights reserved.'),
            StringStruct('OriginalFilename', 'UnfollowX.exe'),
            StringStruct('ProductName', 'UnfollowX PRO'),
            StringStruct('ProductVersion', '{ver_str}')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    with open(VERSION_INFO_TXT, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [✓] Updated: {VERSION_INFO_TXT}")


def update_how_to_use(ver_str):
    if not os.path.exists(HOW_TO_USE_TXT):
        return
    with open(HOW_TO_USE_TXT, "r", encoding="utf-8") as f:
        content = f.read()
    new_content = re.sub(r'UnfollowX PRO v\d+\.\d+\.\d+', f'UnfollowX PRO v{ver_str}', content)
    with open(HOW_TO_USE_TXT, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"  [✓] Updated: {HOW_TO_USE_TXT}")


def update_agent_docs(ver_str):
    if not os.path.exists(AGENT_README):
        return
    with open(AGENT_README, "r", encoding="utf-8") as f:
        content = f.read()
    new_content = re.sub(r'UnfollowX PRO v\d+\.\d+\.\d+', f'UnfollowX PRO v{ver_str}', content)
    with open(AGENT_README, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"  [✓] Updated: {AGENT_README}")


def run_build():
    print(f"\n[*] Starting PyInstaller build...")
    cmd = [sys.executable, "-m", "PyInstaller", SPEC_FILE, "--noconfirm"]
    res = subprocess.run(cmd, cwd=ENGINE_DIR)
    if res.returncode == 0:
        print("  [✓] PyInstaller build successful!")
        if os.path.exists(DIST_EXE):
            shutil.copy2(DIST_EXE, ROOT_EXE)
            print(f"  [✓] Deployed standalone EXE to: {ROOT_EXE}")
    else:
        print(f"  [✗] Build failed with return code {res.returncode}")


def main():
    if ENGINE_DIR not in sys.path:
        sys.path.insert(0, ENGINE_DIR)
    if len(sys.argv) < 2:
        try:
            import version
            current = version.VERSION
        except Exception:
            current = "Unknown"
        print("=" * 60)
        print(f"  UnfollowX PRO Version Manager")
        print(f"  Current Version: {current}")
        print("=" * 60)
        print("Usage:")
        print("  python set_version.py <new_version> [--build]")
        print("Example:")
        print("  python set_version.py 0.0.2")
        print("  python set_version.py 0.0.2 --build")
        sys.exit(0)

    new_version = sys.argv[1].strip().lstrip("v")
    do_build = "--build" in sys.argv

    print(f"\n[+] Setting UnfollowX version to: {new_version}")
    update_version_py(new_version)
    update_version_info(new_version)
    update_how_to_use(new_version)
    update_agent_docs(new_version)

    print(f"\n[✓] Version synchronization complete -> {new_version}")

    if do_build:
        run_build()


if __name__ == "__main__":
    main()
