import os
import sys
import json
import time
import random
import atexit
import csv
import queue
import threading
import io
import webview
from playwright.sync_api import sync_playwright

# Redirect stdout/stderr to avoid NoneType attribute errors when frozen with console=False
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

try:
    from version import VERSION, APP_NAME, AUTHOR
except ImportError:
    VERSION = "0.0.1"
    APP_NAME = "UnfollowX PRO"
    AUTHOR = "ZXD44"

APP_VERSION = VERSION
APP_TITLE = f"{APP_NAME} v{APP_VERSION} — By {AUTHOR}"

# 1. Base and Profile Paths
APPDATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "ZXD44-IG-Cleaner")
PROFILE_DIR = os.path.join(APPDATA_DIR, "browser_profile")
os.makedirs(PROFILE_DIR, exist_ok=True)

if getattr(sys, "frozen", False):
    RESOURCE_DIR = sys._MEIPASS
    BASE_DIR = os.path.dirname(sys.executable)
else:
    RESOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = RESOURCE_DIR

HTML_PATH = os.path.join(RESOURCE_DIR, "gui_template.html")


def find_chrome():
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


class BrowserWorker:
    """
    Dedicated Worker for Playwright.
    Pure background thread: NEVER calls evaluate_js() directly!
    Communicates strictly via Thread-Safe State updates on API object.
    """
    def __init__(self, api_ref):
        self.api = api_ref
        self.q = queue.Queue()
        self.pw = None
        self.browser = None
        self.page = None
        self.running = True
        self.is_ready = False
        self.abort_flag = False
        self.thread = threading.Thread(target=self._run_loop, name="PlaywrightWorker", daemon=True)
        self.thread.start()

    def _init_browser(self):
        try:
            if not self.pw:
                self.pw = sync_playwright().start()

            chrome_exe = find_chrome()
            kwargs = dict(
                user_data_dir=PROFILE_DIR,
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
                no_viewport=True,
            )
            if chrome_exe:
                kwargs["executable_path"] = chrome_exe

            self.browser = self.pw.chromium.launch_persistent_context(**kwargs)
            self.page = self.browser.pages[0] if self.browser.pages else self.browser.new_page()

            try:
                if "instagram.com" not in self.page.url:
                    self.page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass

            self.is_ready = True
            self.api.update_state(browser_ready=True, error=None)
        except Exception as e:
            self.is_ready = False
            self.api.update_state(browser_ready=False, error=str(e))

    def _run_loop(self):
        self._init_browser()
        last_cookie_check = 0

        while self.running:
            # 1. Process queued task if any
            try:
                task = self.q.get(timeout=0.4)
                func, args = task
                if func is None:
                    break
                try:
                    if not self.is_ready or not self.browser:
                        self._init_browser()

                    if self.browser:
                        if not self.page or self.page.is_closed():
                            self.page = self.browser.pages[0] if self.browser.pages else self.browser.new_page()

                    func(self, *args)
                except Exception as e:
                    self.api.update_state(error=str(e))
                continue
            except queue.Empty:
                pass

            # 2. Idle Heartbeat: check login status without blocking UI
            now = time.time()
            if self.is_ready and self.browser and (now - last_cookie_check > 2.0):
                last_cookie_check = now
                try:
                    cookies = self.browser.cookies()
                    has_session = any(c.get("name") == "sessionid" for c in cookies)
                    ds_user_id = next((c.get("value") for c in cookies if c.get("name") == "ds_user_id"), None)
                    self.api.update_state(logged_in=has_session, user_id=ds_user_id)
                except Exception:
                    pass

        # Cleanup
        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass
        try:
            if self.pw:
                self.pw.stop()
        except Exception:
            pass

    def dispatch_async(self, func, *args):
        self.q.put((func, args))

    def stop(self):
        self.abort_flag = True
        self.running = False
        self.q.put((None, ()))


class API:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = {
            "version": APP_VERSION,
            "browser_ready": False,
            "logged_in": False,
            "user_id": None,
            "is_scanning": False,
            "scan_progress": "กำลังเชื่อมต่อ...",
            "scan_percent": 0,
            "scan_current": 0,
            "scan_total": 0,
            "scan_phase": "",
            "scan_has_data": False,
            "scan_error": None,
            "scan_summary": None,
            "is_unfollowing": False,
            "unfollow_progress": None,
            "unfollow_finished": None,
            "error": None
        }
        self._cached_scan_data = None
        self._window = None
        self._worker = BrowserWorker(self)

    def set_window(self, win):
        self._window = win

    def update_state(self, **kwargs):
        with self._lock:
            self._state.update(kwargs)

    def _handle_scan_progress(self, info):
        """Called by Playwright expose_function during live scan."""
        pct = info.get("percent", 0)
        curr = info.get("current", 0)
        tot = info.get("total", 0)
        phase = info.get("phase", "")
        msg = info.get("message", f"กำลังสแกน... ({pct}%)")

        self.update_state(
            scan_percent=pct,
            scan_current=curr,
            scan_total=tot,
            scan_phase=phase,
            scan_progress=msg
        )

    # --- Javascript API Bridge (Pure Pull State & Data - 0% evaluate_js deadlocks) ---

    def get_version_info(self):
        """Return application version information dynamically to frontend."""
        return {
            "version": APP_VERSION,
            "title": APP_TITLE,
            "author": AUTHOR if "AUTHOR" in globals() else "ZXD44"
        }

    def get_app_state(self):
        """Called by UI timer (every ~300ms). Returns instantly with current thread-safe state snapshot."""
        with self._lock:
            return dict(self._state)

    def get_scan_results(self):
        """Returns the full parsed scan data directly via PyWebView's native JSON serialization without eval()."""
        with self._lock:
            return self._cached_scan_data or {}

    def ack_unfollow_finished(self):
        """Acknowledge unfollow finished alert so frontend doesn't re-trigger modal."""
        with self._lock:
            self._state["unfollow_finished"] = None
        return {"status": "ok"}

    def open_browser_window(self):
        def _task(worker):
            if worker.page:
                try:
                    worker.page.bring_to_front()
                    if "instagram.com" not in worker.page.url:
                        worker.page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
                except Exception:
                    pass
        self._worker.dispatch_async(_task)
        return {"status": "dispatched"}

    def toggle_always_on_top(self):
        """Toggle window always on top mode safely using Win32 API."""
        try:
            if self._window and hasattr(self._window, "native") and self._window.native:
                hwnd = self._window.native.Handle.ToInt32()
                if hwnd:
                    import ctypes
                    user32 = ctypes.windll.user32
                    ex_style = user32.GetWindowLongW(hwnd, -20)
                    is_topmost = bool(ex_style & 0x0008)
                    new_topmost = not is_topmost
                    user32.SetWindowPos(hwnd, -1 if new_topmost else -2, 0, 0, 0, 0, 0x0001 | 0x0002)
                    self._window.on_top = new_topmost
                    return {"success": True, "on_top": new_topmost}
        except Exception as e:
            return {"success": False, "error": str(e), "on_top": False}
        return {"success": False, "on_top": False}

    def get_history(self):
        """Return persistent unfollow audit log."""
        try:
            h_file = os.path.join(APPDATA_DIR, "unfollow_history.json")
            if os.path.exists(h_file):
                with open(h_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        except Exception:
            return []

    def _save_history_item(self, item):
        """Record a single unfollow audit event."""
        try:
            h_file = os.path.join(APPDATA_DIR, "unfollow_history.json")
            items = []
            if os.path.exists(h_file):
                try:
                    with open(h_file, "r", encoding="utf-8") as f:
                        items = json.load(f)
                except Exception:
                    items = []
            items.insert(0, item)
            items = items[:2000]
            with open(h_file, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def clear_history(self):
        """Clear audit history log."""
        try:
            h_file = os.path.join(APPDATA_DIR, "unfollow_history.json")
            if os.path.exists(h_file):
                os.remove(h_file)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def request_scan(self, max_pages=200):
        with self._lock:
            if self._state["is_scanning"]:
                return {"status": "already_scanning"}
            self._state["is_scanning"] = True
            self._state["scan_error"] = None
            self._state["scan_percent"] = 0
            self._state["scan_current"] = 0
            self._state["scan_total"] = 0
            self._state["scan_phase"] = "init"
            self._state["scan_progress"] = "กำลังตรวจสอบเซสชัน Instagram..."

        def _scan_worker(worker):
            try:
                # Ensure expose_function is registered for live percent reporting
                try:
                    worker.page.expose_function("report_scan_progress", self._handle_scan_progress)
                except Exception:
                    pass

                # Ensure sessionid is present
                for _ in range(30):
                    if any(c.get("name") == "sessionid" for c in worker.browser.cookies()):
                        break
                    time.sleep(1)

                self.update_state(scan_progress="กำลังดึงข้อมูลบัญชีและเริ่มต้นการสแกน...", scan_percent=2)

                scan_script = f"""
                async () => {{
                    const ds = document.cookie.match(/ds_user_id=([0-9]+)/)?.[1];
                    if (!ds) return {{ error: 'no_user_id' }};

                    const report = (pct, curr, tot, phase, msg) => {{
                        if (window.report_scan_progress) {{
                            window.report_scan_progress({{
                                percent: Math.min(100, Math.max(0, Math.round(pct))),
                                current: curr,
                                total: tot,
                                phase: phase,
                                message: msg
                            }});
                        }}
                    }};

                    report(2, 0, 0, 'init', 'กำลังเตรียมการสแกน (2%)...');

                    // 1. Try to fetch user info to know exact follower & following count
                    let followingTarget = 0;
                    let followersTarget = 0;
                    try {{
                        const infoRes = await fetch(`/api/v1/users/${{ds}}/info/`, {{ headers: {{ 'x-ig-app-id': '936619743392459' }} }});
                        if (infoRes.ok) {{
                            const infoData = await infoRes.json();
                            followingTarget = infoData?.user?.following_count || 0;
                            followersTarget = infoData?.user?.follower_count || 0;
                        }}
                    }} catch (e) {{}}

                    const totalTarget = (followingTarget + followersTarget) || 0;
                    let totalFetched = 0;

                    report(5, 0, totalTarget, 'start', totalTarget > 0 ? `พบข้อมูลทั้งหมด ${{totalTarget}} คน (เริ่มสแกน 5%)...` : 'เริ่มดึงรายชื่อ (5%)...');

                    const grab = async (ep, basePct, maxPhasePct, targetCount) => {{
                        let all = [], mx = null;
                        const maxP = {int(max_pages)};
                        const epLabel = (ep === 'following') ? 'Following' : 'Followers';

                        for (let i = 0; i < maxP; i++) {{
                            const u = `/api/v1/friendships/${{ds}}/${{ep}}/?count=50` + (mx ? `&max_id=${{encodeURIComponent(mx)}}` : '');
                            const r = await fetch(u, {{ headers: {{ 'x-ig-app-id': '936619743392459' }} }});
                            if (!r.ok) break;
                            const j = await r.json();
                            if (j.users && j.users.length) {{
                                all.push(...j.users);
                                totalFetched += j.users.length;
                            }}

                            let phasePct;
                            if (targetCount > 0) {{
                                phasePct = basePct + ((all.length / targetCount) * (maxPhasePct - basePct));
                            }} else {{
                                const progressRatio = Math.min(0.9, all.length / (all.length + 50));
                                phasePct = basePct + (progressRatio * (maxPhasePct - basePct));
                            }}

                            const overallPct = totalTarget > 0 ? (totalFetched / totalTarget) * 90 + 5 : phasePct;
                            const displayPct = Math.min(94, Math.round(overallPct));
                            const msg = totalTarget > 0 
                                ? `กำลังดึง ${{epLabel}} (${{all.length}} คน) — รวม ${{totalFetched}}/${{totalTarget}} (${{displayPct}}%)`
                                : `กำลังดึง ${{epLabel}} (${{all.length}} คน) — ${{displayPct}}%`;

                            report(displayPct, totalFetched, totalTarget, ep, msg);

                            if (!j.next_max_id) break;
                            mx = j.next_max_id;
                            await new Promise(res => setTimeout(res, 200));
                        }}
                        return all;
                    }};

                    // Sequential execution to avoid Instagram rate limit (429)
                    const following = await grab('following', 5, 48, followingTarget);
                    const followers = await grab('followers', 50, 92, followersTarget);

                    report(95, totalFetched, totalTarget, 'compare', 'กำลังวิเคราะห์บัญชีที่ไม่ติดตามกลับ (95%)...');

                    const fSet = new Set(followers.map(u => String(u.pk || u.id)));
                    const nonFollowers = following.filter(u => !fSet.has(String(u.pk || u.id)));
                    const mutual = following.filter(u => fSet.has(String(u.pk || u.id)));

                    report(100, totalFetched, totalTarget, 'done', `สแกนสำเร็จ 100% (พบ ${{nonFollowers.length}} คนไม่ฟอลกลับ)`);

                    return {{
                        my_id: ds,
                        following_count: following.length,
                        followers_count: followers.length,
                        mutual: mutual.map(u => ({{
                            id: String(u.pk || u.id),
                            username: u.username,
                            full_name: u.full_name || '',
                            profile_pic_url: u.profile_pic_url || '',
                            is_verified: !!u.is_verified,
                            is_private: !!u.is_private
                        }})),
                        non_followers: nonFollowers.map(u => ({{
                            id: String(u.pk || u.id),
                            username: u.username,
                            full_name: u.full_name || '',
                            profile_pic_url: u.profile_pic_url || '',
                            is_verified: !!u.is_verified,
                            is_private: !!u.is_private
                        }}))
                    }};
                }}
                """
                # Use generous timeout of 120s
                data = worker.page.evaluate(scan_script)
                if data and "error" in data:
                    self.update_state(
                        is_scanning=False,
                        scan_has_data=False,
                        scan_error=data.get("error", "ไม่สามารถดึงข้อมูล User ID ได้"),
                        scan_progress="การสแกนล้มเหลว",
                        scan_percent=0
                    )
                else:
                    with self._lock:
                        self._cached_scan_data = data
                        self._state["scan_summary"] = {
                            "following_count": data.get("following_count", 0),
                            "followers_count": data.get("followers_count", 0),
                            "mutual_count": len(data.get("mutual", [])),
                            "non_followers_count": len(data.get("non_followers", []))
                        }
                        self._state["scan_has_data"] = True
                        self._state["is_scanning"] = False
                        self._state["scan_error"] = None
                        self._state["scan_percent"] = 100
                        self._state["scan_progress"] = "สแกนสำเร็จ 100%"
            except Exception as e:
                self.update_state(
                    is_scanning=False,
                    scan_has_data=False,
                    scan_error=str(e),
                    scan_progress="เกิดข้อผิดพลาดในการสแกน",
                    scan_percent=0
                )

        self._worker.dispatch_async(_scan_worker)
        return {"status": "scanning_started"}

    def request_unfollow_batch(self, targets, speed_mode="turbo"):
        with self._lock:
            if self._state["is_unfollowing"]:
                return {"status": "already_unfollowing"}
            self._state["is_unfollowing"] = True
            self._state["unfollow_finished"] = None
            self._worker.abort_flag = False

        def _unfollow_worker(worker):
            success_count = 0
            failed_count = 0
            total = len(targets)

            try:
                for idx, target in enumerate(targets):
                    if worker.abort_flag:
                        break

                    u_id = target.get("id")
                    u_name = target.get("username")

                    # Direct Web/GraphQL In-Session API
                    fast_res = self._execute_fast_api_unfollow(worker, u_id, u_name)
                    ok = fast_res.get("success", False)

                    # DOM fallback if needed
                    if not ok and fast_res.get("fallback_needed", False):
                        ok = self._execute_dom_unfollow_fallback(worker, u_name)

                    if ok:
                        success_count += 1
                        self._save_history_item({
                            "username": u_name,
                            "id": u_id,
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "status": "success"
                        })
                    else:
                        failed_count += 1

                    progress_info = {
                        "username": u_name,
                        "success": ok,
                        "index": idx + 1,
                        "total": total,
                        "success_count": success_count,
                        "failed_count": failed_count,
                    }
                    self.update_state(unfollow_progress=progress_info)

                    if not worker.abort_flag and (idx + 1 < total):
                        if speed_mode == "turbo":
                            delay = random.uniform(0.7, 1.2)
                        elif speed_mode == "fast":
                            delay = random.uniform(1.2, 1.8)
                        else:  # safe
                            delay = random.uniform(2.0, 3.2)
                        time.sleep(delay)

            finally:
                summary = {
                    "total": len(targets),
                    "success": success_count,
                    "failed": failed_count,
                    "aborted": worker.abort_flag,
                }
                self.update_state(is_unfollowing=False, unfollow_finished=summary)

        self._worker.dispatch_async(_unfollow_worker)
        return {"status": "unfollow_started"}

    def stop_unfollow(self):
        self._worker.abort_flag = True
        return {"status": "stopped"}

    def _execute_fast_api_unfollow(self, worker, user_id, username):
        script = f"""
        async () => {{
            const targetId = "{user_id}";
            const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
            if (!csrf) return {{ success: false, reason: 'no_csrf' }};

            const headers = {{
                'content-type': 'application/x-www-form-urlencoded',
                'x-csrftoken': csrf,
                'x-ig-app-id': '936619743392459',
                'x-asbd-id': '129477',
                'x-requested-with': 'XMLHttpRequest'
            }};

            // 1. GraphQL PolarisUnfollowMutation
            try {{
                const body = new URLSearchParams({{
                    doc_id: '27789106940691111',
                    variables: JSON.stringify({{
                        target_user_id: targetId,
                        container_module: 'profile',
                        nav_chain: 'PolarisProfilePostsTabRoot:profilePage:1:via_cold_start'
                    }}),
                    server_timestamps: 'true'
                }}).toString();

                const res = await fetch('https://www.instagram.com/api/graphql', {{
                    method: 'POST',
                    headers,
                    credentials: 'include',
                    body
                }});

                if (res.ok) {{
                    const text = await res.text();
                    try {{
                        const j = JSON.parse(text.replace(/^for\\s*\\(;;\\);\\s*/, '').trim());
                        if (j?.data?.user_unfollow_or_remove_follower?.user?.friendship_status?.following === false || j?.status === 'ok') {{
                            return {{ success: true, method: 'graphql' }};
                        }}
                    }} catch(e) {{}}
                }}
            }} catch(e) {{}}

            // 2. Direct Web API
            try {{
                const res = await fetch(`/api/v1/web/friendships/${{targetId}}/unfollow/`, {{
                    method: 'POST',
                    headers,
                    credentials: 'include'
                }});
                if (res.ok) {{
                    const j = await res.json();
                    if (j.status === 'ok') return {{ success: true, method: 'web_api' }};
                }}
            }} catch(e) {{}}

            // 3. Destroy endpoint
            try {{
                const res = await fetch(`/api/v1/friendships/destroy/${{targetId}}/`, {{
                    method: 'POST',
                    headers,
                    credentials: 'include',
                    body: new URLSearchParams({{ user_id: targetId }}).toString()
                }});
                if (res.ok) {{
                    const j = await res.json();
                    if (j.status === 'ok') return {{ success: true, method: 'destroy_api' }};
                }}
            }} catch(e) {{}}

            return {{ success: false, fallback_needed: true }};
        }}
        """
        try:
            return worker.page.evaluate(script)
        except Exception as e:
            return {"success": False, "fallback_needed": True, "error": str(e)}

    def _execute_dom_unfollow_fallback(self, worker, username):
        try:
            worker.page.goto(f"https://www.instagram.com/{username}/", wait_until="domcontentloaded", timeout=12000)
            time.sleep(random.uniform(1.0, 1.5))

            selectors_following = [
                worker.page.get_by_role("button", name="Following"),
                worker.page.get_by_role("button", name="กำลังติดตาม"),
                worker.page.get_by_role("button", name="Requested"),
                worker.page.get_by_role("button", name="ส่งคำขอแล้ว"),
                worker.page.locator("header button:has-text('Following')"),
                worker.page.locator("header button:has-text('กำลังติดตาม')"),
            ]
            btn = None
            for loc in selectors_following:
                if loc.count() > 0 and loc.first.is_visible():
                    btn = loc.first
                    break

            if not btn:
                return True

            btn.click()
            time.sleep(random.uniform(0.7, 1.2))

            confirm_btn = None
            for name in ["Unfollow", "เลิกติดตาม", "ยกเลิกการติดตาม"]:
                c = worker.page.get_by_role("button", name=name).first
                if c.count() > 0 and c.is_visible():
                    confirm_btn = c
                    break

            if not confirm_btn:
                dialog = worker.page.locator("div[role='dialog']").first
                if dialog.count() > 0:
                    buttons = dialog.locator("button").all()
                    for b in buttons:
                        txt = (b.text_content() or "").strip().lower()
                        if txt in ["unfollow", "เลิกติดตาม", "ยกเลิกการติดตาม"]:
                            confirm_btn = b
                            break

            if confirm_btn:
                confirm_btn.click()
                time.sleep(random.uniform(0.6, 1.0))
                return True

            return False
        except Exception:
            return False

    def export_data(self, data, fmt="json", data_type="non_followers"):
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
            target_dir = desktop_dir if os.path.exists(desktop_dir) else BASE_DIR

            if data_type == "history":
                filename = f"UnfollowX_History_{timestamp}.csv" if fmt == "csv" else f"UnfollowX_History_{timestamp}.json"
                filepath = os.path.join(target_dir, filename)
                if fmt == "csv":
                    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow(["User ID", "Username", "Timestamp", "Status", "Profile URL"])
                        for u in data:
                            writer.writerow([
                                u.get("id", ""),
                                u.get("username", ""),
                                u.get("timestamp", ""),
                                u.get("status", ""),
                                f"https://www.instagram.com/{u.get('username')}/"
                            ])
                else:
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                filename = f"UnfollowX_Non_Followers_{timestamp}.csv" if fmt == "csv" else f"UnfollowX_Non_Followers_{timestamp}.json"
                filepath = os.path.join(target_dir, filename)
                if fmt == "csv":
                    with open(filepath, "w", encoding="utf-8-sig", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow(["User ID", "Username", "Full Name", "Verified", "Private", "Profile URL"])
                        for u in data:
                            writer.writerow([
                                u.get("id", ""),
                                u.get("username", ""),
                                u.get("full_name", ""),
                                "Yes" if u.get("is_verified") else "No",
                                "Yes" if u.get("is_private") else "No",
                                f"https://www.instagram.com/{u.get('username')}/"
                            ])
                else:
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

            return {"success": True, "filepath": filepath}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def cleanup(self):
        self.stop_unfollow()
        if hasattr(self, "_worker") and self._worker:
            self._worker.stop()


def main():
    api = API()
    atexit.register(api.cleanup)

    window = webview.create_window(
        title=APP_TITLE,
        url=HTML_PATH,
        js_api=api,
        width=820,
        height=560,
        min_size=(640, 420),
        background_color="#080a0f"
    )
    api.set_window(window)

    def on_closing():
        api.cleanup()
        return True

    window.events.closing += on_closing

    try:
        webview.start(debug=False)
    finally:
        api.cleanup()
        sys.exit(0)


if __name__ == "__main__":
    main()
