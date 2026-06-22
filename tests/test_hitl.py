from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.hitl.adaptive_cards import email_approval_card, task_approval_card
from app.hitl.gate import hitl_gate, record_approval, wait_for_approval
from app.models.enums import ApprovalStatus
from app.models.schemas import EmailDraft, ExtractedTask


@pytest.mark.asyncio
@patch("app.hitl.gate.publish_hitl_request", new_callable=AsyncMock)
@patch("app.hitl.gate.get_redis")
async def test_hitl_gate_creates_request(mock_get_redis, mock_publish):
    mock_publish.return_value = "msg_123"

    result = await hitl_gate(
        action_type="send_email",
        payload={"subject": "Test email"},
    )

    assert result.action_type == "send_email"
    assert result.status == ApprovalStatus.PENDING
    assert result.request_id is not None
    mock_publish.assert_called_once()


@pytest.mark.asyncio
@patch("app.hitl.gate.get_redis")
async def test_wait_for_approval_approved(mock_get_redis):
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(
        return_value=json.dumps({"status": "approved", "resolved_by": "user1"})
    )
    mock_get_redis.return_value = mock_redis

    status = await wait_for_approval("req_123", timeout=10)

    assert status == ApprovalStatus.APPROVED


@pytest.mark.asyncio
@patch("app.hitl.gate.get_redis")
async def test_wait_for_approval_timeout(mock_get_redis):
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_get_redis.return_value = mock_redis

    status = await wait_for_approval("req_123", timeout=3)

    assert status == ApprovalStatus.TIMED_OUT


@pytest.mark.asyncio
@patch("app.hitl.gate.get_redis")
async def test_record_approval(mock_get_redis):
    mock_redis = AsyncMock()
    mock_get_redis.return_value = mock_redis

    await record_approval("req_123", ApprovalStatus.APPROVED, resolved_by="admin")

    mock_redis.set.assert_called_once()
    call_args = mock_redis.set.call_args
    data = json.loads(call_args.args[1])
    assert data["status"] == "approved"
    assert data["resolved_by"] == "admin"


def test_email_approval_card():
    draft = EmailDraft(
        variant="participant",
        subject="Meeting Recap: Q3 Planning",
        body_html="<html><body>Full recap here</body></html>",
        recipients=["a@example.com"],
    )

    card = email_approval_card(draft, request_id="req_123")

    assert card["type"] == "AdaptiveCard"
    assert card["version"] == "1.4"
    assert len(card["actions"]) == 3
    assert card["actions"][0]["data"]["action"] == "approve"


def test_task_approval_card():
    task = ExtractedTask(
        assignee="Unknown",
        task_description="Look into CI failures",
        priority="medium",
        is_ambiguous=True,
    )

    card = task_approval_card(task, request_id="req_456")

    assert card["type"] == "AdaptiveCard"
    assert len(card["actions"]) == 2
    assert card["actions"][1]["data"]["action"] == "reject"
