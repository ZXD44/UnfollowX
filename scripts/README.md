# UnfollowX - Utility & Automation Scripts (`scripts/`)

โฟลเดอร์สำหรับจัดเก็บสคริปต์เสริม เครื่องมือทดสอบ และระบบเฝ้าระวังอัตโนมัติของ UnfollowX

---

## 🛠️ รายการสคริปต์ในโฟลเดอร์

| ชื่อไฟล์ | วัตถุประสงค์การใช้งาน |
|---|---|
| `watch_cooldown.py` | สคริปต์เฝ้าระวัง Action Cooldown ของ Instagram อัตโนมัติ (ตรวจทุก 90 วินาที) เมื่อปลดล็อกจะสแกนและดึงรายชื่อที่ไม่ฟอลกลับบันทึกลง Desktop ทันที |
| `instant_diff.py` | สคริปต์เปรียบเทียบ Followers vs Following จากไฟล์ Instagram Data Export (`.zip` หรือ `.json`) ทันทีใน 0.01 วินาที โดยไม่ต้องรอ Cooldown |
| `check_candidates.py` | สคริปต์ตรวจสอบสถานะการฟอลโลว์ของรายชื่อผู้ใช้ที่ระบุ |
| `find_graphql.py` | สคริปต์ดักจับและวิเคราะห์โมดูล JavaScript / GraphQL ของ Instagram Web |
| `test_graphql.py` | เครื่องมือทดสอบการยิง GraphQL Queries บนหน้าโปรไฟล์ |
| `test_graphql_hashes.py` | ทดสอบ Query Hashes / Persisted Queries ของ Instagram |
| `test_fetch.py` | ทดสอบการดึงข้อมูล Endpoint ต่างๆ ของ Instagram ผ่าน Playwright Session |
| `test_db.py` | ตรวจสอบโครงสร้างและข้อมูลในฐานข้อมูล SQLite (`unfollowx.db`) |
| `set_version.py` | สคริปต์เปลี่ยนเวอร์ชัน สร้าง Release Body และอัปเดตเวอร์ชันโปรเจกต์ |

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
