"""
db.py — SQLite persistence layer for Opdivo Biosimilar Surveillance.

═══════════════════════════════════════════════════════════════════════
  DATA-SAFETY GUARANTEE — READ BEFORE MODIFYING THIS FILE
═══════════════════════════════════════════════════════════════════════
  • This database is designed to preserve ALL historical reports forever.
  • Every surveillance run APPENDS a new row — old rows are NEVER deleted.
  • `init_db()` uses CREATE TABLE IF NOT EXISTS — it NEVER drops or
    recreates tables, so existing data survives every code update and
    every redeploy (Railway, local, or any other environment).
  • Schema migrations MUST use `_safe_add_column()` (ALTER TABLE … ADD
    COLUMN) — never DROP COLUMN, never recreate the table.
  • There are NO DELETE, DROP TABLE, or TRUNCATE statements anywhere in
    this file or in agent.py / main.py.

  Railway note:
    SQLite writes to a file on disk.  On Railway, mount a persistent
    Volume at the path where opdivo_reports.db lives (e.g. /data) and
    set DB_PATH = "/data/opdivo_reports.db" via an environment variable.
    Without a persistent Volume the file resets on every deploy.
    The code itself is safe; the deployment infra must mount the Volume.
═══════════════════════════════════════════════════════════════════════
"""

import os
import sqlite3
import json
from datetime import datetime

# Allow overriding the DB path via environment variable so Railway (or any
# other host) can point to a persistent Volume mount without code changes.
DB_PATH = os.environ.get("DB_PATH", "opdivo_reports.db")

MODEL_FAST = "grok-4.20-reasoning"
MODEL_FLAGSHIP = "grok-4.20-reasoning"


def get_db() -> sqlite3.Connection:
    """Open (or create) the SQLite database with safe, performance-friendly settings.

    WAL mode is used so reads never block writes and writes never block reads —
    critical when the Streamlit UI is reading while the agent thread is writing.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL journal: concurrent reads + writes without blocking each other.
    conn.execute("PRAGMA journal_mode=WAL")
    # Synchronous=NORMAL is safe with WAL and much faster than FULL.
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _safe_add_column(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    """Add a column to a table only if it does not already exist.

    This is the ONLY approved way to extend the schema.  Never drop or
    recreate a table to add a column — that would destroy all existing data.
    """
    existing = {
        row[1].lower()
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column.lower() not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        conn.commit()


def init_db() -> None:
    """Initialise the database schema.

    Safe to call on every startup:
      • CREATE TABLE IF NOT EXISTS — never drops existing tables.
      • _safe_add_column() — never drops existing columns.
      • No DELETE, DROP, or TRUNCATE operations.
    All historical reports are preserved across every call.
    """
    conn = get_db()
    # Create the reports table if it does not already exist.
    # NEVER use DROP TABLE or CREATE TABLE (without IF NOT EXISTS) here.
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS reports (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date      TEXT NOT NULL,
            raw_json      TEXT NOT NULL,
            summary       TEXT,
            model_version TEXT
        );
    """)
    # Non-destructive migrations — add any new columns that older DB files lack.
    _safe_add_column(conn, "reports", "model_version", "TEXT")
    conn.close()
    print(f"Database initialised (path={DB_PATH}).")


def save_report(raw_json: dict, summary: str, model_version: str = MODEL_FAST) -> int:
    """INSERT a new report row and return its id.

    APPEND-ONLY: this function never modifies or deletes existing rows.
    Every surveillance run produces exactly one new row.
    """
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO reports (run_date, raw_json, summary, model_version) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(), json.dumps(raw_json), summary, model_version),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_latest_report(model_version: str | None = None) -> dict | None:
    """Return the most-recent report row, optionally filtered by model_version.

    Read-only — never modifies any data.
    """
    conn = get_db()
    try:
        if model_version:
            row = conn.execute(
                "SELECT * FROM reports WHERE model_version = ? ORDER BY run_date DESC LIMIT 1",
                (model_version,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM reports ORDER BY run_date DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_all_reports() -> list[dict]:
    """Return all reports ordered newest-first (id, run_date, summary, model_version only).

    Read-only — never modifies any data.
    """
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, run_date, summary, model_version FROM reports ORDER BY id DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_report_by_id(report_id: int) -> dict | None:
    """Return the full report row for the given id, or None if not found.

    Read-only — never modifies any data.
    """
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_reports_by_date(run_date: str) -> list[dict]:
    """Return all full report rows for a given run_date prefix (YYYY-MM-DD).

    Read-only — never modifies any data.
    """
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM reports WHERE run_date LIKE ? ORDER BY id DESC",
            (run_date + "%",),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_report_count() -> int:
    """Return the total number of stored reports.

    Useful for health-checks and Railway deployment verification — if this
    returns > 0 after a redeploy, the persistent Volume is working correctly.
    """
    conn = get_db()
    try:
        row = conn.execute("SELECT COUNT(*) FROM reports").fetchone()
        return row[0] if row else 0
    finally:
        conn.close()
