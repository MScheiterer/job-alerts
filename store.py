import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "seen_jobs.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen_jobs (
            job_id TEXT PRIMARY KEY,
            company TEXT,
            title TEXT,
            first_seen TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    return conn


def filter_new(conn, jobs):
    new_jobs = []
    for job in jobs:
        row = conn.execute("SELECT 1 FROM seen_jobs WHERE job_id = ?", (job["id"],)).fetchone()
        if row is None:
            new_jobs.append(job)
    return new_jobs


def mark_seen(conn, jobs):
    conn.executemany(
        "INSERT OR IGNORE INTO seen_jobs (job_id, company, title) VALUES (?, ?, ?)",
        [(j["id"], j["company"], j["title"]) for j in jobs],
    )
    conn.commit()
