import sqlite3
import os
from typing import List
from .models import Job


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "jobs.db")


class JobDatabase:
    """SQLite database to track seen job postings."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_jobs (
                unique_key TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                url TEXT,
                source TEXT,
                first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scrape_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                company TEXT,
                jobs_found INTEGER,
                new_jobs INTEGER,
                error TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.commit()

    def filter_new_jobs(self, jobs: List[Job]) -> List[Job]:
        """Return only jobs that haven't been seen before."""
        if not jobs:
            return []
        new_jobs = []
        for job in jobs:
            cursor = self.conn.execute(
                "SELECT 1 FROM seen_jobs WHERE unique_key = ?",
                (job.unique_key,),
            )
            if cursor.fetchone() is None:
                new_jobs.append(job)
        return new_jobs

    def mark_as_seen(self, jobs: List[Job]):
        """Mark jobs as seen in the database."""
        if not jobs:
            return
        self.conn.executemany(
            """
            INSERT OR IGNORE INTO seen_jobs (unique_key, title, company, location, url, source)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (j.unique_key, j.title, j.company, j.location, j.url, j.source)
                for j in jobs
            ],
        )
        self.conn.commit()

    def log_scrape(self, source: str, company: str, jobs_found: int, new_jobs: int, error: str = None):
        """Log a scraping run for monitoring."""
        self.conn.execute(
            """
            INSERT INTO scrape_log (source, company, jobs_found, new_jobs, error)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source, company, jobs_found, new_jobs, error),
        )
        self.conn.commit()

    def get_stats(self) -> dict:
        """Get overall stats."""
        total = self.conn.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()[0]
        by_company = self.conn.execute(
            "SELECT company, COUNT(*) FROM seen_jobs GROUP BY company ORDER BY COUNT(*) DESC"
        ).fetchall()
        return {"total_jobs_tracked": total, "by_company": dict(by_company)}

    def close(self):
        self.conn.close()
