from __future__ import annotations

import asyncio
import logging

import redis.asyncio as aioredis

from app.config import settings
from app.graph.builder import build_live_graph
from app.models.schemas import TranscriptChunk
from app.services.rag import get_rag_service
from app.services.redis_queue import (
    CONSUMER_GROUP,
    STREAM_CHUNKS,
    ensure_stream_group,
    get_meeting_state,
    store_meeting_state,
)

logger = logging.getLogger(__name__)

CONSUMER_NAME = "worker-1"


def _default_state(meeting_id: str) -> dict:
    return {
        "meeting_id": meeting_id,
        "chunks": [],
        "classified": [],
        "notes": [],
        "decisions": [],
        "action_items": [],
        "tasks": [],
        "research": [],
        "email_drafts": [],
        "pending_approvals": [],
        "is_meeting_active": True,
        "recipient_emails": [],
        "stakeholder_emails": [],
        "error_log": [],
        "transcript": "",
    }


async def process_chunk_message(data: dict, graph) -> None:
    try:
        chunk = TranscriptChunk.model_validate_json(data["data"])
        logger.info("Processing chunk: [%s] %s", chunk.speaker, chunk.text[:50])

        # Load the full meeting state from Redis so accumulated lists carry
        # forward (recipient_emails, classified history, existing notes, etc.)
        stored = await get_meeting_state(chunk.meeting_id)
        state = stored if stored else _default_state(chunk.meeting_id)

        # Embed chunk into ChromaDB so the researcher has RAG context
        try:
            await get_rag_service().embed_and_store(chunk)
        except Exception:
            logger.warning("RAG embed failed for chunk from worker")

        # Run the live graph with the loaded state + this new chunk
        input_state = {**state, "chunks": [chunk]}
        result = await graph.ainvoke(input_state)

        # Merge list fields back (add-reducer semantics)
        for key in state:
            if key in result:
                if isinstance(result[key], list):
                    state[key] = result[key]
                else:
                    state[key] = result[key]

        await store_meeting_state(chunk.meeting_id, state)

        classified = result.get("classified", [])
        label = (
            classified[-1].classification
            if classified and hasattr(classified[-1], "classification")
            else "unknown"
        )
        logger.info("Chunk processed — classification: %s", label)

    except Exception:
        logger.exception("Failed to process chunk message")


async def run_consumer() -> None:
    logger.info("Starting worker consumer...")
    # socket_timeout=None is required for blocking stream reads — the Redis
    # block param controls how long the server waits; a socket-level timeout
    # shorter than that will fire first and raise a spurious TimeoutError.
    r = aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=None,
        socket_connect_timeout=5,
    )

    await ensure_stream_group(STREAM_CHUNKS, CONSUMER_GROUP)
    graph = build_live_graph()

    logger.info("Worker consumer ready, listening on stream: %s", STREAM_CHUNKS)

    while True:
        try:
            messages = await r.xreadgroup(
                CONSUMER_GROUP,
                CONSUMER_NAME,
                {STREAM_CHUNKS: ">"},
                count=1,
                block=2000,  # 2 s — server returns None if no message; loop retries
            )

            if not messages:
                continue

            for _stream_name, stream_messages in messages:
                for msg_id, msg_data in stream_messages:
                    await process_chunk_message(msg_data, graph)
                    await r.xack(STREAM_CHUNKS, CONSUMER_GROUP, msg_id)

        except aioredis.ConnectionError:
            logger.warning("Redis connection lost, retrying in 5s...")
            await asyncio.sleep(5)
        except Exception:
            logger.exception("Worker error")
            await asyncio.sleep(1)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(run_consumer())


if __name__ == "__main__":
    main()
