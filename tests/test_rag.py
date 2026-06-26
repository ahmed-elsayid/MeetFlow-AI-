from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.schemas import TranscriptChunk
from app.services.rag import RAGService


@pytest.fixture
def mock_rag():
    """RAGService with mocked ChromaDB and Azure OpenAI embeddings."""
    with patch("app.services.rag.chromadb") as mock_chroma, \
         patch("app.services.rag.AzureOpenAIEmbeddings") as mock_embed_cls:

        mock_collection = MagicMock()
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.PersistentClient.return_value = mock_client

        mock_embeddings = AsyncMock()
        # aembed_query returns a single vector
        mock_embeddings.aembed_query = AsyncMock(return_value=[0.1] * 1536)
        # aembed_documents returns a list of vectors
        mock_embeddings.aembed_documents = AsyncMock(return_value=[[0.1] * 1536])
        mock_embed_cls.return_value = mock_embeddings

        service = RAGService()
        yield service, mock_collection


@pytest.mark.asyncio
async def test_embed_and_store(mock_rag):
    service, mock_collection = mock_rag

    chunk = TranscriptChunk(
        meeting_id="mtg_001",
        speaker="Sarah",
        text="Q3 deadline is September 15th",
        timestamp_start="00:12:34",
        timestamp_end="00:12:51",
        minute=12,
    )

    await service.embed_and_store(chunk)

    mock_collection.upsert.assert_called_once()
    call_kwargs = mock_collection.upsert.call_args.kwargs
    assert call_kwargs["ids"] == ["mtg_001_00:12:34"]
    assert call_kwargs["metadatas"][0]["speaker"] == "Sarah"
    assert call_kwargs["metadatas"][0]["minute"] == 12


@pytest.mark.asyncio
async def test_query_with_multiple_filters(mock_rag):
    service, mock_collection = mock_rag

    mock_collection.query.return_value = {
        "documents": [["Q3 deadline discussion"]],
        "metadatas": [[{"speaker": "Sarah", "minute": 12}]],
        "distances": [[0.3]],
    }

    results = await service.query(
        question="What about Q3?",
        meeting_id="mtg_001",
        speaker="Sarah",
        minute=12,
    )

    assert len(results) == 1
    assert results[0]["text"] == "Q3 deadline discussion"
    assert results[0]["distance"] == 0.3

    call_kwargs = mock_collection.query.call_args.kwargs
    assert "$and" in call_kwargs["where"]


@pytest.mark.asyncio
async def test_query_single_filter(mock_rag):
    service, mock_collection = mock_rag

    mock_collection.query.return_value = {
        "documents": [["Some text"]],
        "metadatas": [[{"speaker": "Mike"}]],
        "distances": [[0.5]],
    }

    results = await service.query(question="test", meeting_id="mtg_001")

    call_kwargs = mock_collection.query.call_args.kwargs
    assert call_kwargs["where"] == {"meeting_id": "mtg_001"}


@pytest.mark.asyncio
async def test_upload_document(mock_rag):
    service, mock_collection = mock_rag

    # Return two vectors since RecursiveCharacterTextSplitter may produce ≥1 chunks
    service._embeddings.aembed_documents = AsyncMock(return_value=[[0.1] * 1536])

    await service.upload_document(
        meeting_id="mtg_001",
        text="Pre-meeting document content about the project",
        source_name="agenda",
    )

    mock_collection.upsert.assert_called_once()
    call_kwargs = mock_collection.upsert.call_args.kwargs
    assert call_kwargs["metadatas"][0]["source_type"] == "uploaded_document"


@pytest.mark.asyncio
async def test_query_no_filter(mock_rag):
    service, mock_collection = mock_rag

    mock_collection.query.return_value = {
        "documents": [["result"]],
        "metadatas": [[{}]],
        "distances": [[0.2]],
    }

    results = await service.query(question="anything")
    assert len(results) == 1
    # No where filter when no constraints
    call_kwargs = mock_collection.query.call_args.kwargs
    assert "where" not in call_kwargs
