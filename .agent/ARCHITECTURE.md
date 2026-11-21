# Architecture: UnfollowX PRO

This document outlines the architecture, data structures, communication protocols, and execution workflows of **UnfollowX PRO**.

---

## 1. High-Level Architecture

UnfollowX PRO combines a modern lightweight desktop HTML5/CSS3 interface with a Python automation engine controlling a Chromium instance via Playwright.

```mermaid
graph TD
    subgraph UI_Layer ["GUI Frontend (EdgeChromium Webview)"]
        HTML["gui_template.html"]
        UI_Engine["Vanilla JS UI Controller"]
        Audio["Web Audio Synthesizer"]
        HTML --> UI_Engine
        UI_Engine --> Audio
    end

    subgraph Bridge_Layer ["PyWebView Interop"]
        JS_API["window.pywebview.api"]
        Py_API["gui_app.py (class API)"]
        JS_API <-->|"JSON-RPC / eval_js"| Py_API
    end

    subgraph Engine_Layer ["Core Engine & Automation"]
        Worker["AutomationWorker (threading.Thread)"]
        PW["Playwright Stealth Chromium Context"]
        Watchdog["Circuit Breaker & Checkpoint Watchdog"]
        Emulation["Human Emulation & Feed Telemetry"]
        Py_API --> Worker
        Worker --> PW
        PW --> Watchdog
        PW --> Emulation
    end

    subgraph Network_Layer ["Instagram Web API"]
        IG_Auth["Session & Cookie Detection"]
        IG_Query["Friendship API (/following, /followers)"]
        IG_Mutate["Official Web Unfollow (POST /api/v1/friendships/destroy/... + verify show)"]
        PW --> IG_Auth
        PW --> IG_Query
        PW --> IG_Mutate
    end

    subgraph Storage_Layer ["Local Persistence (%LOCALAPPDATA%/ZXD44-IG-Cleaner)"]
        WL["localStorage (zx_protected_users)"]
        Audit["unfollow_history.json (Audit Records)"]
        AuditLog["unfollowx_audit.log (Rotating Execution Log)"]
        SessionStore["browser_profile (Persistent Chromium Context)"]
        Py_API --> WL
        Py_API --> Audit
        Py_API --> AuditLog
        PW --> SessionStore
    end
```

---

## 2. Component Breakdown

### 2.1 PyWebView Host (`gui_app.py`)
- **Engine**: Microsoft Edge WebView2 (via `pythonnet` / WinForms) or MSHTML fallback.
- **Window Specs**: Default dimensions 980×640px, minimum 780×520px, centered on launch.
- **UI Flow (v0.0.6+)**: Guided 3-step rail — Login → Scan → Clean. Sidebar shows hero non-follower count + 24h quota meter; main pane shows gate screens or the account list.
- **Always-on-Top Control**: Directly interfaces with Win32 `user32.dll` via `ctypes.windll.user32.SetWindowPos` to avoid WinForms thread synchronization exceptions.
- **RPC Exposure**: `class API` acts as the single boundary between JavaScript and Python.
  - Public methods: `open_browser_window()`, `request_scan()`, `request_unfollow_batch()`, `stop_unfollow()`, `toggle_always_on_top()`, `get_app_state()`, `get_queue_list()`, `clear_queue()`, `resume_pending_queue()`, `set_warmup_mode()`, `open_profile_in_browser()`, `manual_add_targets()`, `get_history()`, `clear_history()`, `open_log_folder()`, `export_data()`.
  - Internal attributes: Prefixed with `_` to prevent PyWebView `get_functions` from traversing into `.NET` / `threading` objects.

### 2.2 Playwright Automation Engine (`BrowserWorker`)
- **Execution Mode**: Dedicated background daemon thread receiving async task closures through a thread-safe Queue.
- **User Data Directory**: `%LOCALAPPDATA%\ZXD44-IG-Cleaner\browser_profile` preserves authenticated Instagram sessions permanently.
- **Stealth Configurations**:
  - `navigator.webdriver` masked to `undefined`.
  - Realistic User-Agent: Chrome on Windows desktop.
  - Simulated human scrolling impressions and Gaussian timing delays.

### 2.3 SQLite Storage & Persistent Queue (`storage_manager.py`)
- **Database**: `%LOCALAPPDATA%\ZXD44-IG-Cleaner\unfollowx.db`
- **Tables**:
  - `unfollow_queue`: Persistent target queue with attempt counters and failure states.
  - `unfollow_history`: Immutable action log recording target ID, username, method (`friendships_destroy`, `web_friendships_unfollow`, `ui_profile`), and timestamps.
  - `scan_snapshots`: Follower and following lists for diff tracking across sessions.
  - `safety_metrics`: Rolling cooldown and trust score values.

### 2.4 Safety Engine & Trust Scoring (`safety_engine.py`)
- Evaluates threat severity across HTTP responses (401, 403, 429, 302, `checkpoint_required`, `spam: true`).
- Dynamically throttles daily quotas based on account warmup state (Warmup: 15/day, Normal: 50/day).
- Enforces exponential backoff and mandatory cooldown timers.

### 2.5 Cooldown Watcher Daemon (`watch_cooldown.py`)
- Runs as a lightweight standalone background watcher.
- Probes `/api/v1/friendships/{id}/following/?count=12` every 10 minutes without invasive load.
- When Instagram clears the 302/spam cooldown: runs a complete diff scan, writes `NON_FOLLOWERS_FOUND.txt` to Desktop and Workspace, and fires a Windows toast notification.

---

## 3. Communication & Workflows

### 3.1 Scanning Workflow with Real-Time Progress

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as gui_template.html
    participant API as Python API
    participant Worker as AutomationWorker
    participant IG as Instagram API

    User->>UI: Click "Scan Followers"
    UI->>API: window.pywebview.api.start_scan()
    API->>Worker: Start thread (action='scan')
    Worker->>Worker: Launch Chromium / Attach Session
    Worker->>IG: Query User Profile (Get Total Followings)
    IG-->>Worker: Return follow_count (e.g., 850)
    
    loop Fetching Pagination (Max 50 per batch)
        Worker->>IG: GET /api/v1/friendships/{id}/following/?max_id={cursor}
        IG-->>Worker: Return batch users + next_max_id
        Worker->>UI: report_scan_progress(current, total, percent)
        UI->>UI: Update progress bar & counter
    end

    Worker->>IG: Fetch Followers set
    Worker->>Worker: Diff: not_following_back = following - followers
    Worker->>API: _cached_scan_data = not_following_back
    Worker->>UI: eval_js: onScanComplete(data)
    UI->>User: Display targets in table
```

### 3.2 Unfollow Execution Engine

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as gui_template.html
    participant API as Python API
    participant Worker as AutomationWorker
    participant IG as Instagram API
    participant Audit as audit_history.json

    User->>UI: Select users & click "Start Unfollow"
    UI->>API: window.pywebview.api.start_unfollow(user_ids, delay, batch_size)
    API->>Worker: Start thread (action='unfollow')
    
    loop For each selected target
        alt Target in Whitelist
            Worker->>UI: Log "Skipped (Whitelisted)"
        else Target Unfollowable
            Worker->>IG: POST /api/v1/friendships/destroy/{id}/
            alt API failed
                Worker->>IG: POST /web/friendships/{id}/unfollow/ or UI profile click
            end
            Worker->>IG: GET /api/v1/friendships/show/{id}/ (verify following=false)
            IG-->>Worker: confirmed unfollowed
            Worker->>Audit: Append record {id, username, timestamp, status, method}
            Worker->>UI: state pull unfollow_progress
            Worker->>Worker: Gaussian delay 35-65s + micro-breaks
        end
    end

    Worker->>UI: eval_js: onUnfollowComplete()
    UI->>User: Play completion chime & show stats
```

---

## 4. Local Storage Schemas

### 4.1 Whitelist (`whitelist.json`)
Stores accounts protected from automated unfollowing.
```json
[
  {
    "pk": "123456789",
    "username": "zirconx_official",
    "full_name": "ZirconX",
    "profile_pic_url": "https://...",
    "added_at": "2026-10-24T20:00:00Z"
  }
]
```

### 4.2 Audit Log (`audit_history.json`)
Maintains an immutable record of all unfollow operations.
```json
[
  {
    "pk": "987654321",
    "username": "spam_account_99",
    "timestamp": "2026-10-24T21:45:12Z",
    "status": "success",
    "error": null
  }
]
```

---

## 5. Scripts & Automation Directory (`scripts/`)

| Script | Purpose |
|---|---|
| `scripts/watch_cooldown.py` | Standalone background watcher probing Instagram friendship cooldown every 90s. When clear, auto-diffs Following vs Followers, writes `NON_FOLLOWERS_FOUND.txt` to Desktop/Workspace, and triggers Windows Toast Notification. |
| `scripts/instant_diff.py` | Instant diff tool for Instagram Data Export ZIP/JSON (`following.json` vs `followers_1.json`). Bypasses all web/API rate limits in 0.01s. |
| `scripts/check_candidates.py` | Direct profile verification checker testing if candidates are followed and follow back. |
| `scripts/set_version.py` | Single Source of Truth version bump & PyInstaller build orchestrator. |

