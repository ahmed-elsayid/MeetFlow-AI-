from __future__ import annotations

import asyncio
import logging

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.models.schemas import TranscriptChunk

logger = logging.getLogger(__name__)


class RAGService:
    """ChromaDB-backed retrieval-augmented generation service.

    Embeddings are lazy-initialised on first use so a missing/slow model
    doesn't crash the server on startup.  All ChromaDB calls run in a
    thread-pool executor so they never block the event loop.
    """

    def __init__(self) -> None:
        self.chroma = chromadb.PersistentClient(path=settings.chromadb_path)
        self.collection = self.chroma.get_or_create_collection("meeting_transcripts")
        self._embeddings = None  # initialised lazily on first embed call

    # ------------------------------------------------------------------
    # Embedding helpers
    # ------------------------------------------------------------------

    def _get_embeddings(self):
        """Return the embedding model, creating it on first call."""
        if self._embeddings is not None:
            return self._embeddings
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            self._embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
            )
            logger.info("HuggingFace embeddings model loaded")
        except Exception as exc:
            logger.error("Failed to load HuggingFace embeddings: %s", exc)
            raise RuntimeError(f"Embedding model unavailable: {exc}") from exc
        return self._embeddings

    async def _embed(self, text: str) -> list[float]:
        emb = self._get_embeddings()
        return await emb.aembed_query(text)

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        emb = self._get_embeddings()
        return await emb.aembed_documents(texts)

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def embed_and_store(self, chunk: TranscriptChunk) -> None:
        """Embed a single transcript chunk. Prefer embed_window() for richer context."""
        await self.embed_window([chunk])

    async def embed_window(self, chunks: list[TranscriptChunk]) -> None:
        """Embed a window of consecutive utterances as one ChromaDB document.

        Combining multiple utterances gives the retriever enough conversational
        context to return meaningful passages instead of isolated one-liners.
        The first chunk supplies the doc_id and metadata anchor; speakers are
        deduplicated so filters still work correctly.
        """
        if not chunks:
            return
        try:
            # Build the text that will be embedded and stored.
            # Format: "[Speaker]: text\n[Speaker]: text\n..."
            combined_text = "\n".join(f"[{c.speaker}]: {c.text}" for c in chunks)

            embedding = await self._embed(combined_text)

            anchor = chunks[0]
            # doc_id encodes the window start so upsert is idempotent for the same window.
            doc_id = f"{anchor.meeting_id}_w_{anchor.timestamp_start}"

            # Preserve unique speakers so speaker-filtered queries still work.
            seen: dict[str, None] = {}
            for c in chunks:
                seen[c.speaker] = None
            speakers = ", ".join(seen)

            metadata = {
                "meeting_id": anchor.meeting_id,
                "speaker": speakers,
                "timestamp_start": anchor.timestamp_start,
                "timestamp_end": chunks[-1].timestamp_end,
                "minute": anchor.minute,
                "topic_cluster": anchor.topic_cluster or "",
                "source_type": anchor.source_type,
            }

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: self.collection.upsert(
                    ids=[doc_id],
                    embeddings=[embedding],
                    documents=[combined_text],
                    metadatas=[metadata],
                ),
            )
            logger.debug(
                "Stored window %s (%d utterances, %d chars) in ChromaDB",
                doc_id, len(chunks), len(combined_text),
            )
        except Exception:
            logger.exception(
                "Failed to embed window starting at %s for meeting %s",
                chunks[0].timestamp_start if chunks else "?",
                chunks[0].meeting_id if chunks else "?",
            )

    async def query(
        self,
        question: str,
        meeting_id: str | None = None,
        speaker: str | None = None,
        minute: int | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        """Async two-stage retrieval: metadata filter then semantic search.

        Returns an empty list (never raises) so callers can always fall back
        to Tavily web search when the embedding model is unavailable or the
        collection is empty.
        """
        try:
            # Guard: querying an empty collection raises in some ChromaDB versions
            loop = asyncio.get_running_loop()
            count: int = await loop.run_in_executor(None, self.collection.count)
            if count == 0:
                logger.debug("ChromaDB collection is empty — skipping RAG query")
                return []

            where_filter: dict = {}
            if meeting_id is not None:
                where_filter["meeting_id"] = meeting_id
            if speaker is not None:
                where_filter["speaker"] = speaker
            if minute is not None:
                where_filter["minute"] = minute

            embedding = await self._embed(question)

            actual_top_k = min(top_k, count)
            query_kwargs: dict = {
                "query_embeddings": [embedding],
                "n_results": actual_top_k,
            }
            if where_filter:
                query_kwargs["where"] = (
                    where_filter
                    if len(where_filter) == 1
                    else {"$and": [{k: v} for k, v in where_filter.items()]}
                )

            results = await loop.run_in_executor(
                None, lambda: self.collection.query(**query_kwargs)
            )

            output: list[dict] = []
            if results and results.get("documents"):
                docs = results["documents"][0]
                metadatas = results.get("metadatas", [[{}] * len(docs)])[0]
                distances = results.get("distances", [[0.0] * len(docs)])[0]
                for doc, meta, dist in zip(docs, metadatas, distances):
                    output.append({"text": doc, "metadata": meta, "distance": dist})

            return output

        except RuntimeError:
            # Embedding model failed to load — degrade gracefully
            logger.warning("Embedding model unavailable; returning empty RAG results")
            return []
        except Exception:
            logger.exception("RAG query failed; returning empty results for fallback")
            return []

    async def delete_by_meeting(self, meeting_id: str) -> int:
        """Delete all ChromaDB documents for a given meeting."""
        try:
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(
                None,
                lambda: self.collection.get(where={"meeting_id": meeting_id}),
            )
            ids: list[str] = results.get("ids", [])
            if ids:
                await loop.run_in_executor(None, lambda: self.collection.delete(ids=ids))
            logger.info("Deleted %d ChromaDB docs for meeting %s", len(ids), meeting_id)
            return len(ids)
        except Exception:
            logger.exception("Failed to delete ChromaDB docs for meeting %s", meeting_id)
            return 0

    async def upload_document(self, meeting_id: str, text: str, source_name: str) -> None:
        """Split, embed, and store a supplementary document."""
        try:
            splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
            chunks = splitter.split_text(text)
            if not chunks:
                return

            embeddings = await self._embed_batch(chunks)

            ids = [f"{meeting_id}_doc_{source_name}_{i}" for i in range(len(chunks))]
            base_meta = {
                "meeting_id": meeting_id,
                "speaker": "",
                "timestamp_start": "",
                "timestamp_end": "",
                "minute": -1,
                "topic_cluster": "",
                "source_type": "uploaded_document",
            }
            metadatas = [base_meta] * len(chunks)

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: self.collection.upsert(
                    ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas
                ),
            )
            logger.info(
                "Stored %d chunk(s) from '%s' for meeting %s",
                len(chunks), source_name, meeting_id,
            )
        except Exception:
            logger.exception("Failed to upload document '%s'", source_name)
            raise


_rag_service: RAGService | None = None


def get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
