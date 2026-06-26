"""Append-only audit log backed by SQLite."""

from __future__ import annotations

import asyncio
import json
import logging

from app.persistence.database import _connect

logger = logging.getLogger(__name__)


async def log_event(
    event_type: str,
    meeting_id: str | None = None,
    request_id: str | None = None,
    actor: str | None = None,
    detail: dict | str | None = None,
) -> None:
    detail_str = (
        json.dumps(detail, default=str) if isinstance(detail, dict) else (detail or "")
    )

    def _write() -> None:
        with _connect() as conn:
            conn.execute(
                """INSERT INTO audit_log (event_type, meeting_id, request_id, actor, detail)
                   VALUES (?, ?, ?, ?, ?)""",
                (event_type, meeting_id, request_id, actor, detail_str),
            )

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _write)
    except Exception:
        # Audit log failures must never crash the main flow
        logger.warning("Failed to write audit log event: %s", event_type)


async def get_meeting_audit_trail(meeting_id: str) -> list[dict]:
    def _read() -> list[dict]:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE meeting_id=? ORDER BY created_at ASC",
                (meeting_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _read)
    except Exception:
        logger.warning("Failed to fetch audit trail for meeting %s", meeting_id)
        return []
