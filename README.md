# 🚀 UnfollowX PRO v0.0.1 — By ZirconX

> **เครื่องมือตรวจสอบและเลิกติดตามผู้ที่ไม่ติดตามกลับบน Instagram อัตโนมัติ ปลอดภัย 100% ด้วย Python Engine + Playwright + PyWebView**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-0.0.1-purple.svg)](source_code/python_engine/version.py)
[![Architecture](https://img.shields.io/badge/Arch-PyWebView%20%2B%20Playwright-indigo.svg)](.agent/ARCHITECTURE.md)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-emerald.svg)](HOW_TO_USE.txt)

---

## ✨ ไฮไลท์ฟีเจอร์เด่น (Key Features)

* 🎨 **Impeccable Obsidian Dark UI**: หน้ากากแบบ Mini Dashboard ขนาดกะทัดรัด สไตล์กระจกดำหรูหรา ใช้งานลื่นไหล ไม่กินพื้นที่หน้าจอ
* ⚡ **Live Real-time Scan %**: แสดงหลอดความคืบหน้าการสแกนแบบเรียลไทม์ `0% - 100%` จากเบราว์เซอร์ตรงสู่หน้าจอ
* 🛡️ **Zero Freeze / Deadlock Architecture**: แก้ปัญหา WinForms UI Deadlock 100% ด้วย Async Pull State Polling และ Win32 API Isolation
* 📌 **Always-on-Top (โหมดปักหมุด)**: ตรึงหน้าต่างให้อยู่บนสุดตลอดเวลาขณะสลับทำงานอื่น
* 🔊 **Web Audio Synthesizer**: สังเคราะห์เสียงเอฟเฟกต์แจ้งเตือนระดับ Sine Wave สบายหู ไม่ต้องใช้ไฟล์เสียงภายนอก
* 📜 **Audit History & Whitelist**: บันทึกประวัติการเลิกติดตามย้อนหลัง และมีระบบปกป้องเพื่อน/คนสำคัญไม่ให้ถูกเผลอเลิกติดตาม
* 🔐 **100% Account Safety**: ทำงานผ่าน Chrome Profile จริง ไม่ต้องกรอกรหัสผ่านในโปรแกรม และมี Random Jitter Cooldown ป้องกัน Action Block

---

## 🚀 วิธีเริ่มใช้งานอย่างรวดเร็ว (Quick Start)

### วิธีที่ 1: ใช้งานผ่านไฟล์พร้อมรัน (.exe)
1. ดาวน์โหลดหรือเปิดไฟล์ `UnfollowX.exe`
2. กดปุ่ม **"เปิดหน้าต่างล็อกอิน Instagram"** แล้วล็อกอินเข้าบัญชีของคุณตามปกติ
3. เมื่อเข้าฟีดแล้ว ให้กลับมากดปุ่ม **"เริ่มสแกนคนไม่ฟอลกลับ"**
4. ตรวจสอบรายชื่อ เลือกคนที่ต้องการ และกด **"เริ่มเลิกติดตาม"**

### วิธีที่ 2: รันจาก Source Code (สำหรับ Developers)
```powershell
# 1. ติดตั้งไลบรารีที่จำเป็น
pip install -r source_code\python_engine\requirements.txt

# 2. ติดตั้งเบราว์เซอร์ Playwright Chromium
playwright install chromium

# 3. รันโปรแกรม
python source_code\python_engine\gui_app.py
```

---

## 🛠️ ระบบจัดการเวอร์ชันและสั่ง Build (Version Manager)

โปรเจกต์มีสคริปต์ [set_version.py](file:///C:/Users/ZirconX/Desktop/Ads%20Dis/ZirconX-IG-Cleaner-Pro-v3.0/set_version.py) ช่วยซิงค์ข้อมูลเวอร์ชันทุกจุดและคอมไพล์ EXE ใหม่ในคำสั่งเดียว:

```powershell
# ตรวจสอบเวอร์ชันปัจจุบัน
python set_version.py

# อัปเดตเวอร์ชันใหม่
python set_version.py 0.0.2

# อัปเดตเวอร์ชันใหม่พร้อมคอมไพล์ UnfollowX.exe ทันที
python set_version.py 0.0.2 --build
```

---

## 📂 โครงสร้างแฟ้มไฟล์โปรเจกต์ (Repository Structure)

```
ZirconX-IG-Cleaner-Pro-v3.0/
├── LICENSE                            # 📜 MIT License
├── README.md                          # 📖 เอกสารแนะนำโปรเจกต์หลัก (หน้านี้)
├── HOW_TO_USE.txt                     # 📖 คู่มือการใช้งานสำหรับผู้ใช้ทั่วไป
├── set_version.py                     # ⚡ เครื่องมือจัดการเวอร์ชันอัตโนมัติ
├── .gitignore                         # กำหนดไฟล์ที่ไม่ต้อง push ขึ้น Git
├── .agent/                            # 🤖 เอกสารเชิงลึกสำหรับ Developer & AI Agent
│   ├── README.md                      # สารบัญเอกสาร
│   ├── RULES.md                       # กฎเหล็กความปลอดภัย JS Bridge, Win32, Rate Limits
│   ├── ARCHITECTURE.md                # แผนผังสถาปัตยกรรมระบบ, Workflows, Schemas
│   └── GUIDE.md                       # คู่มือการทดสอบ, การดีบั๊ก, และการแก้ปัญหา
└── source_code/                       # 💻 ซอร์สโค้ดของระบบทั้งหมด
    ├── README.md                      # เอกสารซอร์สโค้ด
    └── python_engine/
        ├── gui_app.py                 # Core Controller (Playwright + PyWebView)
        ├── gui_template.html          # Obsidian Dark Minimalist Interface
        ├── version.py                 # Single Source of Truth สำหรับเวอร์ชัน
        ├── version_info.txt           # Windows Executable File Metadata
        ├── set_version.py             # Script ซิงค์เวอร์ชันของ Engine
        ├── build_gui_exe.spec         # PyInstaller Configuration
        └── requirements.txt           # Python Dependencies
```

---

## ⚖️ ข้อกำหนดและการใช้งานอย่างปลอดภัย (Disclaimer)

โปรเจกต์นี้พัฒนาขึ้นเพื่อการศึกษาและการจัดระเบียบบัญชีส่วนตัวเท่านั้น กรุณาใช้งานตามขีดจำกัดที่ปลอดภัย (แนะนำเลิกติดตามไม่เกิน 100-150 บัญชีต่อวัน และตั้งค่าหน่วงเวลา 15-35 วินาทีขึ้นไป) ผู้พัฒนาไม่รับผิดชอบต่อการนำไปใช้งานที่ผิดข้อกำหนดการใช้งานของแพลตฟอร์ม

---

## 📄 ใบอนุญาต (License)

โปรเจกต์นี้เผยแพร่ภายใต้ใบอนุญาต [MIT License](LICENSE)
