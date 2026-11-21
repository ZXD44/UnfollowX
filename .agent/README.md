# .agent Directory Index (สารบัญคู่มือระบบ)

Welcome to the internal system and agentic documentation directory for **UnfollowX PRO v0.0.9** (Bilingual TH / EN).

## User & Public Documentation
- [README.md (🇹🇭 ภาษาไทย & 🇬🇧 English)](file:///C:/Users/ZirconX/Documents/UnfollowX/README.md): เอกสารแนะนำโปรเจกต์ฉบับสมบูรณ์ (รวมภาษาไทยและภาษาอังกฤษในไฟล์เดียว)
- [HOW_TO_USE.txt](file:///C:/Users/ZirconX/Documents/UnfollowX/HOW_TO_USE.txt): คู่มือการใช้งานสำหรับผู้ใช้ทั่วไป

## Developer & Agent Specifications
- [WORKFLOW.md](file:///C:/Users/ZirconX/Documents/UnfollowX/.agent/WORKFLOW.md): ขั้นตอนการทำงานและแนวทางปฏิบัติมาตรฐานทั้งหมด (SOPs, Lifecycle, Code & Documentation Standards).
- [RULES.md](file:///C:/Users/ZirconX/Documents/UnfollowX/.agent/RULES.md): กฎเหล็กความปลอดภัย (PyWebView bridge safety, thread safety, rate limits, UI standards).
- [ARCHITECTURE.md](file:///C:/Users/ZirconX/Documents/UnfollowX/.agent/ARCHITECTURE.md): แผนผังสถาปัตยกรรมระบบ, Workflows, Schemas.
- [GUIDE.md](file:///C:/Users/ZirconX/Documents/UnfollowX/.agent/GUIDE.md): คู่มือการทดสอบ, การดีบั๊ก, และการแก้ปัญหา.

## Key Subsystems & Utilities
- **`scripts/watch_cooldown.py`**: Background daemon monitoring Instagram 302/spam cooldown (every 90s) and generating `NON_FOLLOWERS_FOUND.txt`.
- **`scripts/instant_diff.py`**: Instant diff tool comparing Instagram Data Export ZIP/JSON (`following.json` vs `followers_1.json`) in 0.01s.
- **`scripts/check_candidates.py`**: Verification script checking follow & followback status for target accounts.
- **`scripts/set_version.py`**: Single Source of Truth version manager & build tool.
- **`storage_manager.py`**: SQLite persistent queue, audit history, and diff scan snapshot storage (`unfollowx.db`).
- **`safety_engine.py`**: Adaptive trust scoring, rate limiting, and circuit breaker heuristics.
- **`notifier.py`**: Windows native toast notification integration via PowerShell WinForms.
