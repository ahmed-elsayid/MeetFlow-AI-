from __future__ import annotations

import asyncio
import json
import logging

import redis.asyncio as aioredis

from app.config import settings
from app.graph.builder import build_live_graph
from app.models.schemas import TranscriptChunk
from app.services.redis_queue import (
    CONSUMER_GROUP,
    STREAM_CHUNKS,
    ensure_stream_group,
)

logger = logging.getLogger(__name__)

CONSUMER_NAME = "worker-1"


async def process_chunk_message(data: dict, graph) -> None:
    try:
        chunk = TranscriptChunk.model_validate_json(data["data"])
        logger.info("Processing chunk: [%s] %s", chunk.speaker, chunk.text[:50])

        state = {
            "meeting_id": chunk.meeting_id,
            "chunks": [chunk],
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

        result = await graph.ainvoke(state)
        logger.info(
            "Chunk processed — classification: %s",
            result.get("classified", [{}])[-1].classification
            if result.get("classified")
            else "unknown",
        )
    except Exception:
        logger.exception("Failed to process chunk message")


async def run_consumer() -> None:
    logger.info("Starting worker consumer...")
    r = aioredis.from_url(settings.redis_url, decode_responses=True)

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
                block=5000,
            )

            for stream_name, stream_messages in messages:
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
