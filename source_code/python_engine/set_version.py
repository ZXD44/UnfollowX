# -*- coding: utf-8 -*-
"""
UnfollowX Version Manager & Build Automation Tool
Single command to update version across all files, compile EXE, and publish GitHub Release.

Usage:
    python set_version.py 0.0.2
    python set_version.py 0.0.2 --build
    python set_version.py 0.0.2 --build --release
"""

import sys
import os
import re
import json
import subprocess
import shutil
import urllib.request
import urllib.error

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(ENGINE_DIR, "..", ".."))

VERSION_PY = os.path.join(ENGINE_DIR, "version.py")
VERSION_INFO_TXT = os.path.join(ENGINE_DIR, "version_info.txt")
HOW_TO_USE_TXT = os.path.join(ROOT_DIR, "HOW_TO_USE.txt")
AGENT_README = os.path.join(ROOT_DIR, ".agent", "README.md")
SPEC_FILE = os.path.join(ENGINE_DIR, "build_gui_exe.spec")
DIST_EXE = os.path.join(ENGINE_DIR, "dist", "UnfollowX.exe")
ROOT_EXE = os.path.join(ROOT_DIR, "UnfollowX.exe")
GITHUB_REPO = "ZXD44/UnfollowX"


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
            StringStruct('CompanyName', 'ZXD44'),
            StringStruct('FileDescription', 'UnfollowX PRO — Automatic Instagram Cleaner'),
            StringStruct('FileVersion', '{file_ver_str}'),
            StringStruct('InternalName', 'UnfollowX'),
            StringStruct('LegalCopyright', 'Copyright © 2026 ZXD44. All rights reserved.'),
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
        # Clean build artifacts
        shutil.rmtree(os.path.join(ENGINE_DIR, "build"), ignore_errors=True)
        shutil.rmtree(os.path.join(ENGINE_DIR, "dist"), ignore_errors=True)
        return True
    else:
        print(f"  [✗] Build failed with return code {res.returncode}")
        return False


def publish_github_release(ver_str):
    print(f"\n[*] Starting GitHub Release deployment for v{ver_str}...")

    # 1. Commit and push
    subprocess.run(["git", "add", "."], cwd=ROOT_DIR)
    commit_res = subprocess.run(["git", "commit", "-m", f"chore: bump version to v{ver_str}"], cwd=ROOT_DIR)
    
    tag_name = f"v{ver_str}"
    subprocess.run(["git", "tag", "-a", tag_name, "-m", f"UnfollowX PRO {tag_name}"], cwd=ROOT_DIR)
    subprocess.run(["git", "push", "origin", "main", "--tags"], cwd=ROOT_DIR)
    print("  [✓] Git commit and tag pushed to GitHub.")

    # 2. Get GitHub token from Credential Manager
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n",
        text=True,
        capture_output=True,
        cwd=ROOT_DIR
    )
    token = None
    for line in proc.stdout.splitlines():
        if line.startswith("password="):
            token = line.split("=", 1)[1].strip()
            break

    if not token:
        print("  [✗] Could not retrieve GitHub token. Skipping API upload.")
        return

    # 3. Create or Update Release via GitHub API
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ZXD44-Release-Agent"
    }

    release_title = f"UnfollowX PRO v{ver_str} — Release"
    release_body = f"""# 🚀 UnfollowX PRO v{ver_str}

## 🇹🇭 ไฮไลท์การอัปเดต (Release Highlights)
* 🌐 **Bilingual System**: รองรับทั้งภาษาไทย (หลัก) และภาษาอังกฤษ สลับได้ทันทีบนหน้าจอ
* ⚡ **Live Telemetry**: แสดงหลอดความคืบหน้าการสแกนแบบเรียลไทม์ `0% - 100%`
* 🛡️ **Zero Freeze Guarantee**: สถาปัตยกรรมไร้ Deadlock 100% ไม่ค้าง ไม่ติด Not Responding
* 📌 **Always-on-Top & Audio**: โหมดปักหมุดหน้าต่างบนสุด และเสียงสังเคราะห์แจ้งเตือน
* 🛡️ **Whitelist & Audit History**: ปกป้องเพื่อนสำคัญ และบันทึกประวัติการเลิกติดตาม

## 🇬🇧 English Overview
* 🌐 **Dual Language**: Seamless toggle between Thai (Default) and English.
* ⚡ **Real-Time Progress**: Live scan streaming from browser context.
* 🛡️ **Safety Guardrails**: Real browser sessions, zero password logging, and spam-prevention cooldowns.

## 📦 การติดตั้งและดาวน์โหลด (Downloads)
1. ดาวน์โหลดไฟล์ **`UnfollowX.exe`** ด้านล่างนี้ในส่วน Assets
2. ดับเบิลคลิกเปิดไฟล์ใช้งานได้ทันที (ไม่ต้องติดตั้งโปรแกรมเสริม)

---
Developed with ❤️ by **[ZXD44](https://github.com/ZXD44)**
"""

    check_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/{tag_name}"
    req = urllib.request.Request(check_url, headers=headers)
    release_id = None
    upload_url = None

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            release_id = data["id"]
            upload_url = data["upload_url"].split("{")[0]
            print(f"  [✓] Existing release found (ID: {release_id}). Updating...")
            patch_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/{release_id}"
            patch_body = json.dumps({"name": release_title, "body": release_body}).encode("utf-8")
            patch_req = urllib.request.Request(patch_url, data=patch_body, headers={**headers, "Content-Type": "application/json"}, method="PATCH")
            urllib.request.urlopen(patch_req)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"  [✓] Creating new GitHub release for {tag_name}...")
            create_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
            create_body = json.dumps({
                "tag_name": tag_name,
                "name": release_title,
                "body": release_body,
                "draft": False,
                "prerelease": False
            }).encode("utf-8")
            create_req = urllib.request.Request(create_url, data=create_body, headers={**headers, "Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(create_req) as resp:
                data = json.loads(resp.read().decode())
                release_id = data["id"]
                upload_url = data["upload_url"].split("{")[0]
        else:
            print(f"  [✗] GitHub API Error: {e}")
            return

    # 4. Upload UnfollowX.exe binary asset
    if not os.path.exists(ROOT_EXE):
        print(f"  [✗] Binary {ROOT_EXE} not found. Skipping asset upload.")
        return

    print(f"  [*] Uploading UnfollowX.exe asset ({os.path.getsize(ROOT_EXE) / (1024*1024):.2f} MB)...")
    # Delete existing asset if any
    list_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/{release_id}/assets"
    req = urllib.request.Request(list_url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        assets = json.loads(resp.read().decode())
        for a in assets:
            if a["name"] == "UnfollowX.exe":
                del_req = urllib.request.Request(f"https://api.github.com/repos/{GITHUB_REPO}/releases/assets/{a['id']}", headers=headers, method="DELETE")
                urllib.request.urlopen(del_req)
                break

    upload_endpoint = f"{upload_url}?name=UnfollowX.exe"
    with open(ROOT_EXE, "rb") as f:
        exe_bytes = f.read()

    upload_headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/octet-stream",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ZXD44-Release-Agent"
    }
    upload_req = urllib.request.Request(upload_endpoint, data=exe_bytes, headers=upload_headers, method="POST")
    with urllib.request.urlopen(upload_req) as resp:
        res_data = json.loads(resp.read().decode())
        print(f"  [✓] Binary uploaded successfully!")
        print(f"  [✓] Direct download: {res_data.get('browser_download_url')}")

    print(f"\n[🎉] Release {tag_name} is published live on GitHub!")
    print(f"     https://github.com/{GITHUB_REPO}/releases/tag/{tag_name}")


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
        print(f"  UnfollowX PRO Version & Release Manager")
        print(f"  Current Version: {current}")
        print("=" * 60)
        print("Usage:")
        print("  python set_version.py <new_version> [--build] [--release]")
        print("Example:")
        print("  python set_version.py 0.0.2")
        print("  python set_version.py 0.0.2 --build")
        print("  python set_version.py 0.0.2 --build --release")
        sys.exit(0)

    new_version = sys.argv[1].strip().lstrip("v")
    do_build = "--build" in sys.argv
    do_release = "--release" in sys.argv

    print(f"\n[+] Setting UnfollowX version to: {new_version}")
    update_version_py(new_version)
    update_version_info(new_version)
    update_how_to_use(new_version)
    update_agent_docs(new_version)

    print(f"\n[✓] Version synchronization complete -> {new_version}")

    built_ok = True
    if do_build or do_release:
        built_ok = run_build()

    if do_release and built_ok:
        publish_github_release(new_version)


if __name__ == "__main__":
    main()
