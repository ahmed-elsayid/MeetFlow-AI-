from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.graph.nodes.researcher import researcher_node


def _base_state(classified):
    return {
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


SYNTHESIS_JSON = json.dumps({
    "summary": "K8s migration typically costs $50k-200k depending on scale.",
    "sources": ["Internal RAG document"],
})

WEB_SYNTHESIS_JSON = json.dumps({
    "summary": "According to web sources, K8s migration costs vary.",
    "sources": ["K8s Cost Guide"],
})


@pytest.mark.asyncio
@patch("app.graph.nodes.researcher.get_tavily_search")
@patch("app.graph.nodes.researcher.get_rag_service")
@patch("app.graph.nodes.researcher.llm")
async def test_researcher_uses_rag_when_good_results(
    mock_llm, mock_get_rag, mock_get_tavily, classified_research
):
    mock_rag = MagicMock()
    # RAG.query is now async
    mock_rag.query = AsyncMock(return_value=[
        {"text": "K8s migration costs range from $50k-200k", "metadata": {}, "distance": 0.3},
        {"text": "Cloud provider charges vary by workload", "metadata": {}, "distance": 0.4},
    ])
    mock_get_rag.return_value = mock_rag

    question_response = AsyncMock()
    question_response.content = "What are the Kubernetes migration costs?"
    synthesis_response = AsyncMock()
    synthesis_response.content = SYNTHESIS_JSON
    mock_llm.ainvoke = AsyncMock(side_effect=[question_response, synthesis_response])

    result = await researcher_node(_base_state(classified_research))

    assert len(result["research"]) == 1
    assert result["research"][0].from_rag is True
    mock_get_tavily.return_value.search.assert_not_called()


@pytest.mark.asyncio
@patch("app.graph.nodes.researcher.get_tavily_search")
@patch("app.graph.nodes.researcher.get_rag_service")
@patch("app.graph.nodes.researcher.llm")
async def test_researcher_falls_back_to_tavily(
    mock_llm, mock_get_rag, mock_get_tavily, classified_research
):
    mock_rag = MagicMock()
    mock_rag.query = AsyncMock(return_value=[
        {"text": "Unrelated chunk", "metadata": {}, "distance": 0.9},
    ])
    mock_get_rag.return_value = mock_rag

    mock_tavily = AsyncMock()
    mock_tavily.search = AsyncMock(return_value=[
        {"title": "K8s Cost Guide", "url": "https://example.com", "content": "Migration costs..."},
    ])
    mock_get_tavily.return_value = mock_tavily

    question_response = AsyncMock()
    question_response.content = "What are the Kubernetes migration costs?"
    synthesis_response = AsyncMock()
    synthesis_response.content = WEB_SYNTHESIS_JSON
    mock_llm.ainvoke = AsyncMock(side_effect=[question_response, synthesis_response])

    result = await researcher_node(_base_state(classified_research))

    assert len(result["research"]) == 1
    assert result["research"][0].from_rag is False


@pytest.mark.asyncio
async def test_researcher_empty_input():
    result = await researcher_node(_base_state([]))
    assert result["research"] == []
