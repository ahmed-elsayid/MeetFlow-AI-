from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import settings
from app.models.schemas import TranscriptChunk

logger = logging.getLogger(__name__)

_pool: aioredis.Redis | None = None

STREAM_CHUNKS = "meeting:chunks"
STREAM_HITL = "hitl:requests"
CONSUMER_GROUP = "meeting-workers"


async def get_redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _pool


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


async def ensure_stream_group(stream: str, group: str) -> None:
    r = await get_redis()
    try:
        await r.xgroup_create(stream, group, id="0", mkstream=True)
    except aioredis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


async def publish_chunk(chunk: TranscriptChunk) -> str:
    r = await get_redis()
    msg_id = await r.xadd(STREAM_CHUNKS, {"data": chunk.model_dump_json()})
    return msg_id


async def publish_hitl_request(data: dict) -> str:
    r = await get_redis()
    msg_id = await r.xadd(STREAM_HITL, {"data": json.dumps(data)})
    return msg_id


async def set_key(key: str, value: Any, ex: int | None = None) -> None:
    r = await get_redis()
    await r.set(key, json.dumps(value) if not isinstance(value, str) else value, ex=ex)


async def get_key(key: str) -> str | None:
    r = await get_redis()
    return await r.get(key)


async def store_meeting_state(meeting_id: str, state: dict) -> None:
    r = await get_redis()
    await r.set(f"meeting:{meeting_id}:state", json.dumps(state, default=str))


async def get_meeting_state(meeting_id: str) -> dict | None:
    r = await get_redis()
    data = await r.get(f"meeting:{meeting_id}:state")
    if data:
        return json.loads(data)
    return None
