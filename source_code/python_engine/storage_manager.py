"""
UnfollowX Core Storage & Database Manager
SQLite-backed persistent queue, history, daily metrics, and diff snapshots.
Explicit context-manager for auto-closing connections cleanly on Windows.
"""

import os
import sqlite3
import json
import time
from datetime import datetime, timedelta
from contextlib import contextmanager

class StorageManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            
            # 1. Unfollow Persistent Queue
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS unfollow_queue (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    full_name TEXT,
                    avatar_url TEXT,
                    is_verified INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending', -- pending, processing, completed, failed, skipped
                    attempts INTEGER DEFAULT 0,
                    last_error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. Audit & Execution History
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS unfollow_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    status TEXT NOT NULL, -- success, failed, skipped
                    method TEXT,
                    reason TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_user_id ON unfollow_history(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_timestamp ON unfollow_history(timestamp)")

            # 3. Follower / Following Snapshots for Diff Scan
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scan_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_type TEXT NOT NULL, -- 'following' or 'followers'
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    full_name TEXT,
                    avatar_url TEXT,
                    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_type_uid ON scan_snapshots(snapshot_type, user_id)")

            # 4. Safety Metrics & Cooldown
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS safety_metrics (
                    key TEXT PRIMARY KEY,
                    val_num REAL,
                    val_text TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 5. Persistent Whitelist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS whitelist (
                    user_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    full_name TEXT,
                    avatar_url TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_whitelist_username ON whitelist(username)")

            conn.commit()

    # --- Queue Operations ---
    def enqueue_targets(self, targets):
        """Add targets to persistent queue if not already pending/completed."""
        added = 0
        with self._connection() as conn:
            cursor = conn.cursor()
            for t in targets:
                u_id = str(t.get("id") or "").strip()
                u_name = str(t.get("username") or "").strip()
                if not u_id or not u_name:
                    continue
                cursor.execute("""
                    INSERT OR IGNORE INTO unfollow_queue (id, username, full_name, avatar_url, is_verified, status)
                    VALUES (?, ?, ?, ?, ?, 'pending')
                """, (
                    u_id,
                    u_name,
                    t.get("full_name", ""),
                    t.get("avatar_url", ""),
                    1 if t.get("is_verified") else 0
                ))
                if cursor.rowcount > 0:
                    added += 1
            conn.commit()
        return added

    def get_pending_queue(self, limit=100):
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, full_name, avatar_url, is_verified, attempts
                FROM unfollow_queue
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_queue_stats(self):
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status, COUNT(*) as cnt
                FROM unfollow_queue
                GROUP BY status
            """)
            stats = {row["status"]: row["cnt"] for row in cursor.fetchall()}
            return {
                "pending": stats.get("pending", 0),
                "completed": stats.get("completed", 0),
                "failed": stats.get("failed", 0),
                "total": sum(stats.values())
            }

    def update_queue_item(self, user_id, status, error=None):
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE unfollow_queue
                SET status = ?, attempts = attempts + 1, last_error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, error, str(user_id)))
            conn.commit()

    def clear_completed_queue(self):
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM unfollow_queue WHERE status IN ('completed', 'skipped')")
            conn.commit()

    def retry_failed_queue(self):
        """Reset all failed queue items back to pending for retry."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE unfollow_queue
                SET status = 'pending', last_error = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE status = 'failed'
            """)
            count = cursor.rowcount
            conn.commit()
            return count

    def clear_all_queue(self):
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM unfollow_queue")
            conn.commit()

    # --- Whitelist Operations ---
    def get_whitelist(self):
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id as id, username, full_name, avatar_url, added_at FROM whitelist ORDER BY added_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def add_to_whitelist(self, user_id, username, full_name="", avatar_url=""):
        u_id = str(user_id or "").strip()
        u_name = str(username or "").strip()
        if not u_id or not u_name:
            return False
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO whitelist (user_id, username, full_name, avatar_url, added_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = CASE WHEN excluded.full_name != '' THEN excluded.full_name ELSE whitelist.full_name END,
                    avatar_url = CASE WHEN excluded.avatar_url != '' THEN excluded.avatar_url ELSE whitelist.avatar_url END
            """, (u_id, u_name, full_name or "", avatar_url or ""))
            cursor.execute("DELETE FROM unfollow_queue WHERE id = ? AND status = 'pending'", (u_id,))
            conn.commit()
        return True

    def remove_from_whitelist(self, user_id):
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM whitelist WHERE user_id = ?", (str(user_id),))
            conn.commit()
            return cursor.rowcount > 0

    def sync_whitelist(self, items):
        """Bulk import whitelist entries (e.g. migrating from localStorage)."""
        rows = [
            (
                str(it.get("id") or it.get("user_id") or "").strip(),
                str(it.get("username") or "").strip(),
                it.get("full_name", ""),
                it.get("avatar_url", "")
            )
            for it in (items or [])
            if str(it.get("id") or it.get("user_id") or "").strip() and str(it.get("username") or "").strip()
        ]
        with self._connection() as conn:
            cursor = conn.cursor()
            if rows:
                cursor.executemany("""
                    INSERT OR IGNORE INTO whitelist (user_id, username, full_name, avatar_url)
                    VALUES (?, ?, ?, ?)
                """, rows)
            conn.commit()
        return len(rows)

    # --- Smart Skip & History Operations ---
    def record_history(self, user_id, username, status, method=None, reason=None):
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO unfollow_history (user_id, username, status, method, reason, timestamp)
                VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))
            """, (str(user_id), str(username), status, method, reason))
            conn.commit()

    def is_recently_processed(self, user_id, days=7):
        """Check if an account was already unfollowed or failed recently within N days."""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM unfollow_history
                WHERE user_id = ? AND timestamp >= ? AND status = 'success'
                LIMIT 1
            """, (str(user_id), cutoff))
            return cursor.fetchone() is not None

    def get_recent_failures_count(self, user_id, days=3):
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as cnt FROM unfollow_history
                WHERE user_id = ? AND timestamp >= ? AND status = 'failed'
            """, (str(user_id), cutoff))
            row = cursor.fetchone()
            return row["cnt"] if row else 0

    def get_24h_history_count(self):
        cutoff = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as cnt FROM unfollow_history
                WHERE timestamp >= ? AND status = 'success'
            """, (cutoff,))
            row = cursor.fetchone()
            return row["cnt"] if row else 0

    def get_audit_history(self, limit=500):
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id as id, username, status, method, reason, timestamp
                FROM unfollow_history
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # --- Safety Metrics Operations ---
    def get_metric(self, key, default_num=None, default_text=None):
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT val_num, val_text FROM safety_metrics WHERE key = ?", (str(key),))
            row = cursor.fetchone()
            if not row:
                return {"val_num": default_num, "val_text": default_text}
            return {
                "val_num": row["val_num"] if row["val_num"] is not None else default_num,
                "val_text": row["val_text"] if row["val_text"] is not None else default_text
            }

    def set_metric(self, key, val_num=None, val_text=None):
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO safety_metrics (key, val_num, val_text, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    val_num = excluded.val_num,
                    val_text = excluded.val_text,
                    updated_at = CURRENT_TIMESTAMP
            """, (str(key), val_num, val_text))
            conn.commit()

    # --- Diff Scan & Snapshots ---
    def save_scan_snapshot(self, snapshot_type, users):
        rows = [
            (
                snapshot_type,
                str(u.get("id") or ""),
                str(u.get("username") or ""),
                u.get("full_name", ""),
                u.get("avatar_url", "")
            )
            for u in users
        ]
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM scan_snapshots WHERE snapshot_type = ?", (snapshot_type,))
            if rows:
                cursor.executemany("""
                    INSERT INTO scan_snapshots (snapshot_type, user_id, username, full_name, avatar_url)
                    VALUES (?, ?, ?, ?, ?)
                """, rows)
            conn.commit()

    def compute_diff(self, current_followers):
        """
        Compare current followers against the latest saved followers snapshot.
        Identify who unfollowed you since last scan.
        """
        curr_ids = {str(u.get("id") or ""): u for u in current_followers if u.get("id")}
        lost_followers = []
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, username, full_name, avatar_url FROM scan_snapshots WHERE snapshot_type = 'followers'")
            previous = cursor.fetchall()
            for row in previous:
                p_id = row["user_id"]
                if p_id and p_id not in curr_ids:
                    lost_followers.append({
                        "id": p_id,
                        "username": row["username"],
                        "full_name": row["full_name"],
                        "avatar_url": row["avatar_url"],
                        "event": "lost_follower"
                    })
        return lost_followers

    def get_last_scan_snapshot(self, snapshot_type):
        """Retrieve the most recent saved snapshot of following or followers."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id as id, username, full_name, avatar_url FROM scan_snapshots WHERE snapshot_type = ?", (snapshot_type,))
            return [dict(row) for row in cursor.fetchall()]

