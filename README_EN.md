<div align="right">
  <strong>🌐 Language / ภาษา:</strong>
  <a href="README.md">🇹🇭 ภาษาไทย (หลัก)</a> |
  <a href="README_EN.md"><strong>🇬🇧 English</strong></a>
</div>

# 🚀 UnfollowX PRO v0.0.1 — By ZirconX

> **Automated, safe, and modern Instagram Non-Follower Cleaner powered by Python Engine + Playwright + PyWebView**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-0.0.1-purple.svg)](source_code/python_engine/version.py)
[![Architecture](https://img.shields.io/badge/Arch-PyWebView%20%2B%20Playwright-indigo.svg)](.agent/ARCHITECTURE.md)
[![Language](https://img.shields.io/badge/Language-TH%20%7C%20EN-blue.svg)](README.md)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-emerald.svg)](HOW_TO_USE.txt)

---

## ✨ Key Features

* 🌐 **Bilingual System (Thai & English)**: Toggle between `🇹🇭 TH` and `🇬🇧 EN` instantly with persistent language memory (Thai default).
* 🎨 **Impeccable Obsidian Dark UI**: Compact, high-density mini dashboard inspired by [impeccable.style](https://impeccable.style/).
* ⚡ **Live Real-time Scan %**: Real-time progress bar streaming directly from the browser context (`0% - 100%`).
* 🛡️ **Zero Freeze / Deadlock Architecture**: Resolves WinForms UI deadlocks with async pull state polling and Win32 API isolation.
* 📌 **Always-on-Top Window Pinning**: Keep the window floating above other windows while multitasking.
* 🔊 **Web Audio Synthesizer**: Pure sine-wave feedback sounds with zero external audio dependencies.
* 📜 **Audit History & Whitelist**: Keep track of all unfollow actions and protect important creators/friends with 1-click protection.
* 🔐 **100% Account Safety**: Uses actual persistent Chromium user data. Never requires passwords inside the app; features randomized jitter delays to prevent Instagram Action Blocks.

---

## 🚀 Quick Start Guide

### Method 1: Pre-compiled Executable (.exe)
1. Download or launch `UnfollowX.exe`.
2. Click **"Chrome"** to open the browser and log in to Instagram normally (handles 2FA, OTP, and captcha).
3. Once logged in, return to UnfollowX and click **"Scan"**.
4. Review the detected non-followers list, protect accounts if needed (`🛡️`), and click **"1-Click Clean"** or **"Unfollow Selected"**.

### Method 2: Run from Source (For Developers)
```powershell
# 1. Install dependencies
pip install -r source_code\python_engine\requirements.txt

# 2. Install Playwright Chromium
playwright install chromium

# 3. Launch application
python source_code\python_engine\gui_app.py
```

---

## 🛠️ Version Manager & Build Automation

UnfollowX includes a single-source-of-truth version management tool [set_version.py](file:///C:/Users/ZirconX/Desktop/Ads%20Dis/ZirconX-IG-Cleaner-Pro-v3.0/set_version.py):

```powershell
# Check current version
python set_version.py

# Bump version across all files
python set_version.py 0.0.2

# Bump version AND build executable in one single command
python set_version.py 0.0.2 --build
```

---

## 📂 Repository Structure

```
ZirconX-IG-Cleaner-Pro-v3.0/
├── LICENSE                            # 📜 MIT License
├── README.md                          # 📖 Main Documentation (Thai - Default)
├── README_EN.md                       # 📖 English Documentation (This file)
├── HOW_TO_USE.txt                     # 📖 User Quick Guide (Bilingual TH / EN)
├── set_version.py                     # ⚡ Version Manager & Build CLI
├── .gitignore                         # Git exclusion rules
├── .agent/                            # 🤖 Internal System Rules & Architecture
│   ├── README.md                      # Directory index
│   ├── RULES.md                       # Security, Threading & Bridge constraints
│   ├── ARCHITECTURE.md                # System diagrams & Data workflows
│   └── GUIDE.md                       # Testing, building & debugging guide
└── source_code/                       # 💻 Complete source code
    ├── README.md                      # Source code overview
    └── python_engine/
        ├── gui_app.py                 # Core Controller (Playwright + PyWebView)
        ├── gui_template.html          # Obsidian Dark Mini UI (i18n engine)
        ├── version.py                 # Single Source of Truth for version
        ├── version_info.txt           # Windows Executable metadata
        ├── set_version.py             # Engine version sync script
        ├── build_gui_exe.spec         # PyInstaller Spec
        └── requirements.txt           # Python dependencies
```

---

## ⚖️ Disclaimer

This software is developed strictly for educational and personal account organization purposes. Always abide by Instagram's terms of service. Recommended daily unfollow limit: 100-150 accounts with 15-35s delays. The developers assume no liability for misuse.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
