"""SQLite persistence for krish — chat memory and activity logs.

Uses the stdlib sqlite3 module with a single db file at data/krish.db.
Tables are created on import if they don't already exist.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "krish.db"


def _now() -> str:
    """Current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                role    TEXT,
                content TEXT,
                ts      TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                activity TEXT,
                app      TEXT,
                seconds  INTEGER,
                ts       TEXT
            )
            """
        )


def save_message(role: str, content: str) -> None:
    """Persist a single chat message."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (role, content, ts) VALUES (?, ?, ?)",
            (role, content, _now()),
        )


def recent_messages(limit: int = 20) -> list[dict]:
    """Return the most recent messages in chronological (oldest-first) order."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, role, content, ts FROM messages ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def save_log(activity: str, app: str | None = None, seconds: int | None = None) -> None:
    """Persist an activity log entry."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO logs (activity, app, seconds, ts) VALUES (?, ?, ?, ?)",
            (activity, app, seconds, _now()),
        )


def recent_logs(limit: int = 50) -> list[dict]:
    """Return the most recent activity logs in chronological (oldest-first) order."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, activity, app, seconds, ts FROM logs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_logs(since: str | None = None) -> list[dict]:
    """Return activity logs, optionally only those with ts >= `since` (ISO string)."""
    with _connect() as conn:
        if since is None:
            rows = conn.execute(
                "SELECT id, activity, app, seconds, ts FROM logs ORDER BY id"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, activity, app, seconds, ts FROM logs "
                "WHERE ts >= ? ORDER BY id",
                (since,),
            ).fetchall()
    return [dict(r) for r in rows]


# Ensure tables exist as soon as the module is imported.
init_db()
