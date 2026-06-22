from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.graph.nodes.notetaker import notetaker_node


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
@patch("app.graph.nodes.notetaker.NotionClient")
@patch("app.graph.nodes.notetaker.ChatAnthropic")
async def test_notetaker_produces_notes(mock_llm_cls, mock_notion_cls, classified_discussion):
    mock_llm = MagicMock()
    mock_response = AsyncMock()
    mock_response.content = json.dumps({
        "sections": [
            {"topic": "Performance", "points": ["40% improvement after cache change"], "is_decision": False}
        ],
        "decisions": [],
    })
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    mock_llm_cls.return_value = mock_llm

    result = await notetaker_node(_make_state(classified_discussion))

    assert "notes" in result
    assert len(result["notes"]) == 1
    assert result["notes"][0].topic == "Performance"


@pytest.mark.asyncio
@patch("app.graph.nodes.notetaker.NotionClient")
@patch("app.graph.nodes.notetaker.ChatAnthropic")
async def test_notetaker_captures_decisions(mock_llm_cls, mock_notion_cls, classified_decision):
    mock_llm = MagicMock()
    mock_response = AsyncMock()
    mock_response.content = json.dumps({
        "sections": [
            {"topic": "Frontend Migration", "points": ["Team agreed to use React"], "is_decision": True}
        ],
        "decisions": ["Use React for frontend migration"],
    })
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    mock_llm_cls.return_value = mock_llm

    result = await notetaker_node(_make_state(classified_decision))

    assert "decisions" in result
    assert "React" in result["decisions"][0]


@pytest.mark.asyncio
async def test_notetaker_empty_input():
    result = await notetaker_node(_make_state([]))
    assert result.get("notes", []) == []
