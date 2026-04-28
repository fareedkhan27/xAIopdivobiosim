import sqlite3
import json
from datetime import datetime

DB_PATH = "opdivo_reports.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS reports (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date   TEXT NOT NULL,
            raw_json   TEXT NOT NULL,
            summary    TEXT
        );
    """)
    conn.commit()
    conn.close()
    print("Database initialised.")


def save_report(raw_json: dict, summary: str):
    conn = get_db()
    conn.execute(
        "INSERT INTO reports (run_date, raw_json, summary) VALUES (?, ?, ?)",
        (datetime.now().isoformat(), json.dumps(raw_json), summary),
    )
    conn.commit()
    conn.close()


def get_latest_report() -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM reports ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_reports() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT id, run_date, summary FROM reports ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
