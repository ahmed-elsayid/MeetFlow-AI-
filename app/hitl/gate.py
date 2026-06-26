from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime

from app.config import settings
from app.models.enums import ApprovalStatus
from app.models.schemas import ApprovalRequest
from app.persistence.audit_log import log_event
from app.persistence.hitl_store import save_hitl_request, update_hitl_status
from app.services.redis_queue import get_redis, publish_hitl_request

logger = logging.getLogger(__name__)


async def hitl_gate(
    action_type: str,
    payload: dict,
    timeout: int | None = None,
) -> ApprovalRequest:
    """Create an approval request, persist it, and notify the reviewer.

    Returns immediately — use ``wait_for_approval`` to poll for the response.
    """
    request_id = str(uuid.uuid4())

    approval = ApprovalRequest(
        request_id=request_id,
        action_type=action_type,
        payload=payload,
        status=ApprovalStatus.PENDING,
        requested_at=datetime.utcnow(),
    )

    # Persist to Redis (for live polling) and SQLite (for durability)
    await publish_hitl_request(approval.model_dump(mode="json"))
    await save_hitl_request(request_id, action_type, payload)
    await log_event(
        "hitl_opened",
        request_id=request_id,
        detail={"action_type": action_type},
    )

    # Best-effort: send Teams adaptive card
    try:
        from app.services.teams_bot import teams_bot

        card = payload.get("adaptive_card")
        user_id = payload.get("user_id")
        if card and user_id:
            await teams_bot.send_adaptive_card(user_id=user_id, card=card)
    except Exception:
        logger.warning("Could not send Teams adaptive card for request %s", request_id)

    logger.info("HITL gate opened: %s  action=%s", request_id, action_type)
    return approval


async def wait_for_approval(
    request_id: str,
    timeout: int = 600,
) -> tuple[ApprovalStatus, dict | None]:
    """Poll Redis until a human responds or the timeout is reached.

    Returns a ``(status, edited_payload)`` tuple. ``edited_payload`` is the
    dict the reviewer submitted when choosing "Approve with edits", or ``None``
    for plain approvals / rejections.
    """
    redis = await get_redis()
    key = f"hitl:response:{request_id}"
    elapsed = 0
    poll_interval = 2

    while elapsed < timeout:
        value = await redis.get(key)
        if value is not None:
            try:
                data = json.loads(value)
                status_str = data.get("status", "approved")
                edited_payload = data.get("edited_payload")
            except (json.JSONDecodeError, AttributeError):
                status_str = str(value)
                edited_payload = None

            try:
                return ApprovalStatus(status_str), edited_payload
            except ValueError:
                logger.warning("Unknown approval status value: %s", status_str)
                return ApprovalStatus.APPROVED, None

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    logger.warning("HITL gate timed out for request %s", request_id)
    return ApprovalStatus.TIMED_OUT, None


async def record_approval(
    request_id: str,
    status: ApprovalStatus,
    resolved_by: str = "unknown",
    edited_payload: dict | None = None,
) -> None:
    """Record a human's decision in both Redis and SQLite."""
    redis = await get_redis()
    key = f"hitl:response:{request_id}"
    data: dict = {
        "status": status.value,
        "resolved_by": resolved_by,
        "resolved_at": datetime.utcnow().isoformat(),
    }
    if edited_payload is not None:
        data["edited_payload"] = edited_payload
    await redis.set(key, json.dumps(data), ex=settings.hitl_timeout_seconds * 2)

    await update_hitl_status(request_id, status.value, resolved_by)
    await log_event(
        "hitl_resolved",
        request_id=request_id,
        actor=resolved_by,
        detail={"status": status.value},
    )

    logger.info(
        "HITL decision recorded: %s  status=%s  by=%s",
        request_id, status.value, resolved_by,
    )
