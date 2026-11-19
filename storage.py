"""
وحدة تخزين بيانات الوظائف (Storage & History)
باستخدام قاعدة بيانات SQLite لتفادي تكرار إرسال الوظائف التي تم فحصها من قبل.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

DB_PATH = Path(__file__).parent / "jobs.db"


class JobStorage:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS seen_jobs (
                    job_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    company TEXT,
                    location TEXT,
                    job_url TEXT NOT NULL,
                    match_score INTEGER DEFAULT 0,
                    is_match INTEGER DEFAULT 0,
                    match_summary TEXT,
                    matching_skills TEXT,
                    missing_skills TEXT,
                    notified INTEGER DEFAULT 0,
                    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notified_at TIMESTAMP
                )
            """)
            conn.commit()

    def is_seen(self, job_id: str) -> bool:
        """فحص ما إذا كانت الوظيفة مسجلة لدينا مسبقاً لمنع التكرار"""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT 1 FROM seen_jobs WHERE job_id = ?", (job_id,))
            return cur.fetchone() is not None

    def is_already_notified(self, job_id: str, company: str = "", title: str = "") -> bool:
        """
        التحقق الصارم من عدم تكرار إرسال الوظيفة للمستخدم:
        1. فحص إذا كان معرف الوظيفة (job_id) أُرسل إشعار عنه مسبقاً (notified = 1).
        2. فحص تطابق اسم الشركة والمسمى الوظيفي لمنع التكرار حتى لو قامت الشركة بإعادة نشر الوظيفة بمعرف جديد.
        """
        with self._get_connection() as conn:
            # 1. فحص مباشر بالـ job_id
            cur = conn.execute("SELECT 1 FROM seen_jobs WHERE job_id = ? AND notified = 1", (job_id,))
            if cur.fetchone() is not None:
                return True

            # 2. فحص تطابق الشركة والمسمى
            if company and title:
                c_clean = company.strip().lower()
                t_clean = title.strip().lower()
                cur = conn.execute(
                    "SELECT 1 FROM seen_jobs WHERE LOWER(company) = ? AND LOWER(title) = ? AND notified = 1",
                    (c_clean, t_clean)
                )
                if cur.fetchone() is not None:
                    return True

        return False

    def save_job(
        self,
        job_id: str,
        title: str,
        company: str,
        location: str,
        job_url: str,
        match_score: int,
        is_match: bool,
        match_summary: str,
        matching_skills: str = "",
        missing_skills: str = "",
        notified: bool = False
    ):
        """حفظ تفاصيل الوظيفة ونتيجة التحليل"""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO seen_jobs (
                    job_id, title, company, location, job_url,
                    match_score, is_match, match_summary,
                    matching_skills, missing_skills, notified,
                    first_seen_at, notified_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                title,
                company,
                location,
                job_url,
                match_score,
                1 if is_match else 0,
                match_summary,
                matching_skills,
                missing_skills,
                1 if notified else 0,
                now,
                now if notified else None
            ))
            conn.commit()

    def mark_as_notified(self, job_id: str):
        """تحديث حالة الوظيفة بأنه تم إرسال إشعار للمستخدم عنها بنجاح"""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE seen_jobs
                SET notified = 1, notified_at = ?
                WHERE job_id = ?
            """, (now, job_id))
            conn.commit()

    def get_stats(self) -> Dict[str, int]:
        """إرجاع إحصائيات سريعة عن الوظائف المسجلة"""
        with self._get_connection() as conn:
            total_seen = conn.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()[0]
            total_matches = conn.execute("SELECT COUNT(*) FROM seen_jobs WHERE is_match = 1").fetchone()[0]
            total_notified = conn.execute("SELECT COUNT(*) FROM seen_jobs WHERE notified = 1").fetchone()[0]
            return {
                "total_seen": total_seen,
                "total_matches": total_matches,
                "total_notified": total_notified
            }

    def get_recent_matches(self, limit: int = 10) -> List[Dict[str, Any]]:
        """جلب آخر الوظائف المتطابقة التي تم العثور عليها"""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT job_id, title, company, location, match_score, match_summary, job_url, notified_at
                FROM seen_jobs
                WHERE is_match = 1
                ORDER BY first_seen_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(row) for row in rows]
