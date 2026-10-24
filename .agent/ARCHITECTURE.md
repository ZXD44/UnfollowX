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
        PW["Playwright Chromium Context"]
        Py_API --> Worker
        Worker --> PW
    end

    subgraph Network_Layer ["Instagram Web API"]
        IG_Auth["Session & Cookie Detection"]
        IG_Query["Friendship API (/following, /followers)"]
        IG_Mutate["Unfollow Mutation (POST /web/friendships/)"]
        PW --> IG_Auth
        PW --> IG_Query
        PW --> IG_Mutate
    end

    subgraph Storage_Layer ["Local Persistence"]
        WL["whitelist.json"]
        Audit["audit_history.json"]
        SessionStore[".profile_data/ig_user_data"]
        Py_API --> WL
        Py_API --> Audit
        PW --> SessionStore
    end
```

---

## 2. Component Breakdown

### 2.1 PyWebView Host (`gui_app.py`)
- **Engine**: Microsoft Edge WebView2 (via `pythonnet` / WinForms) or MSHTML fallback.
- **Window Specs**: Default dimensions 980×680px, minimum 800×560px, centered on launch.
- **Always-on-Top Control**: Directly interfaces with Win32 `user32.dll` via `ctypes.windll.user32.SetWindowPos` to avoid WinForms thread synchronization exceptions.
- **RPC Exposure**: `class API` acts as the single boundary between JavaScript and Python.
  - Public methods: `open_login()`, `start_scan()`, `stop_scan()`, `start_unfollow()`, `stop_unfollow()`, `toggle_always_on_top()`, `get_whitelist()`, `add_whitelist()`, `remove_whitelist()`, `get_audit_history()`, `clear_audit_history()`.
  - Internal attributes: Prefixed with `_` to prevent PyWebView `get_functions` from traversing into `.NET` / `threading` objects.

### 2.2 Playwright Automation Engine (`AutomationWorker`)
- **Execution Mode**: Runs in a dedicated background daemon thread.
- **User Data Directory**: `.profile_data/ig_user_data` ensures persistent login sessions across restarts without requiring credential entry.
- **Stealth Configurations**:
  - `navigator.webdriver` set to `undefined`.
  - Realistic User-Agent: Chrome 122+ Windows desktop.
  - Natural viewport: 1280×800.
  - Randomized click delays and mouse trajectory simulation.

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
            Worker->>IG: POST /api/v1/web/friendships/{id}/unfollow/
            IG-->>Worker: HTTP 200 {status: "ok"}
            Worker->>Audit: Append record {id, username, timestamp, status}
            Worker->>UI: eval_js: onUnfollowProgress(index, total, user_id)
            Worker->>Worker: Sleep (randomized delay 15-35s)
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
