# Agent & Developer Rules: UnfollowX PRO

This document governs code modifications, architecture design, and automation constraints for **UnfollowX PRO**. All agents and human contributors must strictly follow these rules.

---

## 1. PyWebView JS Bridge Safety (CRITICAL)

### 1.1 The Recursive Traversal Freeze Trap
PyWebView inspects `window._js_api` by calling internal `get_functions(api)`:
```python
# pywebview/util.py
def get_functions(obj):
    functions = []
    for k in dir(obj):
        if not k.startswith('_'):
            attr = getattr(obj, k)
            if hasattr(attr, '__call__'):
                functions.append((k, attr))
            elif isinstance(attr, object):
                functions.extend([(k + '.' + fn, f) for fn, f in get_functions(attr)])
    return functions
```
- **RULE**: **NEVER** expose any non-underscore property on the `API` class that references complex objects, especially `webview.Window`, `threading.Thread`, or any Python/.NET objects.
- **Why**: Exposing `api.window` causes `get_functions` to crawl into `.NET WinForms` (`window.native.AccessibilityObject.Bounds.Empty...`) leading to `RecursionError: maximum recursion depth exceeded` and a permanent Windows `IsHungAppWindow = 1` freeze ("Not Responding").
- **Mandatory naming convention**:
  - All internal state, handles, and background workers **MUST** start with an underscore `_` (e.g. `_window`, `_worker`, `_cached_scan_data`, `_whitelist_file`).
  - Only genuine RPC methods called by JavaScript should be public methods without leading underscores (e.g. `start_scan()`, `get_stats()`).

### 1.2 WinForms UI Threading Rules
- PyWebView runs on a Windows Forms event loop on the main thread.
- **RULE**: Never mutate WinForms UI properties (such as `window.on_top`) directly from worker threads.
- Direct Win32 API calls via `ctypes.windll.user32.SetWindowPos` using the window handle `HWND` are thread-safe and must be used for window manipulation (e.g. Always-on-Top).
- Use `window.evaluate_js(...)` for pushing asynchronous events to the UI.

---

## 2. Instagram API & Automation Safety Rules

### 2.1 Rate Limiting & Cooldowns
Instagram uses aggressive heuristic spam scoring. Violating limits causes instant account checkpoints or action blocks.
- **Scan Phase**:
  - Max query rate: 1 request every 1.5 - 3.5 seconds.
  - Read-only endpoints: `/api/v1/friendships/{id}/following/` and `/followers/`.
  - Always forward full browser cookies (`sessionid`, `ds_user_id`, `csrftoken`) and headers (`x-ig-app-id: 936619743392459`).
- **Unfollow Phase**:
  - Batch size: 10 - 25 unfollows per batch.
  - Per-action delay: 15 to 35 seconds (randomized with jitter).
  - Batch pause: 5 to 10 minutes between batches.
  - Daily cap: Never exceed 150 - 200 unfollows in a 24-hour window.

### 2.2 Abort Conditions
The automation worker must immediately halt and notify the user if:
1. HTTP 429 (Too Many Requests).
2. HTTP 400 with `checkpoint_required` or `feedback_required`.
3. Response body contains `"spam": true` or `"message": "user_has_logged_out"`.
4. Browser page navigates away from `instagram.com` to a challenge URL (`/challenge/`, `/two_factor/`).

---

## 3. UI/UX Rules (Impeccable Minimalist Standard)

### 3.1 Design Guidelines
- Inspired by [impeccable.style](https://impeccable.style/).
- **Palette**: Obsidian Dark (`#0a0b0e`, `#111318`, `#161922`, `#202533`).
- **Accent**: Indigo/Violet (`#6366f1` / `#818cf8`), Emerald (`#10b981`), Amber (`#f59e0b`), Rose (`#f43f5e`).
- **Compactness**: Compact headers (≤ 38px), dense tables (≤ 34px row height), zero fluff, no wasted whitespace.
- **Offline Self-Containment**: Zero external CDN calls (`unpkg`, `cdnjs`, Google Fonts). All styles, SVG icons, and audio synth must run 100% offline.
- **Bilingual Requirement**: All text elements MUST support both Thai (Primary) and English via the `I18N` engine.

### 3.2 Feedback & Telemetry
- Always provide live progress percentage indicators for long-running tasks.
- Keep audit log history locally in `audit_history.json`.
- Provide synthesized audio feedback (Web Audio API) for critical user actions without audio file assets.

---

## 4. Build & Distribution Rules

### 4.1 PyInstaller Spec Constraints
- Always pack `gui_template.html` and collect `playwright` + `webview` data/submodules.
- Explicitly collect `pythonnet` and `clr` for Windows Forms backend.
- Exclude unnecessary heavy libraries (e.g. `numpy`, `scipy`, `matplotlib`) to keep EXE size under 60MB.
- Embed `version_info.txt` into the EXE specification.
- Output executable name: `UnfollowX.exe`.

---

## 5. Post-Build Version Bump & GitHub Release Protocol (MANDATORY)

Whenever a new version is created or an executable is compiled:
1. **Automated 1-Command Pipeline**:
   The agent or developer MUST run:
   ```powershell
   python set_version.py <version> --build --release
   ```
2. **Mandatory Protocol Requirements**:
   - **Version Sync**: Synchronize version in `version.py`, `version_info.txt`, `HOW_TO_USE.txt`, and `.agent/README.md`.
   - **Standalone Compilation**: Build `UnfollowX.exe` and deploy directly to project root.
   - **Git Commit & Tag**: Commit under author `ZXD44 <zxd44@users.noreply.github.com>` and create tag `v<version>`.
   - **Push to GitHub**: Push commits and tags to `https://github.com/ZXD44/UnfollowX.git`.
   - **GitHub Release Publishing**: Automatically create or update the GitHub Release on `https://github.com/ZXD44/UnfollowX/releases` with rich bilingual (Thai & English) release notes.
   - **Binary Asset Upload**: Upload `UnfollowX.exe` (~51MB) directly to the release assets so users can immediately download and run it without needing Python.
