# -*- coding: utf-8 -*-
"""
UnfollowX - Automated Cooldown Watcher & Non-Followers Finder
Monitors Instagram friendship endpoint cooldown every 10-15 minutes.
When the cooldown expires:
1. Runs full follower vs following diff scan.
2. Identifies exact non-followers (including the 4 accounts).
3. Writes report to NON_FOLLOWERS_FOUND.txt on Desktop and Workspace.
4. Triggers Windows Toast Notification.
"""

import os
import sys
import time
import json
import random
from datetime import datetime
from playwright.sync_api import sync_playwright

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR) if os.path.basename(SCRIPT_DIR) == "scripts" else SCRIPT_DIR
ENGINE_DIR = os.path.join(ROOT_DIR, "source_code", "python_engine")
sys.path.insert(0, ENGINE_DIR)

try:
    from notifier import show_desktop_notification
    from storage_manager import StorageManager
except ImportError:
    show_desktop_notification = None
    StorageManager = None

APPDATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "ZXD44-IG-Cleaner")
PROFILE_DIR = os.path.join(APPDATA_DIR, "browser_profile")
DB_PATH = os.path.join(APPDATA_DIR, "unfollowx.db")
OUTPUT_FILE_WORKSPACE = os.path.join(ROOT_DIR, "NON_FOLLOWERS_FOUND.txt")
DESKTOP_DIR = os.path.join(os.path.expanduser("~"), "Desktop")
OUTPUT_FILE_DESKTOP = os.path.join(DESKTOP_DIR, "NON_FOLLOWERS_FOUND.txt")

CHECK_INTERVAL_SECONDS = 90  # Check every 1.5 minutes (accelerated)


def check_and_scan():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] Checking Instagram friendship endpoint cooldown status...")

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.pages[0] if browser.pages else browser.new_page()

        try:
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
        except Exception as e:
            print(f"[{timestamp}] Failed to load instagram.com: {e}")
            browser.close()
            return False

        cookies = browser.cookies()
        ds = next((c.get("value") for c in cookies if c.get("name") == "ds_user_id"), None)
        csrf = next((c.get("value") for c in cookies if c.get("name") == "csrftoken"), None)

        if not ds:
            print(f"[{timestamp}] No ds_user_id cookie found in session.")
            browser.close()
            return False

        # Test single query to verify if 302 cooldown has ended
        test_script = f"""
        async () => {{
            try {{
                const r = await fetch('/api/v1/friendships/{ds}/following/?count=12', {{
                    credentials: 'include',
                    headers: {{
                        'x-ig-app-id': '936619743392459',
                        'x-requested-with': 'XMLHttpRequest',
                        'accept': '*/*'
                    }}
                }});
                const text = await r.text();
                return {{
                    status: r.status,
                    redirected: r.redirected,
                    is_json: !text.trim().startsWith('<') && !r.redirected && r.status === 200,
                    text: text.slice(0, 300)
                }};
            }} catch (e) {{
                return {{ error: e.message }};
            }}
        }}
        """
        check_res = page.evaluate(test_script)
        print(f"[{timestamp}] Probe result: status={check_res.get('status')}, redirected={check_res.get('redirected')}, is_json={check_res.get('is_json')}")

        if not check_res.get("is_json"):
            print(f"[{timestamp}] ⏳ Cooldown still active from Instagram. Next check in {CHECK_INTERVAL_SECONDS} seconds.")
            browser.close()
            return False

        print(f"[{timestamp}] 🎉 COOLDOWN CLEARED! Running full list scan...")

        # Cooldown cleared! Execute full scan
        full_scan_script = f"""
        async () => {{
            const ds = '{ds}';
            const grab = async (ep) => {{
                let all = [], mx = null;
                for (let i = 0; i < 200; i++) {{
                    const queryParam = (ep === 'followers') ? 'count=20&search_surface=follow_list_page' : 'count=20';
                    const u = `/api/v1/friendships/${{ds}}/${{ep}}/?${{queryParam}}` + (mx ? `&max_id=${{encodeURIComponent(mx)}}` : '');
                    const r = await fetch(u, {{
                        credentials: 'include',
                        headers: {{
                            'x-ig-app-id': '936619743392459',
                            'x-requested-with': 'XMLHttpRequest',
                            'accept': '*/*'
                        }}
                    }});
                    const text = await r.text();
                    if (!text || text.trim().startsWith('<') || r.redirected) break;
                    let j;
                    try {{ j = JSON.parse(text); }} catch (e) {{ break; }}
                    if (j.users && j.users.length) all.push(...j.users);
                    if (!j.next_max_id) break;
                    mx = j.next_max_id;
                    await new Promise(res => setTimeout(res, 350 + Math.random() * 250));
                }}
                return all;
            }};

            const following = await grab('following');
            await new Promise(res => setTimeout(res, 600));
            const followers = await grab('followers');

            const fSet = new Set(followers.map(u => String(u.pk || u.id)));
            const nonFollowers = following.filter(u => !fSet.has(String(u.pk || u.id)));

            return {{
                following_count: following.length,
                followers_count: followers.length,
                non_followers: nonFollowers.map(u => ({{
                    id: String(u.pk || u.id),
                    username: u.username,
                    full_name: u.full_name || '',
                    profile_pic_url: u.profile_pic_url || '',
                    is_verified: !!u.is_verified,
                    is_private: !!u.is_private
                }})),
                following: following,
                followers: followers
            }};
        }}
        """
        scan_data = page.evaluate(full_scan_script)
        browser.close()

        non_followers = scan_data.get("non_followers", [])
        following_cnt = scan_data.get("following_count", 0)
        followers_cnt = scan_data.get("followers_count", 0)

        print(f"[{timestamp}] Scan Complete! Following: {following_cnt}, Followers: {followers_cnt}")
        print(f"[{timestamp}] Found {len(non_followers)} accounts who do NOT follow back!")

        # Format report
        report_lines = [
            "=" * 60,
            f"   UnfollowX — รายชื่อผู้ที่ไม่ติดตามกลับ (Non-Followers)",
            f"   เวลาที่สแกนสำเร็จ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"   กำลังติดตาม (Following): {following_cnt} คน",
            f"   ผู้ติดตาม (Followers): {followers_cnt} คน",
            f"   ผลต่าง (ไม่ฟอลกลับ): {len(non_followers)} คน",
            "=" * 60,
            "",
            "รายชื่อสำหรับเปิดกดยกเลิกการติดตามด้วยตนเอง:",
            ""
        ]

        for i, u in enumerate(non_followers, 1):
            uname = u.get("username")
            fname = u.get("full_name") or "-"
            report_lines.append(f"{i}. @{uname} ({fname})")
            report_lines.append(f"   Link: https://www.instagram.com/{uname}/")
            report_lines.append("")

        report_lines.append("=" * 60)
        report_lines.append("คุณสามารถเปิดโปรไฟล์ตาม Link ด้านบนเพื่อกดยกเลิกการติดตามด้วยตนเองได้ทันที")
        report_text = "\n".join(report_lines)

        # Write to files
        try:
            with open(OUTPUT_FILE_WORKSPACE, "w", encoding="utf-8") as f:
                f.write(report_text)
            print(f"Saved: {OUTPUT_FILE_WORKSPACE}")
        except Exception as e:
            print(f"Error writing workspace report: {e}")

        try:
            with open(OUTPUT_FILE_DESKTOP, "w", encoding="utf-8") as f:
                f.write(report_text)
            print(f"Saved: {OUTPUT_FILE_DESKTOP}")
        except Exception as e:
            pass

        # Save snapshots in SQLite
        if StorageManager and os.path.exists(DB_PATH):
            try:
                storage = StorageManager(DB_PATH)
                storage.save_scan_snapshot("followers", scan_data.get("followers", []))
                storage.save_scan_snapshot("following", scan_data.get("following", []))
                print("Saved snapshot into SQLite DB.")
            except Exception as e:
                print(f"Error saving DB: {e}")

        # Desktop notification
        if show_desktop_notification:
            show_desktop_notification(
                "UnfollowX — สแกนรายชื่อสำเร็จ!",
                f"Instagram Cooldown หมดแล้ว! พบ {len(non_followers)} คนที่ไม่ฟอลกลับ ดูได้ที่หน้าจอ Desktop"
            )

        return True


def run_watcher(single_run=False):
    print("=" * 60)
    print("  UnfollowX Cooldown Monitor & Non-Followers Watcher")
    print(f"  Target: %LOCALAPPDATA%\\ZXD44-IG-Cleaner")
    print(f"  Check Interval: {CHECK_INTERVAL_SECONDS // 60} Minutes")
    print("=" * 60)

    while True:
        try:
            done = check_and_scan()
            if done or single_run:
                break
        except Exception as e:
            print(f"Watcher loop error: {e}")

        time.sleep(CHECK_INTERVAL_SECONDS + random.randint(-30, 30))


if __name__ == "__main__":
    is_single = "--check-now" in sys.argv
    run_watcher(single_run=is_single)
