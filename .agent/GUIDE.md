# User & Operations Guide: UnfollowX PRO

This document covers end-user operations, developer workflows, and troubleshooting procedures for **UnfollowX PRO**.

---

## 1. Quick Start Guide

### 1.1 Running the Prebuilt Binary
1. Double-click `UnfollowX.exe`.
2. The mini GUI dashboard opens in dark obsidian mode.
3. If not already logged in, click **"Open Instagram Login"** (headed Chromium window opens).
4. Log into Instagram normally (handles 2FA, OTP, and captcha).
5. Once logged in and on the feed, return to UnfollowX and click **"Scan Non-Followers"**.
6. The scanning progress bar updates dynamically (`0%` to `100%`).
7. Review the list of accounts not following you back.
8. Protect important friends or creators by clicking **"Whitelist"** (`🛡️`).
9. Select targets and click **"Start Batch Unfollow"**.

---

## 2. Developer Operations

### 2.1 Running from Source
Ensure Python 3.10+ is installed on Windows:
```powershell
# 1. Navigate to engine directory
cd "source_code\python_engine"

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Ensure Playwright Chromium browser is installed
playwright install chromium

# 4. Launch GUI application
python gui_app.py
```

### 2.2 Version Management & 1-Command Build
The project provides a single-source-of-truth version management tool `scripts/set_version.py`:

```powershell
# Check current version
python scripts/set_version.py

# Update version across all config files (version.py, version_info.txt, docs)
python scripts/set_version.py 0.0.9

# Update version AND compile new UnfollowX.exe in one command
python scripts/set_version.py 0.0.9 --build
```

### 2.3 Automation & Utility Scripts (`scripts/`)
- **Cooldown Watcher**:
  ```powershell
  python scripts/watch_cooldown.py
  ```
  Monitors Instagram friendship endpoint cooldown every 90 seconds. Once lifted, performs a full diff and writes `NON_FOLLOWERS_FOUND.txt` to Desktop.
- **Instant Data Export Diff**:
  ```powershell
  python scripts/instant_diff.py "path_to_instagram_export.zip"
  ```
  Compares followers vs following directly from Instagram JSON export in 0.01 seconds without triggering API rate limits.

### 2.4 Manual PyInstaller Build (Optional)
If compiling manually without `set_version.py`:
```powershell
# 1. Navigate to engine directory
cd "source_code\python_engine"

# 2. Run PyInstaller build
python -m PyInstaller build_gui_exe.spec --noconfirm

# 3. Deploy output binary to project root
Copy-Item "dist\UnfollowX.exe" "..\..\UnfollowX.exe" -Force
```

---

## 3. Advanced Features

### 3.1 Always-on-Top (📌 Pin)
- Clicking the pin icon in the top header toggles the window to stay above all other applications.
- Implemented via direct Win32 `SetWindowPos` call (`HWND_TOPMOST`), safe from UI thread deadlocks.

### 3.2 Synthesized Web Audio
- Uses browser Web Audio API oscillator synthesis.
- Plays distinct sine waves:
  - High pitch double-beep on completion.
  - Low warning pulse on errors or block warnings.
  - Zero external MP3/WAV files required.

### 3.3 Audit History & Persistent Execution Logs (📋 Logs)
- View past unfollow actions directly in the app.
- Check real-time execution logs by clicking **"📋 Logs"** in the top header, which opens `%LOCALAPPDATA%\ZXD44-IG-Cleaner\`.
- Inspect `unfollowx_audit.log` for timestamps, stealth hooks, watchdog events, and API response codes.

---

## 4. Troubleshooting & FAQ

### Issue 1: App freezes or shows "Not Responding"
- **Cause**: Attribute name collision in `API` exposing native WinForms objects to PyWebView's recursive inspection.
- **Fix**: Verify in `gui_app.py` that all attributes and non-RPC methods on `class API` begin with `_`.

### Issue 2: Action Blocked / Challenge Required on Instagram
- **Cause**: Unfollowing too fast or exceeding Instagram's heuristic spam thresholds.
- **Remedy**:
  1. UnfollowX v0.0.5's Circuit Breaker halts immediately upon detection.
  2. Inspect `%LOCALAPPDATA%\ZXD44-IG-Cleaner\unfollowx_audit.log` to see the exact trigger.
  3. If account is locked, **use the Instagram Mobile App on 4G/5G** to verify email/SMS and reset password (do not use desktop web to avoid the Facebook 500 error).
  4. Wait 24-48 hours before resuming any automation to allow trust scores to normalize.
  5. Use only **Ultimate Safe Mode (35-65s)** with batches of ≤ 15 accounts.

### Issue 3: Daily Quota Locked (50/50)
- **Cause**: The application reached its hard safety limit of 50 unfollows in a rolling 24-hour window.
- **Remedy**: Wait until earlier actions exit the 24-hour window. This is a deliberate safety mechanism to prevent Instagram bot bans.

### Issue 4: Action Cooldown (302 Redirect / "spam": true)
- **Cause**: Instagram temporarily throttled the friendship listing endpoint (`/api/v1/friendships/...`) due to rapid recent scan or unfollow actions.
- **Behavior**:
  - Web requests return HTTP 302 Found (redirecting to `/`).
  - Mobile requests return HTTP 400 with `{"message":"","spam":true,"status":"fail"}`.
  - The profile header displays counts normally, but the following modal shows: *"Once you follow people, you'll see them here."*
- **Remedy**:
  1. **Do not spam scan attempts**: This prolongs Meta's cooldown timer.
  2. **Use Manual Mode**: Click **"📝 ข้ามไปจัดการรายชื่อเอง (Manual Mode)"** or **"➕ เพิ่มชื่อเอง"** in UnfollowX to enter the workspace immediately.
  3. **Direct Profile 1-Click Jump**: In the table or manual modal, click **"🌐 ดูโปรไฟล์"** to open Chrome at that target's profile to unfollow manually without triggering API rate limits.
  4. **Automated Background Watcher**: Run `python watch_cooldown.py` (or let the background daemon run). It probes every 10 minutes, and the second Instagram clears the block, it will scan all non-followers, write them to `NON_FOLLOWERS_FOUND.txt` on Desktop, and trigger a Windows notification.
