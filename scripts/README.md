# UnfollowX - Utility & Automation Scripts (`scripts/`)

โฟลเดอร์สำหรับจัดเก็บสคริปต์เสริม ระบบเฝ้าระวังอัตโนมัติ และเครื่องมือทดสอบของ UnfollowX

---

## 🛠️ สคริปต์ใช้งานหลัก (`scripts/`)

| ชื่อไฟล์ | วัตถุประสงค์การใช้งาน |
|---|---|
| `watch_cooldown.py` | สคริปต์เฝ้าระวัง Action Cooldown ของ Instagram อัตโนมัติ เมื่อปลดล็อกจะสแกนและดึงรายชื่อที่ไม่ฟอลกลับบันทึกลง Desktop ทันที |
| `instant_diff.py` | สคริปต์เปรียบเทียบ Followers vs Following จากไฟล์ Instagram Data Export (`.zip` หรือ `.json`) ทันทีใน 0.01 วินาที โดยไม่ต้องรอ Cooldown |
| `check_candidates.py` | สคริปต์ตรวจสอบสถานะการฟอลโลว์ของรายชื่อผู้ใช้ที่ระบุ |
| `set_version.py` | สคริปต์อัปเดตเวอร์ชันโปรเจกต์แบบ Single Source of Truth |

---

## 🧪 สคริปต์ทดลองและดีบัก (`scripts/dev/`)

| ชื่อไฟล์ | วัตถุประสงค์การใช้งาน |
|---|---|
| `dev/analyze_snapshot.py` | วิเคราะห์ไฟล์ snapshot ที่บันทึกจากการสแกน |
| `dev/check_show_many.py` | ตรวจสอบจำนวนการแสดงผลรายการบนหน้าเว็บ |
| `dev/find_graphql.py` | ดักจับและวิเคราะห์โมดูล JavaScript / GraphQL ของ Instagram Web |
| `dev/find_last_one.py` | ตรวจสอบตำแหน่งรายการสุดท้ายจากการดึงข้อมูล |
| `dev/test_db.py` | ตรวจสอบโครงสร้างและข้อมูลในฐานข้อมูล SQLite (`unfollowx.db`) |
| `dev/test_fetch.py` | ทดสอบการดึงข้อมูล Endpoint ต่างๆ ของ Instagram ผ่าน Playwright Session |
| `dev/test_graphql.py` | ทดสอบการยิง GraphQL Queries บนหน้าโปรไฟล์ |
| `dev/test_graphql_hashes.py` | ทดสอบ Query Hashes / Persisted Queries ของ Instagram |
| `dev/test_modal_now.py` | ทดสอบการเปิดและดึงข้อมูลจาก Modal รายชื่อ |
| `dev/test_pagination.py` | ทดสอบการแบ่งหน้า (Pagination / `max_id`) |

---

## 🚀 ตัวอย่างคำสั่งใช้งาน

### 1. รันระบบเฝ้าระวัง Cooldown:
```powershell
python scripts/watch_cooldown.py
```

### 2. นำเข้าและเทียบข้อมูลจาก Instagram Data Export:
```powershell
python scripts/instant_diff.py "พาธไฟล์.zip"
```

### 3. ตรวจสอบสถานะบัญชีเป้าหมาย:
```powershell
python scripts/check_candidates.py
```
