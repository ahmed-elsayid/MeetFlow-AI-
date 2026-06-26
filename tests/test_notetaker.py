from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.graph.nodes.notetaker import notetaker_node
from app.models.schemas import TranscriptChunk


def _chunk(text: str, speaker: str = "Sarah") -> TranscriptChunk:
    return TranscriptChunk(
        meeting_id="test_mtg",
        speaker=speaker,
        text=text,
        timestamp_start="00:10:00",
        timestamp_end="00:10:10",
        minute=10,
    )


def _make_state(chunks, **overrides):
    base = {
        "meeting_id": "test_mtg",
        "chunks": chunks,
        "classified": [],
        "notes": [],
        "decisions": [],
        "tasks": [],
        "research": [],
        "email_drafts": [],
        "pending_approvals": [],
        "is_meeting_active": True,
        "error_log": [],
    }
    base.update(overrides)
    return base


LLM_SECTIONS_RESPONSE = json.dumps({
    "sections": [
        {"topic": "Performance", "points": ["40% improvement after cache change"], "is_decision": False}
    ],
    "decisions": [],
})

LLM_DECISIONS_RESPONSE = json.dumps({
    "sections": [
        {"topic": "Frontend Migration", "points": ["Team agreed to use React"], "is_decision": True}
    ],
    "decisions": ["Use React for frontend migration"],
})


@pytest.mark.asyncio
@patch("app.graph.nodes.notetaker._write_to_notion", new_callable=AsyncMock)
@patch("app.graph.nodes.notetaker.build_llm")
async def test_notetaker_produces_notes(mock_build_llm, mock_write_notion):
    mock_llm = MagicMock()
    mock_response = AsyncMock()
    mock_response.content = LLM_SECTIONS_RESPONSE
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    mock_build_llm.return_value = mock_llm

    chunk = _chunk("The performance benchmarks show a 40% improvement after the cache change", "Mike")
    result = await notetaker_node(_make_state([chunk]))

    assert "notes" in result
    assert len(result["notes"]) == 1
    assert result["notes"][0].topic == "Performance"
    mock_write_notion.assert_not_called()  # live mode — no Notion write yet


@pytest.mark.asyncio
@patch("app.graph.nodes.notetaker._write_to_notion", new_callable=AsyncMock)
@patch("app.graph.nodes.notetaker.build_llm")
async def test_notetaker_captures_decisions(mock_build_llm, mock_write_notion):
    mock_llm = MagicMock()
    mock_response = AsyncMock()
    mock_response.content = LLM_DECISIONS_RESPONSE
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    mock_build_llm.return_value = mock_llm

    chunk = _chunk("We agreed to use React for the frontend migration", "Lisa")
    result = await notetaker_node(_make_state([chunk]))

    assert "decisions" in result
    assert "React" in result["decisions"][0]


@pytest.mark.asyncio
@patch("app.graph.nodes.notetaker._write_to_notion", new_callable=AsyncMock)
@patch("app.graph.nodes.notetaker.build_llm")
async def test_notetaker_post_meeting_writes_notion(mock_build_llm, mock_write_notion):
    """Post-meeting mode must call _write_to_notion."""
    mock_llm = MagicMock()
    mock_response = AsyncMock()
    mock_response.content = LLM_SECTIONS_RESPONSE
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    mock_build_llm.return_value = mock_llm

    chunks = [
        _chunk("Performance improved 40%", "Mike"),
        _chunk("We decided on React", "Lisa"),
    ]
    result = await notetaker_node(_make_state(chunks, is_meeting_active=False))

    mock_write_notion.assert_called_once()
    assert "notes" in result


@pytest.mark.asyncio
async def test_notetaker_empty_chunks_returns_empty():
    result = await notetaker_node(_make_state([]))
    assert result == {}


@pytest.mark.asyncio
@patch("app.graph.nodes.notetaker._write_to_notion", new_callable=AsyncMock)
@patch("app.graph.nodes.notetaker.build_llm")
async def test_notetaker_bad_json_returns_error_log(mock_build_llm, mock_write_notion):
    mock_llm = MagicMock()
    mock_response = AsyncMock()
    mock_response.content = "not valid json at all"
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    mock_build_llm.return_value = mock_llm

    chunk = _chunk("some text")
    result = await notetaker_node(_make_state([chunk]))

    assert "error_log" in result
    assert len(result["error_log"]) > 0
