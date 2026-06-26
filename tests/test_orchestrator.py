from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.graph.orchestrator import classify_chunk, route_by_classification
from app.models.schemas import ClassifiedChunk, TranscriptChunk


def _make_classified(classification: str) -> list[ClassifiedChunk]:
    chunk = TranscriptChunk(
        meeting_id="t", speaker="A", text="x",
        timestamp_start="00:00:00", timestamp_end="00:00:05", minute=0,
    )
    return [ClassifiedChunk(chunk=chunk, classification=classification, confidence=0.9)]


@pytest.mark.asyncio
@patch("app.graph.orchestrator.llm")
async def test_classify_chunk_discussion(mock_llm, sample_chunks):
    mock_response = AsyncMock()
    mock_response.content = '{"classification": "discussion", "confidence": 0.9}'
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    result = await classify_chunk(sample_chunks[5])

    assert isinstance(result, ClassifiedChunk)
    assert result.classification == "discussion"
    assert result.confidence == 0.9


@pytest.mark.asyncio
@patch("app.graph.orchestrator.llm")
async def test_classify_chunk_task(mock_llm, sample_chunks):
    mock_response = AsyncMock()
    mock_response.content = '{"classification": "task_commitment", "confidence": 0.92}'
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    result = await classify_chunk(sample_chunks[1])
    assert result.classification == "task_commitment"


@pytest.mark.asyncio
@patch("app.graph.orchestrator.llm")
async def test_classify_chunk_invalid_json_falls_back(mock_llm, sample_chunks):
    mock_response = AsyncMock()
    mock_response.content = "not valid json"
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    result = await classify_chunk(sample_chunks[0])
    assert result.classification == "discussion"
    assert result.confidence == 0.5


def test_route_discussion():
    assert route_by_classification({"classified": _make_classified("discussion")}) == "notetaker"


def test_route_decision():
    assert route_by_classification({"classified": _make_classified("decision")}) == "notetaker"


def test_route_task():
    assert route_by_classification({"classified": _make_classified("task_commitment")}) == "task_extractor"


def test_route_research():
    assert route_by_classification({"classified": _make_classified("research_trigger")}) == "researcher"


def test_route_off_topic():
    assert route_by_classification({"classified": _make_classified("off_topic")}) == "discard"


def test_route_empty_state():
    assert route_by_classification({"classified": []}) == "discard"
