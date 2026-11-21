# -*- coding: utf-8 -*-
"""
UnfollowX - Instant Instagram Data Export Diff Tool
Instantly extracts and compares followers vs following from Instagram JSON data export.
Bypasses all API cooldowns and rate limits with 100% accuracy.
"""

import os
import sys
import json
import zipfile
import sqlite3
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR) if os.path.basename(SCRIPT_DIR) == "scripts" else SCRIPT_DIR
APPDATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "ZXD44-IG-Cleaner")
DB_PATH = os.path.join(APPDATA_DIR, "unfollowx.db")
DESKTOP_DIR = os.path.join(os.path.expanduser("~"), "Desktop")
OUTPUT_TXT_DESKTOP = os.path.join(DESKTOP_DIR, "NON_FOLLOWERS_FOUND.txt")
OUTPUT_TXT_WORKSPACE = os.path.join(ROOT_DIR, "NON_FOLLOWERS_FOUND.txt")


def parse_usernames(data):
    usernames = set()
    if isinstance(data, dict):
        if "relationships_following" in data:
            data = data["relationships_following"]
        elif "relationships_followers" in data:
            data = data["relationships_followers"]

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                string_list = item.get("string_list_data", [])
                if string_list and isinstance(string_list, list):
                    for s in string_list:
                        val = s.get("value")
                        if val:
                            usernames.add(val.strip().lower())
                else:
                    val = item.get("value") or item.get("title")
                    if val:
                        usernames.add(val.strip().lower())
    return usernames


def diff_files(followers_path, following_path):
    print(f"Reading followers from: {followers_path}")
    with open(followers_path, "r", encoding="utf-8") as f:
        followers_data = json.load(f)
    followers = parse_usernames(followers_data)

    print(f"Reading following from: {following_path}")
    with open(following_path, "r", encoding="utf-8") as f:
        following_data = json.load(f)
    following = parse_usernames(following_data)

    non_followers = sorted(list(following - followers))
    print(f"\nTotal Following: {len(following)}")
    print(f"Total Followers: {len(followers)}")
    print(f"Non-Followers Found: {len(non_followers)}\n")

    return non_followers


def diff_zip(zip_path):
    print(f"Inspecting ZIP file: {zip_path}")
    with zipfile.ZipFile(zip_path, "r") as z:
        namelist = z.namelist()
        following_file = next((n for n in namelist if "following" in n.lower() and n.endswith(".json")), None)
        followers_file = next((n for n in namelist if "follower" in n.lower() and n.endswith(".json")), None)

        if not following_file or not followers_file:
            print("Could not find following/followers JSON in zip!")
            print("Files found in zip:", namelist[:15])
            return []

        with z.open(following_file) as f:
            following_data = json.load(f)
        with z.open(followers_file) as f:
            followers_data = json.load(f)

        following = parse_usernames(following_data)
        followers = parse_usernames(followers_data)
        return sorted(list(following - followers))


def save_results(non_followers):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = f"""============================================================
  UnfollowX - Non-Followers Report (Instant Diff)
  Generated: {timestamp}
  Total Non-Followers to Unfollow: {len(non_followers)}
============================================================

รายชื่อบัญชีที่คุณกำลังติดตาม แต่เขาไม่ได้ติดตามคุณกลับ:
"""
    for i, uname in enumerate(non_followers, 1):
        report += f"{i}. @{uname}\n   https://www.instagram.com/{uname}/\n\n"

    report += """------------------------------------------------------------
วิธีดำเนินการ:
1. เปิดโปรแกรม UnfollowX (v0.0.9)
2. คลิกปุ่ม "➕ เพิ่มชื่อเอง (Manual)" หรือ "📝 ข้ามไปจัดการรายชื่อเอง"
3. กดยกเลิกติดตาม หรือคลิก "🌐 ดูโปรไฟล์" เพื่อเปิด Chrome จัดการทีละบัญชี
============================================================
"""
    with open(OUTPUT_TXT_DESKTOP, "w", encoding="utf-8") as f:
        f.write(report)
    with open(OUTPUT_TXT_WORKSPACE, "w", encoding="utf-8") as f:
        f.write(report)

    # Sync to SQLite unfollow_queue
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        for uname in non_followers:
            c.execute(
                "INSERT OR IGNORE INTO unfollow_queue (id, username, status) VALUES (?, ?, 'pending')",
                (uname, uname)
            )
        conn.commit()
        conn.close()
        print(f"Synced {len(non_followers)} targets into UnfollowX database queue.")
    except Exception as e:
        print(f"Warning: Failed to sync with SQLite: {e}")

    print(f"\n[DONE] Saved report to Desktop: {OUTPUT_TXT_DESKTOP}")
    print(f"[DONE] Saved report to Workspace: {OUTPUT_TXT_WORKSPACE}\n")
    for i, u in enumerate(non_followers, 1):
        print(f"  {i}. @{u} (https://www.instagram.com/{u}/)")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1]
        if target.endswith(".zip"):
            res = diff_zip(target)
            save_results(res)
        elif len(sys.argv) > 2:
            res = diff_files(sys.argv[1], sys.argv[2])
            save_results(res)
        elif os.path.isdir(target):
            # Search directory
            f_following = None
            f_followers = None
            for root, _, files in os.walk(target):
                for f in files:
                    if "following" in f.lower() and f.endswith(".json"):
                        f_following = os.path.join(root, f)
                    if "follower" in f.lower() and f.endswith(".json"):
                        f_followers = os.path.join(root, f)
            if f_following and f_followers:
                res = diff_files(f_followers, f_following)
                save_results(res)
            else:
                print("Could not find following.json and followers_1.json in folder.")
    else:
        print("Usage:")
        print("  python instant_diff.py <export.zip>")
        print("  python instant_diff.py <followers_1.json> <following.json>")
        print("  python instant_diff.py <extracted_folder>")
