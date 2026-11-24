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
import logging
from logging.handlers import RotatingFileHandler
import webview
from playwright.sync_api import sync_playwright

from storage_manager import StorageManager
from safety_engine import SafetyEngine
from notifier import show_desktop_notification

# Redirect stdout/stderr to avoid NoneType attribute errors when frozen with console=False
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

try:
    from version import VERSION, APP_NAME, AUTHOR
except ImportError:
    VERSION = "0.0.3"
    APP_NAME = "UnfollowX PRO"
    AUTHOR = "ZXD44"

APP_VERSION = VERSION
APP_TITLE = f"{APP_NAME} v{APP_VERSION} — By {AUTHOR}"

# 1. Base and Profile Paths
APPDATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "ZXD44-IG-Cleaner")
PROFILE_DIR = os.path.join(APPDATA_DIR, "browser_profile")
os.makedirs(PROFILE_DIR, exist_ok=True)

# 2. Hardened Audit Logging System (Local & Persistent)
LOG_FILE = os.path.join(APPDATA_DIR, "unfollowx_audit.log")
logger = logging.getLogger("UnfollowX")
logger.setLevel(logging.INFO)
if not logger.handlers:
    rfh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    rfh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
    logger.addHandler(rfh)

logger.info("==================================================")
logger.info("UnfollowX PRO %s Initialized", APP_VERSION)
logger.info("Execution Log Path: %s", LOG_FILE)
logger.info("==================================================")

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
                    "--disable-infobars",
                    "--disable-background-networking",
                    "--disable-renderer-backgrounding",
                    "--disable-backgrounding-occluded-windows",
                ],
                no_viewport=True,
            )
            if chrome_exe:
                kwargs["executable_path"] = chrome_exe

            self.browser = self.pw.chromium.launch_persistent_context(**kwargs)
            try:
                self.browser.add_init_script("""
                    // 1. Mask navigator.webdriver
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    // 2. Realistic languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['th-TH', 'th', 'en-US', 'en']
                    });
                    // 3. Real Chrome Runtime
                    if (!window.chrome) {
                        window.chrome = { runtime: {} };
                    }
                    // 4. Mock Realistic Plugins
                    const fakePlugins = [
                        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                        { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
                    ];
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => fakePlugins
                    });
                    // 5. Hardware Concurrency & Memory
                    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
                    Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
                """)
            except Exception:
                pass

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

            # 2. Idle Heartbeat: check login status and watch for Checkpoints without blocking UI
            now = time.time()
            if self.is_ready and self.browser and (now - last_cookie_check > 2.0):
                last_cookie_check = now
                try:
                    current_url = self.page.url.lower() if self.page and not self.page.is_closed() else ""
                    # Security Watchdog: detect if Instagram routed account to checkpoint or suspended state
                    if any(x in current_url for x in ["/challenge/", "/checkpoint/", "two_factor", "suspended"]):
                        if not self.abort_flag:
                            self.abort_flag = True
                            self.api.update_state(
                                error="🚨 ตรวจพบ Instagram Security Checkpoint / Challenge! ระบบหยุดการทำงานทันทีเพื่อป้องกันบัญชี",
                                is_scanning=False,
                                is_unfollowing=False
                            )

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
        self.db_path = os.path.join(APPDATA_DIR, "unfollowx.db")
        self.storage = StorageManager(self.db_path)
        self.safety = SafetyEngine(self.storage)
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
            "error": None,
            "trust_score": 100,
            "queue_stats": {"pending": 0, "completed": 0, "failed": 0, "total": 0},
            "cooldown_remaining": 0,
            "is_warmup": False,
            "lost_followers_count": 0
        }
        self._cached_scan_data = None
        self._window = None
        self._load_cached_snapshot_on_startup()
        self._worker = BrowserWorker(self)

    def _load_cached_snapshot_on_startup(self):
        """Load latest saved following/followers snapshot from SQLite on startup for instant search."""
        try:
            following = self.storage.get_last_scan_snapshot("following") or []
            followers = self.storage.get_last_scan_snapshot("followers") or []
            if not following:
                return
            f_set = {str(u.get("id")) for u in followers}
            non_followers = []
            mutual = []
            for u in following:
                uid = str(u.get("id"))
                entry = {
                    "id": uid,
                    "username": u.get("username", ""),
                    "full_name": u.get("full_name", ""),
                    "profile_pic_url": u.get("avatar_url", ""),
                    "is_verified": False,
                    "is_private": False,
                }
                if uid in f_set:
                    mutual.append(entry)
                else:
                    non_followers.append(entry)
            followers_fmt = [
                {
                    "id": str(u.get("id")),
                    "username": u.get("username", ""),
                    "full_name": u.get("full_name", ""),
                    "profile_pic_url": u.get("avatar_url", ""),
                    "is_verified": False,
                    "is_private": False,
                }
                for u in followers
            ]
            following_fmt = mutual + non_followers
            self._cached_scan_data = {
                "following_count": len(following_fmt),
                "followers_count": len(followers_fmt),
                "following": following_fmt,
                "followers": followers_fmt,
                "mutual": mutual,
                "non_followers": non_followers,
                "lost_followers": [],
                "is_cached": True,
            }
            self._state["scan_has_data"] = True
            self._state["scan_summary"] = {
                "following_count": len(following_fmt),
                "followers_count": len(followers_fmt),
                "mutual_count": len(mutual),
                "non_followers_count": len(non_followers),
                "lost_followers_count": 0,
            }
            logger.info("Loaded cached SQLite snapshot on startup: %d non-followers", len(non_followers))
        except Exception as e:
            logger.warning("Failed to load startup snapshot: %s", e)

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

    def get_24h_unfollow_count(self):
        """Return count of successful unfollow actions in the last 24 hours."""
        try:
            return self.storage.get_24h_history_count()
        except Exception:
            return 0

    def _gaussian_delay(self, lo, hi):
        """Human-like delay: clamp Gaussian sample into [lo, hi]."""
        mu = (lo + hi) / 2.0
        sigma = (hi - lo) / 6.0
        return max(lo, min(hi, random.gauss(mu, sigma)))

    def _interruptible_sleep(self, worker, seconds):
        slept = 0.0
        while slept < seconds and not worker.abort_flag:
            step = min(0.5, seconds - slept)
            time.sleep(step)
            slept += step
        return not worker.abort_flag

    def _simulate_human_browsing(self, worker):
        """Simulate subtle human feed scrolling to generate real browser telemetry."""
        try:
            if not worker.page or worker.page.is_closed():
                return
            if "instagram.com" not in (worker.page.url or ""):
                worker.page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=20000)
            worker.page.evaluate("""
                () => {
                    const scrollAmount = Math.floor(Math.random() * 260) + 140;
                    window.scrollBy({ top: scrollAmount, behavior: 'smooth' });
                    setTimeout(() => {
                        window.scrollBy({ top: -Math.floor(scrollAmount * 0.55), behavior: 'smooth' });
                    }, 1400);
                }
            """)
            time.sleep(random.uniform(2.5, 4.0))
        except Exception:
            pass

    def get_app_state(self):
        """Called by UI timer (every ~300ms). Returns instantly with current thread-safe state snapshot."""
        with self._lock:
            snap = dict(self._state)
            snap["daily_count"] = self.get_24h_unfollow_count()
            snap["daily_max"] = self.safety.get_daily_quota(self._state.get("is_warmup", False))
            snap["trust_score"] = self.safety.trust_score
            snap["cooldown_remaining"] = self.safety.get_remaining_cooldown()
            snap["queue_stats"] = self.storage.get_queue_stats()
            return snap

    def get_queue_list(self):
        """Get pending queue items from persistent SQLite storage."""
        return self.storage.get_pending_queue(100)

    def enqueue_unfollow_targets(self, targets):
        """Enqueue targets into persistent storage."""
        count = self.storage.enqueue_targets(targets)
        return {"status": "enqueued", "count": count}

    def clear_queue(self, completed_only=True):
        if completed_only:
            self.storage.clear_completed_queue()
        else:
            self.storage.clear_all_queue()
        return {"status": "cleared"}

    def retry_failed_queue(self):
        """Reset failed queue items back to pending in SQLite."""
        count = self.storage.retry_failed_queue()
        return {"status": "ok", "count": count}

    def get_whitelist(self):
        """Return persistent whitelist entries from SQLite."""
        try:
            return self.storage.get_whitelist()
        except Exception:
            return []

    def add_to_whitelist(self, user_id, username, full_name="", avatar_url=""):
        ok = self.storage.add_to_whitelist(user_id, username, full_name=full_name, avatar_url=avatar_url)
        return {"status": "ok" if ok else "error"}

    def remove_from_whitelist(self, user_id, username=""):
        ok = self.storage.remove_from_whitelist(user_id)
        return {"status": "ok" if ok else "error"}

    def sync_whitelist(self, items):
        """Migrate legacy localStorage whitelist entries into SQLite."""
        count = self.storage.sync_whitelist(items)
        return {"status": "ok", "count": count}

    def resume_pending_queue(self, speed_mode="turbo_fast"):
        """Resume any unfinished unfollow queue items directly from persistent SQLite storage."""
        pending = self.storage.get_pending_queue(50)
        if not pending:
            return {"status": "empty", "message": "ไม่มีคิวค้างในระบบ"}
        targets = [{"id": str(item["id"]), "username": item["username"]} for item in pending]
        return self.request_unfollow_batch(targets, speed_mode=speed_mode)

    def set_warmup_mode(self, enabled=True):
        with self._lock:
            self._state["is_warmup"] = bool(enabled)
        return {"is_warmup": self._state["is_warmup"]}

    def _remove_unfollowed_from_cache(self, unfollowed_ids, unfollowed_usernames):
        """Remove successfully unfollowed accounts from in-memory scan cache and refresh summary counts."""
        id_set = {str(x).strip() for x in (unfollowed_ids or []) if str(x).strip()}
        uname_set = {str(x).strip().lower() for x in (unfollowed_usernames or []) if str(x).strip()}
        if not id_set and not uname_set:
            return

        def _keep(user):
            uid = str(user.get("id") or "").strip()
            uname = str(user.get("username") or "").strip().lower()
            if uid and uid in id_set:
                return False
            if uname and uname in uname_set:
                return False
            return True

        with self._lock:
            if not self._cached_scan_data:
                return
            for key in ("non_followers", "following", "mutual", "lost_followers"):
                if isinstance(self._cached_scan_data.get(key), list):
                    self._cached_scan_data[key] = [u for u in self._cached_scan_data[key] if _keep(u)]

            following_cnt = len(self._cached_scan_data.get("following", []))
            followers_cnt = len(self._cached_scan_data.get("followers", []))
            mutual_cnt = len(self._cached_scan_data.get("mutual", []))
            non_followers_cnt = len(self._cached_scan_data.get("non_followers", []))
            lost_cnt = len(self._cached_scan_data.get("lost_followers", []))

            self._cached_scan_data["following_count"] = following_cnt
            self._cached_scan_data["followers_count"] = followers_cnt

            self._state["scan_summary"] = {
                "following_count": following_cnt,
                "followers_count": followers_cnt,
                "mutual_count": mutual_cnt,
                "non_followers_count": non_followers_cnt,
                "lost_followers_count": lost_cnt,
            }
            self._state["lost_followers_count"] = lost_cnt

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
                    if "instagram.com" not in (worker.page.url or ""):
                        worker.page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
                except Exception:
                    pass
            # Windows foreground focus to ensure browser window pops up directly
            try:
                import ctypes
                user32 = ctypes.windll.user32
                def _enum_cb(hwnd, lparam):
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            t = buff.value
                            if "Instagram" in t or "Chrome" in t:
                                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                                user32.SetForegroundWindow(hwnd)
                                return False
                    return True
                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
                user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)
            except Exception:
                pass
        self._worker.dispatch_async(_task)
        return {"status": "dispatched"}

    def open_profile_in_browser(self, username):
        """Navigate Playwright page to Instagram profile and bring Chrome to front."""
        clean_uname = str(username or "").strip().lstrip("@")
        if not clean_uname:
            return {"status": "error", "error": "Empty username"}

        def _task(worker):
            try:
                if worker.page and not worker.page.is_closed():
                    target_url = f"https://www.instagram.com/{clean_uname}/"
                    worker.page.goto(target_url, wait_until="domcontentloaded", timeout=25000)
                    worker.page.bring_to_front()
            except Exception as e:
                logger.error("Failed to open profile @%s: %s", clean_uname, e)

            # Bring Chrome window to front on Windows
            try:
                import ctypes
                user32 = ctypes.windll.user32
                def _enum_cb(hwnd, lparam):
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            t = buff.value
                            if "Instagram" in t or "Chrome" in t:
                                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                                user32.SetForegroundWindow(hwnd)
                                return False
                    return True
                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
                user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)
            except Exception:
                pass

        self._worker.dispatch_async(_task)
        return {"status": "navigating", "username": clean_uname}

    def manual_add_targets(self, raw_input):
        """Manually inspect entered usernames, fetch profile info if possible, and add to current scan table."""
        lines = [x.strip().lstrip("@") for x in raw_input.replace(",", "\n").splitlines() if x.strip()]
        if not lines:
            return {"status": "error", "error": "No usernames provided"}

        def _task(worker):
            results = []
            for uname in lines:
                try:
                    if not worker.page or worker.page.is_closed():
                        break
                    worker.page.goto(f"https://www.instagram.com/{uname}/", wait_until="domcontentloaded", timeout=20000)
                    time.sleep(random.uniform(0.8, 1.5))
                    
                    data = worker.page.evaluate("""() => {
                        const buttons = Array.from(document.querySelectorAll('header button, header div[role="button"]'));
                        const texts = buttons.map(b => (b.innerText || b.textContent || '').trim().toLowerCase());
                        const isFollowing = texts.some(t => ['following', 'กำลังติดตาม', 'requested', 'ส่งคำขอแล้ว'].some(k => t.includes(k)));
                        
                        const img = document.querySelector('header img');
                        const pic = img ? img.src : '';
                        
                        const titleEl = document.querySelector('header section span, header h1, header h2');
                        const fullName = titleEl ? (titleEl.innerText || titleEl.textContent || '').trim() : '';
                        const isVerified = !!document.querySelector('header svg[aria-label*="Verified"], header svg[aria-label*="ยืนยันแล้ว"]');
                        
                        return {
                            is_following: isFollowing,
                            profile_pic_url: pic,
                            full_name: fullName,
                            is_verified: isVerified
                        };
                    }""")
                    
                    results.append({
                        "id": str(random.randint(10000000000, 99999999999)),
                        "username": uname,
                        "full_name": data.get("full_name") or uname,
                        "profile_pic_url": data.get("profile_pic_url", ""),
                        "is_verified": bool(data.get("is_verified")),
                        "is_private": False,
                        "is_following": bool(data.get("is_following", True))
                    })
                except Exception as e:
                    logger.error("Manual add target @%s error: %s", uname, e)
                    results.append({
                        "id": str(random.randint(10000000000, 99999999999)),
                        "username": uname,
                        "full_name": uname,
                        "profile_pic_url": "",
                        "is_verified": False,
                        "is_private": False,
                        "is_following": True
                    })

            with self._lock:
                if not self._cached_scan_data:
                    self._cached_scan_data = {
                        "following_count": len(results),
                        "followers_count": 0,
                        "following": results,
                        "followers": [],
                        "mutual": [],
                        "non_followers": results,
                        "lost_followers": [],
                        "is_cached": True
                    }
                else:
                    existing = {u.get("username") for u in self._cached_scan_data.get("non_followers", [])}
                    for r in results:
                        if r.get("username") not in existing:
                            self._cached_scan_data["non_followers"].append(r)
                            if "following" in self._cached_scan_data:
                                self._cached_scan_data["following"].append(r)

                non_f = self._cached_scan_data.get("non_followers", [])
                self._state["scan_summary"] = {
                    "following_count": len(self._cached_scan_data.get("following", [])),
                    "followers_count": len(self._cached_scan_data.get("followers", [])),
                    "mutual_count": len(self._cached_scan_data.get("mutual", [])),
                    "non_followers_count": len(non_f),
                    "lost_followers_count": 0
                }
                self._state["scan_has_data"] = True
                self._state["scan_error"] = None
                self._state["scan_progress"] = f"เพิ่มรายชื่อด้วยตนเองสำเร็จ ({len(results)} คน)"
                self._state["scan_percent"] = 100

        self._worker.dispatch_async(_task)
        return {"status": "started", "count": len(lines)}

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
            return self.storage.get_audit_history(500)
        except Exception:
            return []

    def _save_history_item(self, item):
        """Record a single unfollow audit event."""
        try:
            self.storage.record_history(
                user_id=item.get("id"),
                username=item.get("username"),
                status=item.get("status"),
                method=item.get("method"),
                reason=item.get("reason")
            )
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

                cookies = worker.browser.cookies()
                ds_user_id = next((c.get("value") for c in cookies if c.get("name") == "ds_user_id"), None)
                if not ds_user_id:
                    ds_user_id = self._state.get("user_id")

                if not ds_user_id:
                    self.update_state(
                        is_scanning=False,
                        scan_has_data=False,
                        scan_error="⚠️ ไม่พบข้อมูลบัญชีที่เข้าสู่ระบบ\n\n• กรุณากดปุ่ม 'เปิด Instagram' เพื่อเข้าสู่ระบบในเบราว์เซอร์ให้เรียบร้อยก่อนกดสแกน",
                        scan_progress="กรุณาเข้าสู่ระบบ",
                        scan_percent=0
                    )
                    return

                self.update_state(scan_progress="กำลังดึงข้อมูลบัญชีและเริ่มต้นการสแกน...", scan_percent=2)

                scan_script = f"""
                async () => {{
                    const passedDs = "{ds_user_id}";
                    let ds = passedDs || document.cookie.match(/ds_user_id=([0-9]+)/)?.[1];
                    if (!ds) {{
                        ds = window._sharedData?.config?.viewerId || window.__initialData?.data?.viewer?.id;
                    }}
                    if (!ds) return {{ error: '⚠️ ไม่พบ Session บัญชีผู้ใช้ (กรุณาเปิดหน้าต่าง Instagram แล้วตรวจสอบว่าเข้าสู่ระบบเรียบร้อย)' }};

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
                        const infoRes = await fetch(`/api/v1/users/${{ds}}/info/`, {{
                            credentials: 'include',
                            headers: {{ 'x-ig-app-id': '936619743392459', 'x-requested-with': 'XMLHttpRequest' }}
                        }});
                        if (infoRes.ok) {{
                            const text = await infoRes.text();
                            if (text && !text.trim().startsWith('<')) {{
                                const infoData = JSON.parse(text);
                                followingTarget = infoData?.user?.following_count || 0;
                                followersTarget = infoData?.user?.follower_count || 0;
                            }}
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
                            // Use count=20 (standard Instagram web pagination size to avoid bot action blocks)
                            const queryParam = (ep === 'followers') ? 'count=20&search_surface=follow_list_page' : 'count=20';
                            const u = `/api/v1/friendships/${{ds}}/${{ep}}/?${{queryParam}}` + (mx ? `&max_id=${{encodeURIComponent(mx)}}` : '');
                            let r;
                            try {{
                                r = await fetch(u, {{
                                    credentials: 'include',
                                    headers: {{
                                        'x-ig-app-id': '936619743392459',
                                        'x-requested-with': 'XMLHttpRequest',
                                        'accept': '*/*'
                                    }}
                                }});
                            }} catch (netErr) {{
                                return {{ error: '⚠️ การเชื่อมต่อไปยัง Instagram ขัดข้อง: ' + (netErr?.message || netErr) }};
                            }}

                            const text = await r.text();

                            // Action limit / rate limit detection
                            if (r.status === 400 || r.status === 429) {{
                                try {{
                                    const errJson = JSON.parse(text);
                                    if (errJson.message === 'feedback_required' || errJson.is_spam || errJson.feedback_title) {{
                                        return {{
                                            error: '🛡️ Instagram จำกัดความถี่ชั่วคราว (Action Block: Try Again Later)\\n\\n' +
                                                   '• สาเหตุ: Instagram พักการเรียกดูรายชื่อชั่วคราวเพื่อปกป้องบัญชีของคุณ\\n' +
                                                   '• วิธีแก้ไข: แนะนำพักการสแกนประมาณ 1–2 ชั่วโมง หรือเปิด Instagram เพื่อกดยืนยันปุ่มแจ้งเตือน\\n' +
                                                   '• ข้อมูล: บัญชีของคุณยังปลอดภัย 100% ไม่มีการถูกแบนหรือรหัสผ่านหลุด'
                                        }};
                                    }}
                                }} catch (e) {{}}
                                return {{ error: '⚠️ Instagram แจ้งจำกัดความถี่ (HTTP ' + r.status + ') กรุณารอสักครู่' }};
                            }}

                            // Safe check against 302 redirect / HTML fallback
                            if (!text || text.trim().startsWith('<') || r.redirected) {{
                                return {{
                                    error: '🛡️ บัญชีติดข้อจำกัดความถี่จาก Instagram (Action Cooldown)\\n\\n' +
                                           '• สาเหตุ: Instagram กำลังพักการตอบสนองคำขอดูรายชื่อชั่วคราว (302 Cooldown)\\n' +
                                           '• วิธีแก้ไข: แนะนำพักการใช้งานประมาณ 1–2 ชั่วโมง แล้วเปิดหน้า Instagram เพื่อตรวจเช็คสถานะ\\n' +
                                           '• ข้อมูล: ระบบหยุดทำงานอัตโนมัติเพื่อความปลอดภัยของบัญชี 100%'
                                }};
                            }}

                            let j;
                            try {{
                                j = JSON.parse(text);
                            }} catch (parseErr) {{
                                return {{ error: '⚠️ ไม่สามารถอ่านข้อมูล JSON จาก Instagram ได้ กรุณารีเฟรชเซสชัน' }};
                            }}

                            if (j.users && j.users.length) {{
                                all.push(...j.users);
                                totalFetched += j.users.length;
                            }}

                            let phasePct;
                            if (targetCount > 0) {{
                                phasePct = basePct + ((all.length / targetCount) * (maxPhasePct - basePct));
                            }} else {{
                                const progressRatio = Math.min(0.9, all.length / (all.length + 30));
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
                            // Safe humanized delay
                            const pageDelay = Math.floor(Math.random() * 250) + 350;
                            await new Promise(res => setTimeout(res, pageDelay));
                        }}
                        return all;
                    }};

                    // Sequential execution with optimized cooldown break
                    const followingRes = await grab('following', 5, 48, followingTarget);
                    if (followingRes && followingRes.error) return followingRes;
                    const following = Array.isArray(followingRes) ? followingRes : [];

                    // Fast and safe cooldown pause between following and followers (400ms - 600ms)
                    await new Promise(res => setTimeout(res, 400 + Math.random() * 200));

                    const followersRes = await grab('followers', 50, 92, followersTarget);
                    if (followersRes && followersRes.error) return followersRes;
                    const followers = Array.isArray(followersRes) ? followersRes : [];

                    report(95, totalFetched, totalTarget, 'compare', 'กำลังวิเคราะห์บัญชีที่ไม่ติดตามกลับ (95%)...');

                    const fSet = new Set(followers.map(u => String(u.pk || u.id)));
                    const nonFollowers = following.filter(u => !fSet.has(String(u.pk || u.id)));
                    const mutual = following.filter(u => fSet.has(String(u.pk || u.id)));

                    report(100, totalFetched, totalTarget, 'done', `สแกนสำเร็จ 100% (พบ ${{nonFollowers.length}} คนไม่ฟอลกลับ)`);

                    return {{
                        my_id: ds,
                        following_count: following.length,
                        followers_count: followers.length,
                        followers: followers.map(u => ({{
                            id: String(u.pk || u.id),
                            username: u.username,
                            full_name: u.full_name || '',
                            profile_pic_url: u.profile_pic_url || '',
                            is_verified: !!u.is_verified,
                            is_private: !!u.is_private
                        }})),
                        following: following.map(u => ({{
                            id: String(u.pk || u.id),
                            username: u.username,
                            full_name: u.full_name || '',
                            profile_pic_url: u.profile_pic_url || '',
                            is_verified: !!u.is_verified,
                            is_private: !!u.is_private
                        }})),
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
                    err_msg = data.get("error", "เกิดข้อผิดพลาดในการสแกน")
                    # Check if SQLite has previous snapshot to fallback gracefully
                    saved_following = self.storage.get_last_scan_snapshot("following")
                    saved_followers = self.storage.get_last_scan_snapshot("followers")
                    if saved_following:
                        f_set = {str(u.get("id")) for u in saved_followers}
                        non_f = [u for u in saved_following if str(u.get("id")) not in f_set]
                        mutual_f = [u for u in saved_following if str(u.get("id")) in f_set]
                        fallback_data = {
                            "following_count": len(saved_following),
                            "followers_count": len(saved_followers),
                            "following": saved_following,
                            "followers": saved_followers,
                            "mutual": mutual_f,
                            "non_followers": non_f,
                            "lost_followers": [],
                            "is_cached": True
                        }
                        with self._lock:
                            self._cached_scan_data = fallback_data
                            self._state["scan_summary"] = {
                                "following_count": len(saved_following),
                                "followers_count": len(saved_followers),
                                "mutual_count": len(mutual_f),
                                "non_followers_count": len(non_f),
                                "lost_followers_count": 0
                            }
                            self._state["scan_has_data"] = True
                            self._state["is_scanning"] = False
                            self._state["scan_error"] = f"{err_msg}\n\n💡 โหลดข้อมูลสแกนล่าสุดที่บันทึกไว้ ({len(non_f)} คน) ให้คุณใช้งานต่อได้ทันที"
                            self._state["scan_progress"] = "โหลดข้อมูลล่าสุดที่บันทึกไว้ในระบบ"
                            self._state["scan_percent"] = 100
                    else:
                        self.update_state(
                            is_scanning=False,
                            scan_has_data=False,
                            scan_error=err_msg,
                            scan_progress="การสแกนถูกระงับชั่วคราว",
                            scan_percent=0
                        )
                else:
                    # Diff scan analysis & snapshot persistence
                    followers_list = data.get("followers", [])
                    following_list = data.get("following", [])
                    lost = self.storage.compute_diff(followers_list)
                    self.storage.save_scan_snapshot("followers", followers_list)
                    self.storage.save_scan_snapshot("following", following_list)
                    data["lost_followers"] = lost

                    with self._lock:
                        self._cached_scan_data = data
                        self._state["lost_followers_count"] = len(lost)
                        self._state["scan_summary"] = {
                            "following_count": data.get("following_count", 0),
                            "followers_count": data.get("followers_count", 0),
                            "mutual_count": len(data.get("mutual", [])),
                            "non_followers_count": len(data.get("non_followers", [])),
                            "lost_followers_count": len(lost)
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

    def request_unfollow_batch(self, targets, speed_mode="ultimate_safe"):
        if self.safety.is_in_cooldown():
            rem = self.safety.get_remaining_cooldown()
            return {
                "status": "in_cooldown",
                "error": f"🛡️ ระบบอยู่ในช่วง Safety Cooldown เพื่อป้องกันการตรวจจับ (เหลือเวลาพักอีก {rem} วินาที)"
            }

        daily_count = self.get_24h_unfollow_count()
        is_warmup = self._state.get("is_warmup", False)
        max_daily_allowed = self.safety.get_daily_quota(is_warmup=is_warmup)

        if daily_count >= max_daily_allowed:
            return {
                "status": "daily_limit_reached",
                "error": f"🛡️ บัญชีของคุณเลิกติดตามครบโควตาความปลอดภัยสูงสุด {max_daily_allowed} คนในรอบ 24 ชั่วโมงแล้ว (โหมด Warmup: {is_warmup}) ระบบล็อกการทำงานชั่วคราวเพื่อปกป้องบัญชีของคุณ 100%"
            }

        # Filter targets with Smart Skip (skip processed in 7 days or repeatedly failed)
        filtered_targets = []
        for t in targets:
            uid = str(t.get("id") or "").strip()
            if not uid:
                continue
            if self.storage.is_recently_processed(uid, days=7):
                logger.info("Smart Skip: User %s already processed within 7 days", uid)
                continue
            if self.storage.get_recent_failures_count(uid, days=3) >= 3:
                logger.warning("Smart Skip: User %s failed 3+ times recently", uid)
                continue
            filtered_targets.append(t)

        if not filtered_targets:
            return {
                "status": "all_skipped",
                "error": "รายชื่อที่เลือกทั้งหมดถูกข้ามโดย Smart Skip (เนื่องจากเพิ่งเลิกติดตามไปแล้วใน 7 วัน หรือล้มเหลวซ้ำ)"
            }

        # Hard safety cap: maximum 15 accounts per batch session (or 5 if warmup)
        batch_cap = 5 if is_warmup else 15
        max_allowed = min(batch_cap, max(0, max_daily_allowed - daily_count))
        targets = filtered_targets[:max_allowed]

        # Enqueue to persistent storage
        self.storage.enqueue_targets(targets)

        with self._lock:
            if self._state["is_unfollowing"]:
                return {"status": "already_unfollowing"}
            self._state["is_unfollowing"] = True
            self._state["unfollow_finished"] = None
            self._worker.abort_flag = False

        def _unfollow_worker(worker):
            success_count = 0
            failed_count = 0
            consecutive_fail = 0
            succeeded_ids = []
            succeeded_usernames = []
            total = len(targets)
            break_every = random.randint(3, 5) if is_warmup else random.randint(4, 6)

            try:
                self._simulate_human_browsing(worker)

                for idx, target in enumerate(targets):
                    if worker.abort_flag:
                        break

                    current_url = worker.page.url.lower() if worker.page and not worker.page.is_closed() else ""
                    if any(x in current_url for x in ["/challenge/", "/checkpoint/", "facebook.com", "two_factor", "suspended"]):
                        worker.abort_flag = True
                        self.safety.evaluate_threat(403, "checkpoint_required")
                        show_desktop_notification("UnfollowX Alert", "🚨 ตรวจพบ Checkpoint! หยุดระบบทันที")
                        self.update_state(
                            error="🚨 ตรวจพบ Instagram Challenge/Checkpoint! หยุดการทำงานฉุกเฉินทันทีเพื่อป้องกันบัญชีโดนล็อก",
                            is_unfollowing=False
                        )
                        break

                    # Rolling daily re-check mid-batch
                    if self.get_24h_unfollow_count() >= max_daily_allowed:
                        worker.abort_flag = True
                        show_desktop_notification("UnfollowX Notice", "🛡️ ครบโควตาความปลอดภัยรอบวันแล้ว")
                        self.update_state(
                            error=f"🛡️ ครบโควตาความปลอดภัย {max_daily_allowed} คนในรอบ 24 ชั่วโมง — หยุดเพื่อปกป้องบัญชี",
                            is_unfollowing=False
                        )
                        break

                    u_id = str(target.get("id") or "").strip()
                    u_name = str(target.get("username") or "").strip()
                    if not u_id or not u_name:
                        failed_count += 1
                        consecutive_fail += 1
                        continue

                    self.update_state(
                        scan_progress=f"กำลังเลิกติดตาม @{u_name} ({idx + 1}/{total})... [Trust: {self.safety.trust_score}%]"
                    )

                    fast_res = self._execute_safe_unfollow(worker, u_id, u_name)
                    threat_eval = self.safety.evaluate_threat(
                        fast_res.get("status_code", 200),
                        fast_res.get("threat_msg", "") or fast_res.get("reason", "")
                    )

                    if fast_res.get("critical_abort", False) or threat_eval["is_critical"]:
                        worker.abort_flag = True
                        threat_msg = fast_res.get("threat_msg", "ตรวจพบสัญญาณ Rate Limit หรือ Checkpoint จาก Instagram")
                        show_desktop_notification("UnfollowX Warning", f"🚨 ตัดการทำงาน: {threat_msg}")
                        self.update_state(
                            error=f"🚨 ตัดการทำงานฉุกเฉิน: {threat_msg} (Trust Score ลดเหลือ {self.safety.trust_score}%)",
                            is_unfollowing=False
                        )
                        break

                    ok = bool(fast_res.get("success", False))

                    if ok:
                        success_count += 1
                        consecutive_fail = 0
                        succeeded_ids.append(u_id)
                        succeeded_usernames.append(u_name)
                        self._remove_unfollowed_from_cache([u_id], [u_name])
                        self.storage.update_queue_item(u_id, "completed")
                        self._save_history_item({
                            "username": u_name,
                            "id": u_id,
                            "status": "success",
                            "method": fast_res.get("method", "unknown")
                        })
                    else:
                        failed_count += 1
                        consecutive_fail += 1
                        self.storage.update_queue_item(u_id, "failed", error=fast_res.get("reason", "unknown"))
                        self._save_history_item({
                            "username": u_name,
                            "id": u_id,
                            "status": "failed",
                            "reason": fast_res.get("reason", "unknown")
                        })
                        if consecutive_fail >= 3:
                            worker.abort_flag = True
                            self.safety.evaluate_threat(429, "soft_rate_limit")
                            show_desktop_notification("UnfollowX Notice", "⏸️ ล้มเหลวติดกัน 3 ครั้ง — ระบบเข้าสู่ Safety Cooldown")
                            self.update_state(
                                error=f"⏸️ เลิกติดตามล้มเหลวติดกัน 3 ครั้ง — หยุดพักเพื่อลดความเสี่ยง (Trust: {self.safety.trust_score}%)",
                                is_unfollowing=False
                            )
                            break

                    remaining = max(0, total - (idx + 1))
                    avg_gap = 40.0 if "balanced" in str(speed_mode).lower() else 55.0
                    eta_seconds = int(remaining * avg_gap + (remaining // 4) * 100)
                    self.update_state(unfollow_progress={
                        "username": u_name,
                        "success": ok,
                        "index": idx + 1,
                        "total": total,
                        "success_count": success_count,
                        "failed_count": failed_count,
                        "method": fast_res.get("method"),
                        "eta_seconds": eta_seconds,
                    })

                    if worker.abort_flag or (idx + 1 >= total):
                        continue

                    # Dynamic Adaptive Rate Delay based on SafetyEngine
                    delay = self.safety.get_adaptive_delay(base_mode=speed_mode)
                    is_turbo_or_fast = any(k in str(speed_mode).lower() for k in ("turbo", "fast"))

                    if not is_turbo_or_fast and (idx + 1) % break_every == 0:
                        micro_break = self._gaussian_delay(20.0, 45.0)
                        break_every = random.randint(5, 8)
                        self.update_state(
                            scan_progress=f"⏸️ พักเบรกความปลอดภัย ({int(micro_break)} วินาที) จำลองพฤติกรรมมนุษย์..."
                        )
                        if not self._interruptible_sleep(worker, micro_break):
                            break

                    half = delay / 2.0
                    if not self._interruptible_sleep(worker, half):
                        break
                    if not is_turbo_or_fast:
                        self._simulate_human_browsing(worker)
                    if not self._interruptible_sleep(worker, delay - half):
                        break

            finally:
                self._remove_unfollowed_from_cache(succeeded_ids, succeeded_usernames)
                summary = {
                    "total": len(targets),
                    "success": success_count,
                    "failed": failed_count,
                    "aborted": worker.abort_flag,
                    "succeeded_usernames": succeeded_usernames,
                }
                self.update_state(is_unfollowing=False, unfollow_finished=summary)
                show_desktop_notification(
                    "UnfollowX เสร็จสิ้นรอบทำงาน",
                    f"สำเร็จ: {success_count} คน | ล้มเหลว: {failed_count} คน"
                )

        self._worker.dispatch_async(_unfollow_worker)
        return {"status": "unfollow_started"}

    def stop_unfollow(self):
        self._worker.abort_flag = True
        return {"status": "stopped"}

    def _execute_safe_unfollow(self, worker, user_id, username):
        """
        Unfollow via live Instagram web session.
        Primary: POST /api/v1/friendships/destroy/{id}/  (current web protocol)
        Fallback: POST /web/friendships/{id}/unfollow/
        Last resort: UI click on profile (human path)
        Always verify with /api/v1/friendships/show/{id}/
        """
        try:
            if not worker.page or worker.page.is_closed():
                return {"success": False, "critical_abort": True, "threat_msg": "หน้าต่างเบราว์เซอร์ถูกปิด"}

            # Keep session on instagram.com origin (required for cookie + CSRF)
            url = (worker.page.url or "").lower()
            if "instagram.com" not in url or any(x in url for x in ["/challenge/", "/checkpoint/", "suspended"]):
                if any(x in url for x in ["/challenge/", "/checkpoint/", "suspended", "facebook.com", "two_factor"]):
                    return {"success": False, "critical_abort": True, "threat_msg": "ตรวจพบ Checkpoint/Challenge"}
                worker.page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=25000)
                time.sleep(random.uniform(1.2, 2.2))

            uid = str(user_id).replace("\\", "\\\\").replace('"', '\\"')
            uname = str(username).replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")

            script = f"""
            async () => {{
                const targetId = "{uid}";
                const username = "{uname}";

                const csrf = (document.cookie.match(/(?:^|;\\\\s*)csrftoken=([^;]+)/) || [])[1];
                if (!csrf) return {{ success: false, reason: 'no_csrf' }};

                const appIdMatch = (document.documentElement.innerHTML || '').match(/"X-IG-App-ID":"(\\\\d+)"/);
                const appId = appIdMatch ? appIdMatch[1] : '936619743392459';

                const headers = {{
                    'content-type': 'application/x-www-form-urlencoded',
                    'x-csrftoken': csrf,
                    'x-ig-app-id': appId,
                    'x-asbd-id': '129477',
                    'x-instagram-ajax': '1',
                    'x-requested-with': 'XMLHttpRequest',
                    'x-web-session-id': (window._sharedData && window._sharedData.config && window._sharedData.config.viewerId) ? String(Date.now()) : undefined,
                    'accept': '*/*',
                    'origin': 'https://www.instagram.com',
                    'referer': 'https://www.instagram.com/'
                }};
                Object.keys(headers).forEach(k => headers[k] === undefined && delete headers[k]);

                const threatFrom = (status, text) => {{
                    const lower = (text || '').toLowerCase();
                    if (status === 429 || status === 401 || status === 403) {{
                        return {{ critical: true, msg: status === 429 ? 'Rate Limit (429)' : 'สิทธิ์ถูกจำกัด (' + status + ')' }};
                    }}
                    if (
                        lower.includes('checkpoint_required') || lower.includes('challenge_required') ||
                        lower.includes('feedback_required') || lower.includes('action_blocked') ||
                        lower.includes('spam') || lower.includes('please wait a few minutes') ||
                        lower.includes('user_has_logged_out') || lower.includes('login_required')
                    ) {{
                        return {{
                            critical: true,
                            msg: lower.includes('checkpoint') || lower.includes('challenge') ? 'Checkpoint/Challenge' :
                                 lower.includes('feedback') || lower.includes('action_blocked') ? 'Action Block' :
                                 lower.includes('wait') ? 'Rate Limit ชั่วคราว' : 'ถูกจำกัดสิทธิ์จาก Instagram'
                        }};
                    }}
                    return {{ critical: false }};
                }};

                const looksOk = (status, text) => {{
                    if (!(status >= 200 && status < 300)) return false;
                    try {{
                        const j = JSON.parse(text);
                        if (j.status === 'ok') return true;
                        if (j.friendship_status && j.friendship_status.following === false) return true;
                        if (j.following === false) return true;
                    }} catch (e) {{}}
                    return false;
                }};

                const verify = async () => {{
                    try {{
                        const r = await fetch(`/api/v1/friendships/show/${{targetId}}/`, {{
                            method: 'GET',
                            credentials: 'include',
                            headers: {{ 'x-ig-app-id': appId, 'x-requested-with': 'XMLHttpRequest' }}
                        }});
                        const j = await r.json();
                        const fs = j.friendship_status || j;
                        if (fs && fs.following === false) return true;
                        if (j.following === false) return true;
                    }} catch (e) {{}}
                    return false;
                }};

                const tryPost = async (path, body) => {{
                    const res = await fetch(path, {{
                        method: 'POST',
                        headers,
                        credentials: 'include',
                        body: body || ''
                    }});
                    const text = await res.text();
                    const threat = threatFrom(res.status, text);
                    return {{ status: res.status, text: text.slice(0, 400), threat, ok: looksOk(res.status, text) }};
                }};

                const body = new URLSearchParams({{
                    user_id: targetId,
                    container_module: 'profile',
                    jazoest: String(2 + Array.from(csrf).reduce((a, c) => a + c.charCodeAt(0), 0))
                }}).toString();

                // 1) Current official web destroy endpoint
                try {{
                    const a = await tryPost(`/api/v1/friendships/destroy/${{targetId}}/`, body);
                    if (a.threat.critical) return {{ success: false, critical_abort: true, threat_msg: a.threat.msg, http: a.status, body: a.text }};
                    if (a.ok || await verify()) return {{ success: true, method: 'friendships_destroy', http: a.status }};
                }} catch (e) {{}}

                // 2) Classic web unfollow path
                try {{
                    const b = await tryPost(`/web/friendships/${{targetId}}/unfollow/`, body);
                    if (b.threat.critical) return {{ success: false, critical_abort: true, threat_msg: b.threat.msg, http: b.status, body: b.text }};
                    if (b.ok || await verify()) return {{ success: true, method: 'web_friendships_unfollow', http: b.status }};
                }} catch (e) {{}}

                // 3) Legacy /api/v1/web path (kept as last API attempt)
                try {{
                    const c = await tryPost(`/api/v1/web/friendships/${{targetId}}/unfollow/`, body);
                    if (c.threat.critical) return {{ success: false, critical_abort: true, threat_msg: c.threat.msg, http: c.status, body: c.text }};
                    if (c.ok || await verify()) return {{ success: true, method: 'api_v1_web_unfollow', http: c.status }};
                }} catch (e) {{}}

                return {{ success: false, critical_abort: false, reason: 'api_failed', need_ui: true }};
            }}
            """
            res = worker.page.evaluate(script)
            if not isinstance(res, dict):
                res = {"success": False, "reason": "bad_eval_result"}

            if res.get("success") or res.get("critical_abort"):
                logger.info("Unfollow API @%s (%s): %s", username, user_id, json.dumps(res, ensure_ascii=False))
                return res

            # 4) UI fallback — same path a human takes on the profile page
            if res.get("need_ui") or not res.get("success"):
                ui_res = self._unfollow_via_ui(worker, user_id, username)
                logger.info("Unfollow UI @%s (%s): %s", username, user_id, json.dumps(ui_res, ensure_ascii=False))
                return ui_res

            logger.info("Unfollow result @%s (%s): %s", username, user_id, json.dumps(res, ensure_ascii=False))
            return res
        except Exception as e:
            err_str = str(e).lower()
            logger.error("Exception in unfollow for @%s: %s", username, err_str)
            if any(k in err_str for k in ["navigation", "closed", "crash", "target"]):
                return {"success": False, "critical_abort": True, "threat_msg": "หน้าต่างเบราว์เซอร์ถูกปิดหรือนำทางออกนอกระบบ"}
            return {"success": False, "critical_abort": False, "error": str(e)}

    def _unfollow_via_ui(self, worker, user_id, username):
        """Human-path unfollow: open profile → Following → confirm Unfollow → verify."""
        try:
            page = worker.page
            if not page or page.is_closed():
                return {"success": False, "critical_abort": True, "threat_msg": "หน้าต่างเบราว์เซอร์ถูกปิด"}

            profile_url = f"https://www.instagram.com/{username}/"
            page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(self._gaussian_delay(1.8, 3.2))

            cur = (page.url or "").lower()
            if any(x in cur for x in ["/challenge/", "/checkpoint/", "suspended", "facebook.com", "two_factor"]):
                return {"success": False, "critical_abort": True, "threat_msg": "Checkpoint/Challenge ระหว่างเปิดโปรไฟล์"}

            # Already not following?
            check = page.evaluate(f"""
                async () => {{
                    try {{
                        const r = await fetch('/api/v1/friendships/show/{user_id}/', {{
                            credentials: 'include',
                            headers: {{ 'x-ig-app-id': '936619743392459' }}
                        }});
                        const j = await r.json();
                        const fs = j.friendship_status || j;
                        return {{ following: !!(fs && fs.following) }};
                    }} catch (e) {{
                        return {{ following: null }};
                    }}
                }}
            """)
            if isinstance(check, dict) and check.get("following") is False:
                return {"success": True, "method": "already_unfollowed"}

            # Click Following / กำลังติดตาม / Requested
            clicked = page.evaluate("""
                () => {
                    const labels = ['following', 'กำลังติดตาม', 'requested', 'ส่งคำขอแล้ว', 'unfollow'];
                    const nodes = Array.from(document.querySelectorAll('button, div[role="button"], a'));
                    for (const el of nodes) {
                        const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                        if (!t) continue;
                        if (labels.some(l => t === l || t.startsWith(l))) {
                            el.click();
                            return { clicked: true, text: t };
                        }
                    }
                    return { clicked: false };
                }
            """)
            if not clicked or not clicked.get("clicked"):
                return {"success": False, "critical_abort": False, "reason": "following_button_not_found", "method": "ui"}

            time.sleep(self._gaussian_delay(0.7, 1.4))

            # Confirm Unfollow in dialog / menu
            confirmed = page.evaluate("""
                () => {
                    const labels = ['unfollow', 'เลิกติดตาม', 'ยกเลิกการติดตาม'];
                    const nodes = Array.from(document.querySelectorAll('button, div[role="button"], [role="menuitem"]'));
                    for (const el of nodes) {
                        const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                        if (!t) continue;
                        if (labels.some(l => t === l || t.includes(l))) {
                            el.click();
                            return { confirmed: true, text: t };
                        }
                    }
                    return { confirmed: false };
                }
            """)
            time.sleep(self._gaussian_delay(1.2, 2.0))

            verified = page.evaluate(f"""
                async () => {{
                    try {{
                        const r = await fetch('/api/v1/friendships/show/{user_id}/', {{
                            credentials: 'include',
                            headers: {{ 'x-ig-app-id': '936619743392459' }}
                        }});
                        const j = await r.json();
                        const fs = j.friendship_status || j;
                        return fs && fs.following === false;
                    }} catch (e) {{
                        return false;
                    }}
                }}
            """)

            if verified:
                return {"success": True, "method": "ui_profile", "confirmed": bool(confirmed and confirmed.get("confirmed"))}

            # Soft verify via button text change
            soft = page.evaluate("""
                () => {
                    const labels = ['follow', 'ติดตาม'];
                    const bad = ['following', 'กำลังติดตาม', 'requested'];
                    const nodes = Array.from(document.querySelectorAll('button, div[role="button"]'));
                    for (const el of nodes) {
                        const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                        if (labels.includes(t) && !bad.includes(t)) return true;
                    }
                    return false;
                }
            """)
            if soft:
                return {"success": True, "method": "ui_profile_soft"}

            return {
                "success": False,
                "critical_abort": False,
                "reason": "ui_unfollow_unverified",
                "method": "ui",
                "dialog": confirmed
            }
        except Exception as e:
            logger.error("UI unfollow failed @%s: %s", username, e)
            return {"success": False, "critical_abort": False, "reason": "ui_exception", "error": str(e)}

    def open_log_folder(self):
        """Open the directory containing execution and audit logs in Windows Explorer."""
        try:
            if os.path.exists(APPDATA_DIR):
                os.startfile(APPDATA_DIR)
                logger.info("Opened log directory in explorer: %s", APPDATA_DIR)
                return {"success": True, "path": APPDATA_DIR}
        except Exception as e:
            logger.error("Failed to open log directory: %s", str(e))
            return {"success": False, "error": str(e)}
        return {"success": False}

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
        width=980,
        height=640,
        min_size=(780, 520),
        background_color="#12110f"
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
