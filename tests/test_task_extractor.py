from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.graph.nodes.task_extractor import task_extractor_node


def _make_state(classified, **overrides):
    base = {
        "meeting_id": "test_mtg",
        "classified": classified,
        "notes": [],
        "decisions": [],
        "chunks": [],
        "tasks": [],
        "research": [],
        "email_drafts": [],
        "pending_approvals": [],
        "is_meeting_active": True,
        "error_log": [],
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
@patch("app.graph.nodes.task_extractor.JiraClient")
@patch("app.graph.nodes.task_extractor.ChatAnthropic")
async def test_extracts_clear_task(mock_llm_cls, mock_jira_cls, classified_task):
    mock_llm = MagicMock()
    mock_response = AsyncMock()
    mock_response.content = json.dumps({
        "tasks": [
            {
                "assignee": "Mike",
                "task_description": "Update the roadmap document",
                "deadline": "2026-06-27",
                "priority": "medium",
                "is_ambiguous": False,
            }
        ]
    })
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    mock_llm_cls.return_value = mock_llm

    result = await task_extractor_node(_make_state(classified_task))

    assert "tasks" in result
    assert len(result["tasks"]) == 1
    assert result["tasks"][0].assignee == "Mike"
    assert result["tasks"][0].is_ambiguous is False


@pytest.mark.asyncio
@patch("app.graph.nodes.task_extractor.JiraClient")
@patch("app.graph.nodes.task_extractor.ChatAnthropic")
async def test_detects_ambiguous_task(mock_llm_cls, mock_jira_cls, classified_ambiguous_task):
    mock_llm = MagicMock()
    mock_response = AsyncMock()
    mock_response.content = json.dumps({
        "tasks": [
            {
                "assignee": "Unknown",
                "task_description": "Look into the CI pipeline failures",
                "deadline": None,
                "priority": "medium",
                "is_ambiguous": True,
            }
        ]
    })
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    mock_llm_cls.return_value = mock_llm

    result = await task_extractor_node(_make_state(classified_ambiguous_task))

    assert result["tasks"][0].is_ambiguous is True


@pytest.mark.asyncio
async def test_empty_task_input():
    result = await task_extractor_node(_make_state([]))
    assert result.get("tasks", []) == []
