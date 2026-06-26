from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.hitl.gate import record_approval
from app.models.schemas import ApprovalResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/approval", tags=["approval"])


@router.post("/respond")
async def approval_respond(resp: ApprovalResponse):
    """Webhook endpoint for Teams adaptive card approval responses."""
    try:
        await record_approval(
            request_id=resp.request_id,
            status=resp.status,
            resolved_by=resp.resolved_by,
            edited_payload=resp.edited_payload,
        )
        return {"status": "recorded", "request_id": resp.request_id}
    except Exception:
        logger.exception("Failed to record approval response")
        raise HTTPException(500, "Failed to record approval")
