from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.models.schemas import TranscriptChunk
from app.services.rag import RAGService


@pytest.fixture
def mock_rag():
    with patch("app.services.rag.chromadb") as mock_chroma, \
         patch("app.services.rag.openai") as mock_openai:
        mock_collection = MagicMock()
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.HttpClient.return_value = mock_client

        mock_embed_response = MagicMock()
        mock_embed_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_openai_client = MagicMock()
        mock_openai_client.embeddings.create.return_value = mock_embed_response
        mock_openai.OpenAI.return_value = mock_openai_client

        service = RAGService()
        yield service, mock_collection


def test_embed_and_store(mock_rag):
    service, mock_collection = mock_rag

    chunk = TranscriptChunk(
        meeting_id="mtg_001",
        speaker="Sarah",
        text="Q3 deadline is September 15th",
        timestamp_start="00:12:34",
        timestamp_end="00:12:51",
        minute=12,
    )

    service.embed_and_store(chunk)

    mock_collection.upsert.assert_called_once()
    call_args = mock_collection.upsert.call_args
    assert call_args.kwargs["ids"] == ["mtg_001_00:12:34"]
    assert call_args.kwargs["metadatas"][0]["speaker"] == "Sarah"
    assert call_args.kwargs["metadatas"][0]["minute"] == 12


def test_query_with_filters(mock_rag):
    service, mock_collection = mock_rag

    mock_collection.query.return_value = {
        "documents": [["Q3 deadline discussion"]],
        "metadatas": [[{"speaker": "Sarah", "minute": 12}]],
        "distances": [[0.3]],
    }

    results = service.query(
        question="What about Q3?",
        meeting_id="mtg_001",
        speaker="Sarah",
        minute=12,
    )

    assert len(results) == 1
    assert results[0]["text"] == "Q3 deadline discussion"
    assert results[0]["distance"] == 0.3

    call_args = mock_collection.query.call_args
    where = call_args.kwargs["where"]
    assert "$and" in where


def test_query_single_filter(mock_rag):
    service, mock_collection = mock_rag

    mock_collection.query.return_value = {
        "documents": [["Some text"]],
        "metadatas": [[{"speaker": "Mike"}]],
        "distances": [[0.5]],
    }

    results = service.query(question="test", meeting_id="mtg_001")

    call_args = mock_collection.query.call_args
    where = call_args.kwargs["where"]
    assert where == {"meeting_id": "mtg_001"}


def test_upload_document(mock_rag):
    service, mock_collection = mock_rag

    service.upload_document(
        meeting_id="mtg_001",
        text="Pre-meeting document content",
        source_name="agenda",
    )

    mock_collection.upsert.assert_called_once()
    call_args = mock_collection.upsert.call_args
    assert call_args.kwargs["metadatas"][0]["source_type"] == "uploaded_document"
