"""HITL request persistence — thin async wrappers over SQLite."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from app.persistence.database import _connect

logger = logging.getLogger(__name__)


async def save_hitl_request(
    request_id: str,
    action_type: str,
    payload: dict,
    status: str = "pending",
) -> None:
    def _write() -> None:
        with _connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO hitl_requests
                   (request_id, action_type, payload, status, requested_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    request_id,
                    action_type,
                    json.dumps(payload, default=str),
                    status,
                    datetime.utcnow().isoformat(),
                ),
            )

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _write)
    except Exception:
        logger.warning("Failed to save HITL request %s to SQLite", request_id)


async def update_hitl_status(
    request_id: str,
    status: str,
    resolved_by: str = "unknown",
) -> None:
    def _write() -> None:
        with _connect() as conn:
            conn.execute(
                """UPDATE hitl_requests
                   SET status=?, resolved_at=?, resolved_by=?
                   WHERE request_id=?""",
                (status, datetime.utcnow().isoformat(), resolved_by, request_id),
            )

    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _write)
    except Exception:
        logger.warning("Failed to update HITL status for %s", request_id)


async def get_hitl_request(request_id: str) -> dict | None:
    def _read() -> dict | None:
        with _connect() as conn:
            row = conn.execute(
                "SELECT * FROM hitl_requests WHERE request_id=?", (request_id,)
            ).fetchone()
            return dict(row) if row else None

    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _read)
    except Exception:
        logger.warning("Failed to fetch HITL request %s", request_id)
        return None


async def delete_hitl_requests_for_meeting(meeting_id: str) -> int:
    """Delete all HITL records whose payload references this meeting_id."""
    def _delete() -> int:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM hitl_requests WHERE payload LIKE ?",
                (f"%{meeting_id}%",),
            )
            return cur.rowcount

    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _delete)
    except Exception:
        logger.warning("Failed to delete HITL records for meeting %s", meeting_id)
        return 0


async def list_pending_hitl_requests() -> list[dict]:
    def _read() -> list[dict]:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM hitl_requests WHERE status='pending' ORDER BY requested_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _read)
    except Exception:
        logger.warning("Failed to list pending HITL requests")
        return []
