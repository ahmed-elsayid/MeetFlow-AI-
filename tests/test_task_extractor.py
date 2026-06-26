from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.graph.nodes.task_extractor import action_tasks_node

# stdio_client is imported inside action_tasks_node's function body, so we
# patch it at the mcp package level, not the task_extractor module level.
STDIO_PATCH = "mcp.client.stdio.stdio_client"
SESSION_PATCH = "mcp.client.session.ClientSession"

FAKE_JIRA_ENV = {
    "JIRA_BASE_URL": "https://fake.atlassian.net",
    "JIRA_EMAIL": "test@example.com",
    "JIRA_API_TOKEN": "fake-token",
    "JIRA_PROJECT_KEY": "TEST",
}


def _make_state(classified, **overrides):
    base = {
        "meeting_id": "test_mtg",
        "classified": classified,
        "action_items": [],
        "notes": [],
        "decisions": [],
        "chunks": [],
        "tasks": [],
        "research": [],
        "email_drafts": [],
        "pending_approvals": [],
        "is_meeting_active": True,
        "recipient_emails": [],
        "error_log": [],
    }
    base.update(overrides)
    return base


CLEAR_TASK_JSON = json.dumps([
    {
        "task": "Update the roadmap document",
        "assignee_name": "Mike",
        "due_date": "2026-06-27",
        "priority": "Medium",
        "notes": None,
    }
])

AMBIGUOUS_TASK_JSON = json.dumps([
    {
        "task": "Look into the CI pipeline failures",
        "assignee_name": "Unassigned",
        "due_date": None,
        "priority": "Medium",
        "notes": None,
    }
])

JIRA_BULK_RESULT = json.dumps([
    {"success": True, "summary": "Update the roadmap document", "issue_key": "PRJ-42", "url": "https://jira.example.com/PRJ-42"}
])

JIRA_BULK_AMBIGUOUS = json.dumps([
    {"success": True, "summary": "Look into the CI pipeline failures", "issue_key": "PRJ-43", "url": "https://jira.example.com/PRJ-43"}
])


def _mock_mcp_context(jira_json: str):
    """Return (mock_stdio_cm, mock_session_cm) that simulate a successful MCP connection."""
    block = MagicMock()
    block.text = jira_json
    tool_result = MagicMock()
    tool_result.content = [block]

    mock_session = AsyncMock()
    mock_session.call_tool = AsyncMock(return_value=tool_result)
    mock_session.initialize = AsyncMock()

    # stdio_client(...) returns an async context manager for (read, write)
    mock_stdio_cm = AsyncMock()
    mock_stdio_cm.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
    mock_stdio_cm.__aexit__ = AsyncMock(return_value=False)

    # ClientSession(read, write) returns an async context manager for session
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_cm.__aexit__ = AsyncMock(return_value=False)

    return mock_stdio_cm, mock_session_cm


@pytest.mark.asyncio
@patch.dict("os.environ", FAKE_JIRA_ENV)
@patch(SESSION_PATCH)
@patch(STDIO_PATCH)
@patch("app.graph.nodes.task_extractor.build_llm")
async def test_extracts_clear_task(mock_build_llm, mock_stdio, mock_session_cls, classified_task):
    mock_llm = MagicMock()
    mock_response = AsyncMock()
    mock_response.content = CLEAR_TASK_JSON
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    mock_build_llm.return_value = mock_llm

    mock_stdio_cm, mock_session_cm = _mock_mcp_context(JIRA_BULK_RESULT)
    mock_stdio.return_value = mock_stdio_cm
    mock_session_cls.return_value = mock_session_cm

    result = await action_tasks_node(_make_state(classified_task))

    assert "tasks" in result
    assert len(result["tasks"]) == 1
    assert result["tasks"][0].assignee == "Mike"
    assert result["tasks"][0].is_ambiguous is False


@pytest.mark.asyncio
@patch.dict("os.environ", FAKE_JIRA_ENV)
@patch(SESSION_PATCH)
@patch(STDIO_PATCH)
@patch("app.graph.nodes.task_extractor.build_llm")
async def test_extracts_ambiguous_task(mock_build_llm, mock_stdio, mock_session_cls, classified_ambiguous_task):
    mock_llm = MagicMock()
    mock_response = AsyncMock()
    mock_response.content = AMBIGUOUS_TASK_JSON
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    mock_build_llm.return_value = mock_llm

    mock_stdio_cm, mock_session_cm = _mock_mcp_context(JIRA_BULK_AMBIGUOUS)
    mock_stdio.return_value = mock_stdio_cm
    mock_session_cls.return_value = mock_session_cm

    result = await action_tasks_node(_make_state(classified_ambiguous_task))
    assert len(result["tasks"]) == 1


@pytest.mark.asyncio
async def test_empty_task_input():
    result = await action_tasks_node(_make_state([]))
    assert result.get("tasks", []) == []


@pytest.mark.asyncio
@patch.dict("os.environ", FAKE_JIRA_ENV)
@patch(SESSION_PATCH)
@patch(STDIO_PATCH)
@patch("app.graph.nodes.task_extractor.build_llm")
async def test_fallback_reads_from_classified(mock_build_llm, mock_stdio, mock_session_cls, classified_task):
    """When action_items is empty, the node must fall back to classified chunks."""
    mock_llm = MagicMock()
    mock_response = AsyncMock()
    mock_response.content = CLEAR_TASK_JSON
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    mock_build_llm.return_value = mock_llm

    mock_stdio_cm, mock_session_cm = _mock_mcp_context(JIRA_BULK_RESULT)
    mock_stdio.return_value = mock_stdio_cm
    mock_session_cls.return_value = mock_session_cm

    state = _make_state(classified_task, action_items=[])
    result = await action_tasks_node(state)
    assert len(result["tasks"]) == 1
