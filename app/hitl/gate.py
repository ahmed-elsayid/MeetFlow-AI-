from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime

from app.config import settings
from app.models.enums import ApprovalStatus
from app.models.schemas import ApprovalRequest
from app.services.redis_queue import get_redis, publish_hitl_request

logger = logging.getLogger(__name__)


async def hitl_gate(
    action_type: str,
    payload: dict,
    timeout: int | None = None,
) -> ApprovalRequest:
    """Create an approval request and publish it for human review.

    Returns the ApprovalRequest immediately (does NOT wait for resolution).
    Use ``wait_for_approval`` to poll for the human's response.
    """
    request_id = str(uuid.uuid4())

    approval = ApprovalRequest(
        request_id=request_id,
        action_type=action_type,
        payload=payload,
        status=ApprovalStatus.PENDING,
        requested_at=datetime.utcnow(),
    )

    # Publish to Redis stream for persistence / fan-out
    await publish_hitl_request(approval.model_dump(mode="json"))

    # Best-effort: send a Teams adaptive card to the relevant user
    try:
        from app.services.teams_bot import teams_bot

        card = payload.get("adaptive_card")
        user_id = payload.get("user_id")
        if card and user_id:
            await teams_bot.send_adaptive_card(user_id=user_id, card=card)
    except Exception:
        logger.warning("Could not send Teams adaptive card for request %s", request_id)

    logger.info(
        "HITL gate opened: request_id=%s action_type=%s", request_id, action_type
    )
    return approval


async def wait_for_approval(
    request_id: str,
    timeout: int = 600,
) -> ApprovalStatus:
    """Poll Redis until a human responds or the timeout is reached."""
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
            except (json.JSONDecodeError, AttributeError):
                status_str = str(value)

            try:
                return ApprovalStatus(status_str)
            except ValueError:
                logger.warning("Unknown approval status: %s", status_str)
                return ApprovalStatus.APPROVED

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    logger.warning("HITL gate timed out for request %s", request_id)
    return ApprovalStatus.TIMED_OUT


async def record_approval(
    request_id: str,
    status: ApprovalStatus,
    resolved_by: str = "unknown",
) -> None:
    """Record a human's approval/rejection decision in Redis."""
    redis = await get_redis()
    key = f"hitl:response:{request_id}"
    data = {
        "status": status.value,
        "resolved_by": resolved_by,
        "resolved_at": datetime.utcnow().isoformat(),
    }
    await redis.set(key, json.dumps(data), ex=settings.hitl_timeout_seconds * 2)
    logger.info(
        "HITL decision recorded: request_id=%s status=%s by=%s",
        request_id,
        status.value,
        resolved_by,
    )
