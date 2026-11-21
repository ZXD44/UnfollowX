# 🚀 UnfollowX PRO v0.0.8 — By ZXD44

> **เครื่องมือตรวจสอบและเลิกติดตามผู้ที่ไม่ติดตามกลับบน Instagram อัตโนมัติ ปลอดภัย 100% ด้วย Python Engine + Playwright + PyWebView**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](../LICENSE)
[![Version](https://img.shields.io/badge/Version-0.0.8-purple.svg)](python_engine/version.py)
[![Author](https://img.shields.io/badge/Creator-ZXD44-f43f5e.svg)](https://github.com/ZXD44)
[![GitHub](https://img.shields.io/badge/GitHub-ZXD44%2FUnfollowX-indigo.svg)](https://github.com/ZXD44/UnfollowX)

---

## 📂 โครงสร้างแฟ้มไฟล์โปรเจกต์ (Project Structure)

```
UnfollowX/
├── UnfollowX.exe                      # 🚀 โปรแกรมหลักพร้อมใช้งานทันที (Standalone Windows Executable)
├── HOW_TO_USE.txt                     # 📖 คู่มือวิธีใช้งานฉบับย่อสำหรับผู้ใช้ทั่วไป
├── set_version.py                     # ⚡ เครื่องมือจัดการเวอร์ชันและสั่ง Build อัตโนมัติใน 1 คำสั่ง
├── watch_cooldown.py                  # 🛰️ สคริปต์ตรวจจับ Cooldown เบื้องหลังอัตโนมัติ
├── .gitignore                         # ไฟล์ตัดขยะและแคชออกจากการเก็บไฟล์
├── .agent/                            # 🤖 เอกสารเชิงลึกสำหรับ Agent และ Developers
│   ├── README.md                      # สารบัญเอกสาร
│   ├── RULES.md                       # กฎเหล็กด้านความปลอดภัย (JS Bridge, Threading, Rate Limits)
│   ├── ARCHITECTURE.md                # แผนผังสถาปัตยกรรมระบบ, Workflows, Schemas
│   └── GUIDE.md                       # คู่มือการพัฒนา, การทดสอบ, และการแก้ปัญหา
└── source_code/                       # 💻 โค้ดต้นฉบับทั้งหมด
    ├── LICENSE                        # MIT License
    ├── README.md                      # เอกสารนี้
    └── python_engine/
        ├── gui_app.py                 # ตัวควบคุมหลัก (Playwright + PyWebView Native Bridge)
        ├── gui_template.html          # หน้ากาก Obsidian Dark Glassmorphic UI (Impeccable Style)
        ├── storage_manager.py         # จัดการ Persistent Queue และ SQLite Database (unfollowx.db)
        ├── safety_engine.py           # คำนวณ Trust Score, Rate Limit และ Watchdog Heuristics
        ├── notifier.py                # ระบบยิง Windows Native Toast Notification
        ├── version.py                 # Single Source of Truth สำหรับเลขเวอร์ชัน
        ├── version_info.txt           # Windows Executable FileVersion Metadata
        ├── set_version.py             # สคริปต์ Engine สำหรับซิงค์เวอร์ชัน
        ├── build_gui_exe.spec         # คอนฟิก PyInstaller Spec สำหรับคอมไพล์
        └── requirements.txt           # รายการไลบรารีที่จำเป็น
```

---

## 🛠️ วิธีการพัฒนาและบิลด์ (Development & Build)

### 1. ติดตั้ง Dependencies (ทำครั้งแรกครั้งเดียว)
```powershell
pip install -r source_code\python_engine\requirements.txt
playwright install chromium
```

### 2. รันโปรแกรมในโหมดทดสอบ (Development Mode)
```powershell
python source_code\python_engine\gui_app.py
```

### 3. การอัปเดตเวอร์ชันและ Build EXE ใหม่
ใช้เครื่องมือ `set_version.py` ที่โฟลเดอร์ root ได้ทันที:
```powershell
# ซิงค์เวอร์ชันทุกไฟล์ และสั่ง Compile เป็น UnfollowX.exe อัตโนมัติ:
python set_version.py 0.0.8 --build
```
*ระบบจะอัปเดตทั้งโค้ด, metadata, หน้า UI, และเอกสาร พร้อมคอมไพล์และวางไฟล์ `UnfollowX.exe` ไว้ที่โฟลเดอร์หลักให้โดยอัตโนมัติ*

---

## 🛡️ สถาปัตยกรรมและความปลอดภัย (Core Safety Highlights)

1. **JS Bridge Recurse-Proof Architecture**: ป้องกัน WinForms `.NET` recursive inspection trap ด้วยการ prefix ตัวแปรภายในด้วย `_` 100% ทำให้แอปตอบสนองลื่นไหล ไม่มีอาการ "Not Responding"
2. **Win32 Native Window Pinning**: ระบบ Always-on-Top (📌) ผ่าน Win32 API `SetWindowPos` ปลอดภัยข้ามเธรด
3. **Sequential In-Session API**: ดึง Following และ Followers แบบเรียงลำดับพร้อม Progress % แบบเรียลไทม์
4. **Adaptive Rate Limiting & Cooldown**: Unfollow ผ่าน `friendships/destroy` + verify `friendships/show`, Gaussian delay 35–65s, micro-break ทุก 4–6 คน, หยุดอัตโนมัติเมื่อ fail ติดกัน 3 ครั้ง
5. **Manual Mode & 1-Click Profile Jump**: จัดการรายชื่อด้วยตนเอง เพิ่มและตรวจสอบ Username โดยตรง และคลิกเปิดหน้าโปรไฟล์ในเบราว์เซอร์จริงเพื่อกดยกเลิกการติดตามเองได้ 1-Click ทันที แม้ติด Cooldown สแกน
6. **Automated Cooldown Watcher Daemon**: สคริปต์ `watch_cooldown.py` เฝ้าตรวจจับ Cooldown 302/Spam ในเบื้องหลัง เมื่อปลดล็อกจะสแกนและสรุปรายชื่อลงไฟล์บน Desktop พร้อมยิง Toast Notification ทันที
