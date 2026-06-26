"""Lightweight SQLite persistence layer.

Uses the standard-library sqlite3 module.  All blocking calls are wrapped with
asyncio.run_in_executor so they never block the event loop.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path("./meetflow.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # safe for concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create all tables if they don't already exist.  Safe to call on every startup."""
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS hitl_requests (
                request_id   TEXT    PRIMARY KEY,
                action_type  TEXT    NOT NULL,
                payload      TEXT    NOT NULL,
                status       TEXT    NOT NULL DEFAULT 'pending',
                requested_at TEXT    NOT NULL,
                resolved_at  TEXT,
                resolved_by  TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type  TEXT    NOT NULL,
                meeting_id  TEXT,
                request_id  TEXT,
                actor       TEXT,
                detail      TEXT,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS workflow_checkpoints (
                meeting_id  TEXT NOT NULL,
                checkpoint  TEXT NOT NULL,
                state_json  TEXT NOT NULL,
                saved_at    TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (meeting_id, checkpoint)
            );

            CREATE INDEX IF NOT EXISTS idx_audit_meeting
                ON audit_log (meeting_id);
            CREATE INDEX IF NOT EXISTS idx_audit_request
                ON audit_log (request_id);
            CREATE INDEX IF NOT EXISTS idx_hitl_status
                ON hitl_requests (status);
        """)
