import sqlite3
import json
from datetime import datetime

DB_PATH = "opdivo_reports.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


MODEL_FAST = "grok-4-1-fast-reasoning"
MODEL_FLAGSHIP = "grok-4.20-reasoning"


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS reports (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date      TEXT NOT NULL,
            raw_json      TEXT NOT NULL,
            summary       TEXT,
            model_version TEXT
        );
    """)
    # Non-destructive migration: add column if it doesn't exist yet
    try:
        conn.execute("ALTER TABLE reports ADD COLUMN model_version TEXT")
        conn.commit()
    except Exception:
        pass  # column already exists
    conn.close()
    print("Database initialised.")


def save_report(raw_json: dict, summary: str, model_version: str = MODEL_FAST):
    conn = get_db()
    conn.execute(
        "INSERT INTO reports (run_date, raw_json, summary, model_version) VALUES (?, ?, ?, ?)",
        (datetime.now().isoformat(), json.dumps(raw_json), summary, model_version),
    )
    conn.commit()
    conn.close()


def get_latest_report(model_version: str | None = None) -> dict | None:
    """Return the most-recent report, optionally filtered by model_version."""
    conn = get_db()
    if model_version:
        row = conn.execute(
            "SELECT * FROM reports WHERE model_version = ? ORDER BY run_date DESC LIMIT 1",
            (model_version,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM reports ORDER BY run_date DESC LIMIT 1"
        ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_reports() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT id, run_date, summary, model_version FROM reports ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_report_by_id(report_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM reports WHERE id = ?", (report_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None
