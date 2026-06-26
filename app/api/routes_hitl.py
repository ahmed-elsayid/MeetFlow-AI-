"""HITL management endpoints consumed by the frontend dashboard."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.persistence.audit_log import get_meeting_audit_trail
from app.persistence.database import _connect
from app.persistence.hitl_store import get_hitl_request, list_pending_hitl_requests

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/hitl", tags=["hitl"])


@router.get("/pending")
async def list_pending():
    """List all HITL requests still awaiting a human decision."""
    try:
        items = await list_pending_hitl_requests()
        return {"items": items, "count": len(items)}
    except Exception:
        logger.exception("Failed to list pending HITL requests")
        raise HTTPException(500, "Failed to list pending requests")


@router.get("/all")
async def list_all(limit: int = 50):
    """List recent HITL requests (all statuses) for the frontend log view."""
    def _read() -> list[dict]:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM hitl_requests ORDER BY requested_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    try:
        import asyncio
        loop = asyncio.get_running_loop()
        items = await loop.run_in_executor(None, _read)
        return {"items": items, "count": len(items)}
    except Exception:
        logger.exception("Failed to list all HITL requests")
        raise HTTPException(500, "Failed to list requests")


@router.get("/{request_id}")
async def get_request(request_id: str):
    """Fetch a single HITL request by ID."""
    item = await get_hitl_request(request_id)
    if not item:
        raise HTTPException(404, "Request not found")
    return item


@router.get("/audit/events")
async def audit_events(meeting_id: str | None = None, limit: int = 100):
    """Fetch audit log events, optionally filtered by meeting_id."""
    def _read() -> list[dict]:
        with _connect() as conn:
            if meeting_id:
                rows = conn.execute(
                    "SELECT * FROM audit_log WHERE meeting_id=? ORDER BY created_at DESC LIMIT ?",
                    (meeting_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    try:
        import asyncio
        loop = asyncio.get_running_loop()
        items = await loop.run_in_executor(None, _read)
        return {"events": items, "count": len(items)}
    except Exception:
        logger.exception("Failed to fetch audit events")
        raise HTTPException(500, "Failed to fetch audit events")
