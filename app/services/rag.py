from __future__ import annotations

import logging

import chromadb
import openai

from app.config import settings
from app.models.schemas import TranscriptChunk

logger = logging.getLogger(__name__)


class RAGService:
    """ChromaDB-backed retrieval-augmented generation service."""

    def __init__(self) -> None:
        self.chroma = chromadb.HttpClient(
            host=settings.chromadb_host,
            port=settings.chromadb_port,
        )
        self.collection = self.chroma.get_or_create_collection("meeting_transcripts")
        self.openai_client = openai.OpenAI(api_key=settings.openai_api_key)

    def _embed(self, text: str) -> list[float]:
        """Generate an embedding using OpenAI text-embedding-3-small."""
        response = self.openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding

    def embed_and_store(self, chunk: TranscriptChunk) -> None:
        """Embed a transcript chunk and store it in ChromaDB."""
        try:
            embedding = self._embed(chunk.text)
            doc_id = f"{chunk.meeting_id}_{chunk.timestamp_start}"

            metadata = {
                "meeting_id": chunk.meeting_id,
                "speaker": chunk.speaker,
                "timestamp_start": chunk.timestamp_start,
                "timestamp_end": chunk.timestamp_end,
                "minute": chunk.minute,
                "topic_cluster": chunk.topic_cluster or "",
                "source_type": chunk.source_type,
            }

            self.collection.upsert(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[chunk.text],
                metadatas=[metadata],
            )
            logger.debug("Stored chunk %s in ChromaDB", doc_id)
        except Exception:
            logger.exception("Failed to embed and store chunk")
            raise

    def query(
        self,
        question: str,
        meeting_id: str | None = None,
        speaker: str | None = None,
        minute: int | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        """Two-stage retrieval: filter by metadata, then semantic search."""
        where_filter: dict = {}
        if meeting_id is not None:
            where_filter["meeting_id"] = meeting_id
        if speaker is not None:
            where_filter["speaker"] = speaker
        if minute is not None:
            where_filter["minute"] = minute

        embedding = self._embed(question)

        query_kwargs: dict = {
            "query_embeddings": [embedding],
            "n_results": top_k,
        }
        if where_filter:
            if len(where_filter) == 1:
                query_kwargs["where"] = where_filter
            else:
                query_kwargs["where"] = {
                    "$and": [
                        {k: v} for k, v in where_filter.items()
                    ]
                }

        results = self.collection.query(**query_kwargs)

        output: list[dict] = []
        if results and results.get("documents"):
            docs = results["documents"][0]
            metadatas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            distances = results["distances"][0] if results.get("distances") else [0.0] * len(docs)

            for doc, meta, dist in zip(docs, metadatas, distances):
                output.append({
                    "text": doc,
                    "metadata": meta,
                    "distance": dist,
                })

        return output

    def upload_document(self, meeting_id: str, text: str, source_name: str) -> None:
        """Embed and store a supplementary document (not a live transcript chunk)."""
        try:
            embedding = self._embed(text)
            doc_id = f"{meeting_id}_doc_{source_name}"

            metadata = {
                "meeting_id": meeting_id,
                "speaker": "",
                "timestamp_start": "",
                "timestamp_end": "",
                "minute": -1,
                "topic_cluster": "",
                "source_type": "uploaded_document",
            }

            self.collection.upsert(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[metadata],
            )
            logger.info("Stored uploaded document '%s' for meeting %s", source_name, meeting_id)
        except Exception:
            logger.exception("Failed to upload document '%s'", source_name)
            raise


_rag_service: RAGService | None = None


def get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
